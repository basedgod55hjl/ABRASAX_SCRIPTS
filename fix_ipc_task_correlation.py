#!/usr/bin/env python3
"""fix_ipc_task_correlation.py -- let a caller correlate a reply with the request it sent.

Before: AgentBus.handleIpcMessage() -> submitTask() minted a *new* uuid for every task, so
the id a client put on its IPC message appeared nowhere in the reply. A front end could
only guess which answer belonged to which question (and the self-test could not assert it).

Now: submitTask() accepts an optional taskId, and the IPC entry point passes msg.id, so
   request  {id: X, type:"agent.task"}  ->  reply {payload.taskId: X, ...}
holds for the direct agent response and for Hermes' asynchronous hermes.response alike.

Run: python SCRIPTS/fix_ipc_task_correlation.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUS = ROOT / "AGENTS" / "agent-system" / "agent-core" / "src" / "core" / "agent-bus.ts"

SIG_OLD = """  async submitTask(
    type: string,
    payload: unknown,
    targetAgentId?: string,
  ): Promise<string> {
    const task: AgentTask = {
      id: uuid(),"""

SIG_NEW = """  async submitTask(
    type: string,
    payload: unknown,
    targetAgentId?: string,
    taskId?: string,
  ): Promise<string> {
    const task: AgentTask = {
      // An IPC caller supplies its message id, so every reply can carry it back.
      id: taskId ?? uuid(),"""

CALL_OLD = "        await this.submitTask(type, payload, target);"
CALL_NEW = "        await this.submitTask(type, payload, target, msg.id);"


def main() -> int:
    text = BUS.read_text(encoding="utf-8-sig")
    done = "id: taskId ?? uuid()," in text and CALL_NEW in text
    if done:
        print(("PASS " if "--check" in sys.argv else "already patched: ") + BUS.name)
        return 0
    if "--check" in sys.argv:
        print(f"FAIL  task correlation not applied in {BUS.name}")
        return 1
    for name, old in (("submitTask signature", SIG_OLD), ("handleIpcMessage call", CALL_OLD)):
        if old not in text:
            print(f"FAIL  anchor missing: {name}")
            return 1

    backup = BUS.with_suffix(BUS.suffix + ".bak-taskcorr")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    text = text.replace(SIG_OLD, SIG_NEW, 1).replace(CALL_OLD, CALL_NEW, 1)
    BUS.write_text(text, encoding="utf-8")
    print("patched: submitTask(taskId) + IPC passes msg.id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
