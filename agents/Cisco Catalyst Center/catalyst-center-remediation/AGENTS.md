# Catalyst Center Remediation Agent

Reverse-engineered from a live FlowAI agent (`8f36deb0-493a-4c7c-951f-7a457eb6aeb3`,
"Cisco Catalyst Center Remediation Agent (Speculative)", project "Cisco Catalyst Center" on the
Itential Platform). This file is plain context for any coding agent (Claude Code, Codex, Cursor,
etc.) working in this folder — it does not require Itential to be present to be useful.

## What this agent does

Finds Cisco Catalyst Center (DNAC) devices that are out of compliance (config drift, EoX, image,
PSIRT, network settings, etc.), explains exactly what's wrong with each one, and — only for the
one compliance type it can actually fix (`RUNNING_CONFIG` drift) — proposes a remediation. It
**never applies a fix in the same turn it proposes one**. A human has to come back in a
*subsequent* message and explicitly approve, naming the same device(s) proposed, before it will
call the one tool that writes to the network. Everything else it does is read-only discovery and
reporting.

This is the one agent in the family with real write access (`api_complianceRemediation` can push
a config fix). The human-approval gate is the entire safety model — there is no other check
standing between "propose" and "change the network."

## Source of truth for behavior

The actual system prompt shipped with the live agent is at `itential/agent.spec.md` (Section 3,
"Instructions") — treat that as canonical. This file is orientation, not the prompt itself.

## Tools this agent needs

| Tool | Purpose |
|---|---|
| `api_retrieveNetworkDevices` | Resolve a device name/IP to its UUID |
| `api_getComplianceStatusCount` | Global compliant/non-compliant totals (no type specified) |
| `api_getComplianceStatus` | High-level per-device compliance status records |
| `api_getComplianceDetailCount` | Non-compliant totals for one specific compliance type |
| `api_getComplianceDetail` | Which specific devices are non-compliant, and for what |
| `api_complianceDetailsOfDevice` | Full violation breakdown for one device (severity, whether remediation is supported) |
| `api_complianceRemediation` | **Write.** Applies a fix — `RUNNING_CONFIG` drift only. Everything else this agent flags is report-only. |

All seven exist today as MCP tools on Cisco's official Catalyst Center MCP server
(`cisco-en-programmability/catc-mcp-oss`) — the same server `catalyst-center-health` uses, just a
different tool subset. See `mcp/servers.json` and `mcp/INSTALL.md`.

## Testing without Itential

1. Bring up the MCP server per `mcp/INSTALL.md` (same container as `catalyst-center-health`, just
   confirm the compliance tools are in your curated bundle).
2. Point any MCP client (Claude Code via `.mcp.json`, Claude Desktop, `iagctl mcp tool call`) at it.
3. Use `skills/catalyst-center-remediation/SKILL.md` as the operating procedure — it encodes the
   same discovery → detail → propose → wait-for-approval → remediate flow as the live agent.
4. Sample expected input/output pairs are in `tests/missions/`.

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration and a verified, self-sufficient
deploy recipe (Section 0). A full live round-trip (create → run no-args → confirm it stops at
proposal → delete) is documented in `tests/itential-builder-flowagent-test.md`.
