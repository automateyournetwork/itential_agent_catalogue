# Portable FlowAI Agents — Executive Summary

**Date:** 2026-08-08
**Author:** John Capobianco, with Claude Code
**Platform tested:** `itential-se-poc-dev01.trial.itential.io`

## The question

Can a FlowAI agent be defined in a small set of markdown/JSON files — instead of only living as
platform-specific configuration — and still (a) deploy and run correctly on Itential, (b) be
buildable by any standard AI coding tool (Claude Code, Codex, others), and (c) run natively with
no Itential involvement at all, using the same tools?

## The answer: yes, proven end-to-end, not theoretical

We took a real, existing production-style FlowAI agent (**Cisco Catalyst Center Health Triage
Agent**, live on the platform), reverse-engineered it into a portable folder structure, then
rebuilt it forward three independent ways — and all three produced the identical, correct answer
against the same live sandbox data:

| Path | Runtime | Itential involved? | Result |
|---|---|---|---|
| Manual API/CLI reconstruction | `iagctl` + platform REST API | Yes (Gateway only) | `0 of 4 devices degraded` |
| `itential-builder:flowagent` skill, deployed live | FlowAI on the Platform | Yes (full stack) | `0 of 4 devices degraded` |
| Claude Code, native MCP, 3 rounds | Direct MCP tool calls | **No** | `0 of 4 devices degraded` |

Same 5 tools, same instructions, same live Cisco sandbox, three completely different execution
environments, one answer. That's the proof: the agent's *definition* is portable even though
today's *tools* (Itential FlowAI or otherwise) aren't yet built to read it directly.

## What we built

`agents/Cisco/catalyst-center-health/` — a standard folder per agent:

```
AGENTS.md              — orientation, read natively by Codex/Cursor/etc.
skills/*/SKILL.md       — the operating procedure (Anthropic's open Agent Skill format)
mcp/servers.json        — the MCP server definition, in Claude Code's own .mcp.json shape
itential/agent.spec.md  — the FlowAI-specific translation layer + verified deploy recipe
tests/                  — real captured input/output fixtures and full test reports
```

Everything outside `itential/` is Itential-agnostic by design — any MCP-capable AI tool can pick
up the same folder and run the same agent with zero platform-specific code.

## Key findings

1. **`itential-builder:flowagent`'s documented API is stale for at least this platform build.**
   Every `/flowai/*` endpoint in its `SKILL.md` (create agent, discover tools, list providers)
   404s. This platform runs a newer surface: `agent-project-service`, `agent-session-manager`,
   `model-registry-service`, `/tools`. **Fixed** — patched the skill with a compatibility note
   and full endpoint mapping table (see "What we fixed," below).

2. **Gateway does not automatically expose registered MCP server tools to FlowAI.** Registering
   an MCP server on Gateway (`iagctl mcp server add`) makes it callable via `iagctl mcp tool
   call`, but FlowAI's tool discovery does not pick those tools up on its own. A thin
   IAG `python-script` wrapper per MCP tool is required — this is exactly the pattern the
   original production agent already used, now independently re-derived, documented, and
   rebuilt from scratch as working, tested code.

3. **Two real permission gotchas, worth broader awareness:** FlowAI agents are ACL'd
   *per-project* independent of any platform-wide role (viewer vs. editor/owner matters, and a
   platform role grant alone doesn't add project membership); Gateway access is separately ACL'd
   by group membership, and a connected-but-inaccessible Gateway looks identical to a
   disconnected one until you check `/gateway_manager/v1/gateways` directly.

4. **Skill and MCP server edits don't take effect mid-session.** Both are loaded once per Claude
   Code session; on-disk changes require a session reload to take effect. Confirmed for both
   independently — worth knowing before assuming a fix "didn't work."

## What we fixed (already applied, not a recommendation to do later)

- `agents/Cisco/catalyst-center-health/itential/agent.spec.md` — added a self-sufficient, verified
  request recipe (Section 0) so this spec works regardless of the skill's own doc state.
- `itential-builder:flowagent`'s `SKILL.md` (both the marketplace source copy and the actual
  versioned cache copy the `Skill` tool loads at runtime — these are different files) — added a
  platform-compatibility section with the real endpoint mapping.

## Extending to the rest of the agent family (2026-08-08)

The "Cisco Catalyst Center" FlowAI project has two sibling agents beyond the health-triage one
above: a **Remediation Agent** (the only one of the three with write access, gated on explicit
human approval given in a later conversation turn) and an **EoX & Security Advisories** agent.
Both were converted to the same portable shape and verified with a live round-trip (create a
test agent from the spec → run with no arguments → confirm the result → delete the test agent).

The remediation agent's round-trip proved the safety gate holds: against the one condition the
live sandbox could produce (nothing eligible for automated fixing), the agent correctly explained
why and never attempted a write.

The EoX agent's round-trip ran cleanly end-to-end against live data, and also demonstrated the
same honesty discipline under a real permission gap: two of its APIs returned a 403 for this
service account's role, and the agent reported that gap as a finding rather than silently
returning a false "0 advisories, 0 bugs."

## Recommendation

Formalize this folder convention as the standard shape for any new agent going forward, and treat
"can this agent run outside Itential, unmodified, given just its tools?" as a design question
worth asking at build time — not because Itential should be bypassed, but because it's a forcing
function for clean tool boundaries and makes every agent easier to test, demo, and debug in
isolation. A generalized, reusable template and conversion playbook for turning any existing
FlowAI agent into this shape is included in this package (`template/`) for the
rest of the team to use once this repo is on GitHub.
