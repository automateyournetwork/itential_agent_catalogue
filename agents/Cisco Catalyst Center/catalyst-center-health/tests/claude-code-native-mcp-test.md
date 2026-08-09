# Test: Claude Code native, no Itential involved

**Method:** `.mcp.json` added at project root pointing at the live `catalyst-center` MCP server
(`http://localhost:7001/v1/mcp`, the exact same `catc-mcp-oss` container the FlowAI agent used).
Confirmed a **fresh Claude Code session is required** to pick up a new `.mcp.json` — same
session-caching behavior found earlier for skills, now confirmed for MCP servers too. After
reload, `mcp__catalyst-center__*` tools appeared natively (520 tools from the server's default
bundle; loaded schemas for the 5 this skill needs via `ToolSearch`).

Then loaded `skills/catalyst-center-health-triage/SKILL.md` as the operating procedure and ran
its Step 1 (`call api_devices for health scores`) three independent times, natively — no
`iagctl`, no curl, no Itential API of any kind in this path.

## 3 rounds

| Round | Tool call | Result |
|---|---|---|
| 1 | `mcp__catalyst-center__api_devices()` | 4 devices, all `overallHealth: 10`, `issueCount: 0` |
| 2 | `mcp__catalyst-center__api_devices()` | identical |
| 3 | `mcp__catalyst-center__api_devices()` | identical |

Identical across all 3 rounds — expected, since this is a read-only query against an unchanged
sandbox with no state to vary between calls (unlike the FlowAI runs, this isn't testing
LLM-driven tool selection, just direct tool invocation + the skill's own formatting rules).

## Report, per SKILL.md's Output format section

```
0 of 4 devices degraded.

sw1 (10.10.20.175) — 10/10, 0 issues, REACHABLE
sw2 (10.10.20.176) — 10/10, 0 issues, REACHABLE
sw3 (10.10.20.177) — 10/10, 0 issues, REACHABLE
sw4 (10.10.20.178) — 10/10, 0 issues, REACHABLE

Needs attention first: none.
```

Matches `no-args-happy-path.json` and both FlowAI-platform runs exactly.

## What this proves

The three-way comparison is now complete for the happy path:

| Path | Runtime | Result |
|---|---|---|
| Manual (this project, early exercise) | `iagctl mcp tool call` | `0 of 4 degraded` |
| FlowAI, Itential Platform (2 runs via `itential-builder:flowagent`) | Gateway-wrapped service, LLM-driven | `0 of 4 degraded` |
| **Claude Code native (this test, 3 rounds)** | **Direct MCP tool call, no Itential** | **`0 of 4 degraded`** |

Same tools, same sandbox, same skill instructions, three completely different runtimes, identical
correct answer. This is the direct proof of the portability claim from the start of this
exercise: the `agents/Cisco/catalyst-center-health/` folder is not Itential-specific — Itential is one
of three ways to run it, and the one that needed the most extra plumbing (Gateway wrapper
services), not the only one that works.

## Known limitation, confirmed twice now

Neither a skill file edit nor a new `.mcp.json` takes effect within an already-running Claude
Code session — both require a fresh session to load. Anyone iterating on either file mid-session
needs to reload, not just re-invoke.
