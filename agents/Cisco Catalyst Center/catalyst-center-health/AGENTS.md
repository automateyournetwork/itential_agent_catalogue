# Catalyst Center Health Triage Agent

Reverse-engineered from a live FlowAI agent (`cb7448c6-0935-4fc4-b951-5d08fbde53cf`, project
"Cisco Catalyst Center" on the Itential Platform). This file is plain context for any coding
agent (Claude Code, Codex, Cursor, etc.) working in this folder — it does not require Itential
to be present to be useful.

## What this agent does

Reads Cisco Catalyst Center (DNAC) assurance data, flags devices below a health threshold, and
produces a per-site triage report. **Strictly read-only** — never calls a mutating operation,
even if one is reachable through the underlying tool surface.

Health threshold: a device is "degraded" if `overallHealth < 7` (0–10 scale) OR it has one or
more open issues.

## Source of truth for behavior

The actual system prompt shipped with the live agent is at `itential/agent.spec.md` (section
"Instructions") — treat that as canonical. This file is orientation, not the prompt itself.

## Tools this agent needs

Five read-only operations against a Catalyst Center controller:

| Tool | Purpose |
|---|---|
| `api_devices` | DNA Assurance device health — primary data source (`overallHealth`, `issueCount`, site) |
| `api_retrieveNetworkDevices` | Basic inventory — role, family, reachability, management IP |
| `api_getDeviceSummary` | Per-device drill-down when triaging a specific flagged device |
| `api_getSites` | Resolve a raw `siteId` into a readable `nameHierarchy` |
| `api_getSiteAssignedNetworkDevice` | Fallback site resolution when `api_getSites` doesn't resolve it |

All five exist today as MCP tools on Cisco's official Catalyst Center MCP server
(`cisco-en-programmability/catc-mcp-oss`) — see `mcp/servers.json` for the exact server
definition and `mcp/INSTALL.md` to run it with zero Itential involvement.

## Testing without Itential

1. Bring up the MCP server per `mcp/INSTALL.md`.
2. Point any MCP client (Claude Code via `.mcp.json`, Claude Desktop, `iagctl mcp tool call`) at it.
3. Use `skills/catalyst-center-health-triage/SKILL.md` as the operating procedure — it encodes
   the same threshold logic and the same "don't report absence as fact" discipline as the live
   agent's instructions, generalized as reusable guidance.
4. Sample expected input/output pairs are in `tests/missions/`.

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration: provider/model, the exact
tool `referenceId` format Itential expects (`gatewayService:<clusterId>:python-script:<name>`),
and why a thin per-tool wrapper service is required (native MCP tools do not auto-surface to
FlowAI's tool discovery — confirmed empirically, see that file's "Known limitation" section).
