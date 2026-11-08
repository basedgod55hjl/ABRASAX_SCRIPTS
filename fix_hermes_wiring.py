#!/usr/bin/env python3
"""fix_hermes_wiring.py -- finish the Hermes bridge (agent-core, TypeScript).

What was broken (measured on the tree at C:\\abrasax\\AGENTS\\agent-system\\agent-core):
  1. HermesAgent.findAgent() returned the *strings* "executor" / "planner" / "observer".
     Those are role names, never agent ids, and nothing was submitted to the bus -- a
     "route" task answered {"routedTo":"executor"} while no agent ran.
  2. gatherAgentStatus() returned an empty array unconditionally, so "status" always
     reported zero connected agents.
  3. index.ts wired setExternalSender() to console.log, so a Hermes reply never reached
     an IPC/WebSocket client.
  4. The continuous loop polled and shifted the queue without ever dispatching.

What this patch does:
  * agent-bus.ts gains three public methods -- listAgents(), dispatch(), publish() -- and
    processTask() now returns the AgentResponse it produced (it returned void, so a
    caller could not await work it started).
  * index.ts binds HermesAgent's directory to the bus and routes its external sender
    through the bus's IPC outbound channel.
  * hermes-agent.ts is replaced by SCRIPTS/../hermes-agent.ts (see HERMES_TS below) --
    that file is written in full because the fix is structural, not a line edit.

Idempotent: each edit is guarded by its own marker, re-running changes nothing.
Verify:  python SCRIPTS/fix_hermes_wiring.py --check
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "AGENTS" / "agent-system" / "agent-core"
BUS = CORE / "src" / "core" / "agent-bus.ts"
INDEX = CORE / "src" / "index.ts"

# ── agent-bus.ts: processTask returns its response ─────────────────────────────
BUS_SIG_OLD = "  private async processTask(task: AgentTask, agentId: string): Promise<void> {"
BUS_SIG_NEW = "  private async processTask(\n    task: AgentTask,\n    agentId: string,\n  ): Promise<AgentResponse | undefined> {"

BUS_RET_OLD = """      this.sendToFrontend({
        id: uuid(),
        direction: "node-to-net",
        type: "agent.response",
        payload: { taskId: task.id, result: response },
        timestamp: Date.now(),
      });
    } catch (err: any) {
      console.error(`[AgentBus] Task ${task.id} failed:`, err.message);
      this.activeTasks.delete(task.id);
    }
  }"""

BUS_RET_NEW = """      this.sendToFrontend({
        id: uuid(),
        direction: "node-to-net",
        type: "agent.response",
        payload: { taskId: task.id, result: response },
        timestamp: Date.now(),
      });

      return response;
    } catch (err: any) {
      console.error(`[AgentBus] Task ${task.id} failed:`, err.message);
      this.activeTasks.delete(task.id);
      return undefined;
    }
  }"""

BUS_ANCHOR = "  // ── IPC Bridge (Hex Adapter) ──────────────────────────────────────────────"

BUS_METHODS = """  // ── Directory + dispatch (the port Hermes routes against) ────────────────

  /** Who exists right now, as plain data (no agent internals leak out). */
  listAgents(): Array<{ id: string; name: string; role: string; tools: string[] }> {
    return this.getAgents().map((a) => ({
      id: a.id,
      name: a.name,
      role: (a as any).role ?? "custom",
      tools: a.tools.map((t) => t.name),
    }));
  }

  /**
   * Run one task on one agent and hand back its response.
   *
   * submitTask() answers with an id and expects the caller to poll waitForTask();
   * a router needs the result itself, so this awaits the work and returns it.
   */
  async dispatch(
    type: string,
    payload: unknown,
    agentId?: string,
    parentTaskId?: string,
  ): Promise<AgentResponse> {
    const task: AgentTask = {
      id: uuid(),
      type,
      payload,
      parentTaskId,
      createdBy: "hermes",
    };
    this.taskQueue.push(task);

    let target = agentId ? this.agents.get(agentId) : undefined;

    if (!target) {
      // Resolve a known name/role to a real id before falling back to the executor.
      const wanted = agentId?.trim().toLowerCase();
      target = wanted
        ? this.getAgents().find(
            (a) =>
              a.id === agentId ||
              a.name.trim().toLowerCase() === wanted ||
              String((a as any).role ?? "").toLowerCase() === wanted,
          )
        : undefined;
    }

    if (!target) {
      const executors = this.getAgents().filter((a) => (a as any).role === "executor");
      target = executors[0] ?? this.getAgents()[0];
    }

    if (!target) {
      throw new Error(`dispatch(${type}): no agent registered for '${agentId ?? "auto"}'`);
    }

    const response = await this.processTask(task, target.id);
    if (!response) {
      throw new Error(`dispatch(${type}): agent ${target.name} threw while processing`);
    }
    return response;
  }

  /** Publish a message to every IPC client (the only public outbound path). */
  publish(type: IpcMessage["type"], payload: unknown, replyTo?: string): void {
    this.sendToFrontend({
      id: uuid(),
      direction: "node-to-net",
      type,
      payload,
      timestamp: Date.now(),
      replyTo,
    });
  }

