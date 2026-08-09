# Catalyst Center EoX & Security Advisory Risk Agent

Reverse-engineered from a live FlowAI agent (`a2c134f8-d22c-4305-b908-425e6c7ecfa8`,
"Cisco Catalyst Center EoX And Security Advisories", project "Cisco Catalyst Center" on the
Itential Platform). This file is plain context for any coding agent (Claude Code, Codex, Cursor,
etc.) working in this folder — it does not require Itential to be present to be useful.

## What this agent does

Reads Cisco Catalyst Center (DNAC) hardware/software lifecycle, PSIRT security advisory, and
detected network-bug data, and produces a per-device risk exposure report meant to drive refresh
budget decisions and audit/compliance conversations. It names real devices with real reasons —
EoX lifecycle dates, advisory/CVE IDs, bug IDs — not vague totals, and assigns each device a
Critical/High/Medium/Low risk tier with the reasoning stated, not just the label. **Strictly
read-only** — there is no remediation tool for any of these categories, and it never suggests
configuration changes.

## Source of truth for behavior

The actual system prompt shipped with the live agent is at `itential/agent.spec.md` (Section 3,
"Instructions") — treat that as canonical. This file is orientation, not the prompt itself.

## Tools this agent needs

| Tool | Purpose |
|---|---|
| `api_getEoXSummary` | Network-wide EoX aggregate — no parameters, headline numbers |
| `api_getEoXStatusForAllDevices` | Per-device EoX alert list across the network — bulk discovery pass |
| `api_getEoXDetailsPerDevice` | Deep detail for one device — actual lifecycle dates, bulletin info |
| `api_getSecurityAdvisoryNetworkDevices` | Devices affected by PSIRT advisories/CVEs |
| `api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices` | Network-wide headline count of advisory-affected devices |
| `api_getNetworkBugs` | Detected network bugs currently affecting devices (pass `deviceCount: 0`) |
| `api_getCountOfNetworkBugDevices` | Headline count of devices with ≥1 detected bug (pass `bugCount: 0`) |
| `api_retrieveNetworkDevices` | Resolve a raw `deviceId` to a name/management IP — never show a raw UUID in a report |

Four additional tools are bound to the live agent but never referenced by its instructions
(`api_getSecurityAdvisoryNetworkDevicesForTheSecurityAdvisory`,
`api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevice` [singular-device variant],
`api_getNetworkBugsResultsTrendOverTime`, `api_retrieveNetworkDeviceProductName`) — see
`itential/agent.spec.md` Section 2 for the full list; they're included in `mcp/servers.json`'s
curated set for completeness but the skill doesn't currently direct their use.

All exist today as MCP tools on Cisco's official Catalyst Center MCP server
(`cisco-en-programmability/catc-mcp-oss`) — the same server `catalyst-center-health` and
`catalyst-center-remediation` use, just a different tool subset. See `mcp/servers.json` and
`mcp/INSTALL.md`.

## Testing without Itential

1. Bring up the MCP server per `mcp/INSTALL.md` (same container as the sibling agents — confirm
   the EoX/advisory/bug tools are in your curated bundle).
2. Point any MCP client (Claude Code via `.mcp.json`, Claude Desktop, `iagctl mcp tool call`) at it.
3. Use `skills/catalyst-center-eox-security/SKILL.md` as the operating procedure.
4. Sample expected input/output pairs are in `tests/missions/`.

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration and a verified deploy recipe
(Section 0). A full live round-trip is documented in `tests/itential-builder-flowagent-test.md`.
