# Cisco Catalyst Center EoX & Security Advisories Agent — Setup & Quick Start

Produces a hardware/software lifecycle (EoX), PSIRT security advisory, and network-bug risk
exposure report for Catalyst Center devices — named devices with real reasons, risk-tiered
Critical/High/Medium/Low. Strictly read-only. See `AGENTS.md` for the full plain-language
orientation, `itential/agent.spec.md` for the deployable FlowAI spec, and
`skills/catalyst-center-eox-security/SKILL.md` for the portable operating procedure this agent
(and any non-Itential MCP client) follows.

## What you need

Fill in this repo's root `.env` (copy from `.env.example` if you haven't already — see the root
`README.md` "Setup" section for what each variable is and how to find it).

| Variable | Needed for |
|---|---|
| `PLATFORM_URL`, `CLIENT_ID`/`CLIENT_SECRET` (or `USERNAME`/`PASSWORD`) | Deploying this agent to Itential — `itential/agent.spec.md` Section 0 |
| `PROJECT_ID` | Which FlowAI project this agent gets created in |
| `GATEWAY_CLUSTER` | Which Gateway's wrapper services this agent's tools resolve to (8 directed by the instructions, up to 12 if you build the unused ones too — see Section 2.1) |
| `CATALYST_CENTER_HOST`/`_USERNAME`/`_PASSWORD`/`_VERIFY_SSL` | The real Catalyst Center controller the MCP server reads from |
| `CATALYST_CENTER_MCP_URL` | Where the MCP server is reachable once running (default works if you followed `mcp/INSTALL.md` as-is) |

This agent is entirely read-only. Its Catalyst Center account needs read RBAC on the PSIRT/bug-
scanner APIs specifically, separate from general read access — a real, fairly common gap; see
the example run in `itential/agent.spec.md`'s "Provenance" section for what that looks like when
missing (the agent reports it as a finding, not a false "clean fleet").

## Quick start

1. Fill in `.env` (above).
2. Stand up the MCP server — `mcp/INSTALL.md` Steps 1–3. Shared across all three agents in this
   family (`../catalyst-center-health/`, `../catalyst-center-remediation/`) if you're setting up
   more than one — no need to run three separate containers.
3. Build the Gateway wrapper services for this agent's tools — `itential/agent.spec.md` Section
   2's table + wrapper-build recipe (Section 2.2). You only need the 8 marked "Yes" in that
   table unless you want the 4 currently-unused ones too. Skip this entirely if you only want to
   run the agent natively via MCP with no Itential involved (Step 5 below).
4. Deploy — run `itential/agent.spec.md` Section 0's recipe end to end.
5. Delete any test agent you created once you've confirmed it works (the recipe's last step).

## Without Itential

Point any MCP-capable client (Claude Code, Codex, Claude Desktop) at the MCP server from Step 2
above, then use `skills/catalyst-center-eox-security/SKILL.md` as the operating procedure. No
Gateway, no wrapper services, no Itential Platform involved — see `AGENTS.md` for details and
`tests/missions/` for expected input/output.
