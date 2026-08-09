# Cisco Catalyst Center Health Triage Agent — Setup & Quick Start

Reads Cisco Catalyst Center (DNAC) assurance data, flags devices below a health threshold, and
produces a per-site triage report. Strictly read-only. See `AGENTS.md` for the full plain-language
orientation, `itential/agent.spec.md` for the deployable FlowAI spec, and
`skills/catalyst-center-health-triage/SKILL.md` for the portable operating procedure this agent
(and any non-Itential MCP client) follows.

## What you need

Fill in this repo's root `.env` (copy from `.env.example` if you haven't already — see the root
`README.md` "Setup" section for what each variable is and how to find it).

| Variable | Needed for |
|---|---|
| `PLATFORM_URL`, `CLIENT_ID`/`CLIENT_SECRET` (or `USERNAME`/`PASSWORD`) | Deploying this agent to Itential — `itential/agent.spec.md` Section 0 |
| `PROJECT_ID` | Which FlowAI project this agent gets created in |
| `GATEWAY_CLUSTER` | Which Gateway's wrapper services this agent's 5 tools resolve to |
| `CATALYST_CENTER_HOST`/`_USERNAME`/`_PASSWORD`/`_VERIFY_SSL` | The real Catalyst Center controller the MCP server reads from |
| `CATALYST_CENTER_MCP_URL` | Where the MCP server is reachable once running (default works if you followed `mcp/INSTALL.md` as-is) |

This agent is entirely read-only — a least-privilege, read-only Catalyst Center account is enough.

## Quick start

1. Fill in `.env` (above).
2. Stand up the MCP server — `mcp/INSTALL.md` Steps 1–3. Shared across all three agents in this
   family (`../catalyst-center-remediation/`, `../catalyst-center-eox-security/`) if you're
   setting up more than one — no need to run three separate containers.
3. Build the Gateway wrapper services for this agent's 5 tools —
   `itential/agent.spec.md` Section 2's table + wrapper-build recipe (Section 2.1/2.2). Skip this
   if you only want to run the agent natively via MCP with no Itential involved (Step 5 below).
4. Deploy — run `itential/agent.spec.md` Section 0's recipe end to end.
5. Delete any test agent you created once you've confirmed it works (the recipe's last step).

## Without Itential

Point any MCP-capable client (Claude Code, Codex, Claude Desktop) at the MCP server from Step 2
above, then use `skills/catalyst-center-health-triage/SKILL.md` as the operating procedure. No
Gateway, no wrapper services, no Itential Platform involved — see `AGENTS.md` for details and
`tests/missions/` for expected input/output.
