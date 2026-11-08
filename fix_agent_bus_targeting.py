#!/usr/bin/env python3
"""fix_agent_bus_targeting.py -- make the IPC entry point honour a target by name.

Defect (measured 2026-11-01 23:25Z with the Hermes self-test):
    WebSocket {"type":"agent.task","payload":{"type":"route",...}}
      -> AgentBus.handleIpcMessage -> submitTask(type, payload, undefined)
      -> routeTask()  "send to first available executor"
      -> the Executor ran the *route* task and Hermes never saw it.

So the router was unreachable from the front door: a caller had to already know Hermes'
uuid. A task addressed to "Hermes" / "hermes" (or with agentId absent but type "route")
must reach Hermes, and a name must resolve to a real id instead of being passed through
as if it were one.

Three rules added here:
  1. resolveAgentId(ref) accepts an id, a name ("Executor") or a role ("executor").
  2. submitTask() resolves its target through that, and fails loudly on an unknown name
     instead of silently handing the task to somebody else.
  3. routeTask() sends "route"/"relay" tasks to Hermes when it is registered, and
     handleIpcMessage() accepts agentId | targetAgent | agent from the payload.

Run: python SCRIPTS/fix_agent_bus_targeting.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUS = ROOT / "AGENTS" / "agent-system" / "agent-core" / "src" / "core" / "agent-bus.ts"

SUBMIT_OLD = """    // If target specified, assign directly
    if (targetAgentId) {
      await this.processTask(task, targetAgentId);
    } else {
      // Auto-route: find an appropriate agent
      await this.routeTask(task);
    }"""

SUBMIT_NEW = """    // If a target is specified, assign directly -- by id, name or role.
    if (targetAgentId) {
      const resolved = this.resolveAgentId(targetAgentId);
      if (!resolved) {
        throw new Error(
          `submitTask(${type}): no agent matches '${targetAgentId}' ` +
            `(known: ${this.getAgents().map((a) => a.name).join(", ")})`,
        );
      }
      await this.processTask(task, resolved);
    } else {
      // Auto-route: find an appropriate agent
      await this.routeTask(task);
    }"""

ROUTE_OLD = """  /** Route a task to the appropriate agent */
  private async routeTask(task: AgentTask): Promise<void> {
    // Simple routing: send to first available executor, or first agent
    const executors = this.getAgents().filter(
      (a) => (a as any).role === "executor",
    );
    const target = executors.length > 0 ? executors[0] : this.getAgents()[0];

    if (target) {
      await this.processTask(task, target.id);
    }
  }"""

ROUTE_NEW = """  /**
   * Resolve an id, a name ("Executor") or a role ("executor") to a real agent id.
   * Returns undefined when nothing matches -- callers decide whether that is fatal.
   */
  resolveAgentId(ref?: string): string | undefined {
    if (!ref) return undefined;
    const want = ref.trim().toLowerCase();
    const hit = this.getAgents().find(
      (a) =>
        a.id === ref ||
        a.name.trim().toLowerCase() === want ||
        String((a as any).role ?? "").toLowerCase() === want,
    );
    return hit?.id;
  }

  /** Route a task to the appropriate agent */
  private async routeTask(task: AgentTask): Promise<void> {
    // Messaging verbs belong to Hermes; nothing else can answer them.
    if (task.type === "route" || task.type === "relay" || task.type === "broadcast") {
      const hermes = this.getAgents().find((a) => a.name.trim().toLowerCase() === "hermes");
      if (hermes) {
        await this.processTask(task, hermes.id);
        return;
      }
    }

    // Otherwise: first available executor, else first agent.
    const executors = this.getAgents().filter(
      (a) => (a as any).role === "executor",
    );
    const target = executors.length > 0 ? executors[0] : this.getAgents()[0];

    if (target) {
      await this.processTask(task, target.id);
    }
  }"""

HANDLE_OLD = """      case "agent.task": {
        const { type, payload, agentId } = msg.payload as any;
        await this.submitTask(type, payload, agentId);
        break;
      }"""

HANDLE_NEW = """      case "agent.task": {
        const { type, payload, agentId } = msg.payload as any;
        // A caller may address by id, name or role, under any of these keys.
        const p = (msg.payload as any) ?? {};
        const target = agentId ?? p.targetAgent ?? p.agent ?? p.target;
        await this.submitTask(type, payload, target);
        break;
      }"""


def main() -> int:
    text = BUS.read_text(encoding="utf-8-sig")
    # Markers that survive later patches too: fix_ipc_task_correlation.py appends msg.id to
    # the submitTask call, so matching HANDLE_NEW verbatim would report a false "not applied".
    applied = "resolveAgentId(" in text and "p.targetAgent ?? p.agent ?? p.target" in text
    if applied:
        print(("PASS " if "--check" in sys.argv else "already patched: ") + f"{BUS.name}")
        return 0

    missing = [
        name
        for name, old in (
            ("submitTask", SUBMIT_OLD),
            ("routeTask", ROUTE_OLD),
            ("handleIpcMessage", HANDLE_OLD),
        )
        if old not in text
    ]
    if missing:
        print(f"FAIL  anchors missing in {BUS.name}: {missing}")
        return 1
    if "--check" in sys.argv:
        print(f"FAIL  targeting not applied in {BUS.name}")
        return 1

    backup = BUS.with_suffix(BUS.suffix + ".bak-targeting")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    text = text.replace(SUBMIT_OLD, SUBMIT_NEW, 1)
    text = text.replace(ROUTE_OLD, ROUTE_NEW, 1)
    text = text.replace(HANDLE_OLD, HANDLE_NEW, 1)
    BUS.write_text(text, encoding="utf-8")
    print("patched: resolveAgentId + routeTask(Hermes) + handleIpcMessage(target)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
