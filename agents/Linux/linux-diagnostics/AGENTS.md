# Linux Diagnostics

Reverse-engineered from a live FlowAI agent ("Linux Diagnostics", `3d3c8bfa-97ac-4ba9-b2fe-ce51c119f759`,
project "Linux Operations") on an Itential Platform trial instance. This file is plain context for
any coding agent (Claude Code, Codex, Cursor, etc.) working in this folder — it does not require
Itential to be present to be useful.

## What this agent does

Given a target host inventory, it runs a health-check sweep (disk, memory, CPU, swap, inodes,
expected services, failed systemd units, OOM kill events, zombie processes), applies a fixed
threshold table to classify each host OK/WARNING/CRITICAL, and returns a report naming which hosts
need attention and why. It's a read-only diagnostics tool, not a remediation tool — it never
changes anything on the hosts it inspects.

**Scoped down from the original.** The live agent this came from also delegated report delivery
(email + Slack) to a separate "Comms Agent" that called two Itential-native workflows. That's
deliberately not part of this portable version — see `itential/agent.spec.md` Provenance for why.
This agent just returns the report; routing it anywhere is the caller's job.

## Source of truth for behavior

The actual system prompt is at `itential/agent.spec.md` (Section 3, "Instructions") — treat that
as canonical, and functionally identical to `skills/linux-diagnostics/SKILL.md`.

## Tools this agent needs

| Tool | Purpose |
|---|---|
| `run_diagnostics` | The only tool. Takes `inventory` (a group name or host list), returns raw per-host metrics. MCP-backed by `mcp/server.py` — this repo's own implementation, not a wrapped third-party server (see below). |

**Important:** `mcp/server.py` and `ansible/linux_diagnostics.yml` are a **reconstruction**, built
from the original agent's own documented metric/threshold contract — not the original production
playbook, which required Gateway-admin credentials this conversion didn't have access to. It's
functionally equivalent by design, but hasn't been diffed against the real source. See
`itential/agent.spec.md` Provenance for the live evidence (a real, partially-failed test run
against the actual production tool) this reconstruction is grounded in.

## Testing without Itential

1. Stand up the MCP server — `mcp/INSTALL.md` (needs Python 3.10+, `ansible-core`, and SSH access
   to whatever Linux hosts you point it at).
2. Point any MCP client (Claude Code via `.mcp.json`, Claude Desktop, `iagctl mcp tool call`) at it.
3. Use `skills/linux-diagnostics/SKILL.md` as the operating procedure.
4. Sample expected input/output shape is in `tests/missions/`.

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration — provider/model, the exact tool
`referenceId` format, and a self-sufficient deploy recipe (Section 0).