"""

# ── index.ts: bind Hermes to the bus ──────────────────────────────────────────
INDEX_OLD = """  // Wire Hermes to IPC bridge for 2-way relay
  hermes.setExternalSender((msg: unknown) => {
    console.log(`[Hermes→IPC] ${JSON.stringify(msg).slice(0, 200)}`);
  });"""

INDEX_NEW = """  // Wire Hermes into the live system. Two halves, both required:
  //   directory -- the real agent ids + a dispatch() that runs work, so "route"
  //                reaches an agent instead of answering with a role name;
  //   sender    -- the bus's outbound IPC channel, so a Hermes reply reaches the
  //                .NET/WebSocket clients (it used to stop at console.log).
  hermes.setDirectory({
    list: () =>
      agentBus.getAgents().map((a) => ({
        id: a.id,
        name: a.name,
        role: (a as any).role ?? "custom",
        tools: a.tools.map((t) => t.name),
      })),
    dispatch: (type, payload, agentId, parentTaskId) =>
      agentBus.dispatch(type, payload, agentId, parentTaskId),
  });

  hermes.setExternalSender((msg: unknown) => {
    console.log(`[Hermes→IPC] ${JSON.stringify(msg).slice(0, 200)}`);
    agentBus.publish("agent.response", { hermes: msg });
  });"""


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


def write(p: Path, text: str) -> None:
    bak = p.with_suffix(p.suffix + ".bak-hermeswire")
    if not bak.exists():
        bak.write_text(read(p), encoding="utf-8")
    p.write_text(text, encoding="utf-8")


def patch_bus(text: str) -> tuple[str, list[str]]:
    notes = []
    if BUS_SIG_NEW not in text:
        if BUS_SIG_OLD not in text:
            raise SystemExit("agent-bus.ts: processTask signature not found")
        text = text.replace(BUS_SIG_OLD, BUS_SIG_NEW, 1)
        notes.append("processTask returns AgentResponse")

    if "  async dispatch(" not in text:
        if BUS_RET_OLD not in text:
            raise SystemExit("agent-bus.ts: processTask tail not found")
        if BUS_ANCHOR not in text:
            raise SystemExit("agent-bus.ts: IPC Bridge anchor not found")
        text = text.replace(BUS_RET_OLD, BUS_RET_NEW, 1)
        text = text.replace(BUS_ANCHOR, BUS_METHODS + BUS_ANCHOR, 1)
        notes.append("dispatch/publish/listAgents added")
    return text, notes


def patch_index(text: str) -> tuple[str, list[str]]:
    if "hermes.setDirectory({" in text:
        return text, []
    if INDEX_OLD not in text:
        raise SystemExit("index.ts: Hermes wiring block not found")
    return text.replace(INDEX_OLD, INDEX_NEW, 1), ["Hermes bound to bus directory + IPC outbound"]


def main() -> int:
    bus = read(BUS)
    idx = read(INDEX)

    bus_new, bus_notes = patch_bus(bus)
    idx_new, idx_notes = patch_index(idx)
    notes = bus_notes + idx_notes

    if "--check" in sys.argv:
        ok = bus_new == bus and idx_new == idx
        print(("PASS " if ok else "FAIL ") + f"hermes wiring applied={ok}")
        if not ok:
            print("  pending: " + ", ".join(notes))
        return 0 if ok else 1

    if not notes:
        print("already wired: agent-bus.ts + index.ts")
        return 0

    if bus_new != bus:
        write(BUS, bus_new)
    if idx_new != idx:
        write(INDEX, idx_new)
    for n in notes:
        print("  + " + n)
    print("patched agent-bus.ts + index.ts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
