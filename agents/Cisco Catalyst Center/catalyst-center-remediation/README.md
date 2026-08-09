# Cisco Catalyst Center Remediation Agent — Setup & Quick Start

Finds Catalyst Center devices out of compliance, explains what's wrong, and proposes a fix for
the one issue type it can actually remediate (`RUNNING_CONFIG` drift) — but never applies it
without a human explicitly approving in a later conversation turn. This is the only agent in the
family with write access. See `AGENTS.md` for the full plain-language orientation,
`itential/agent.spec.md` for the deployable FlowAI spec, and
`skills/catalyst-center-remediation/SKILL.md` for the portable operating procedure this agent
(and any non-Itential MCP client) follows.

## What you need

Fill in this repo's root `.env` (copy from `.env.example` if you haven't already — see the root
`README.md` "Setup" section for what each variable is and how to find it).

| Variable | Needed for |
|---|---|
| `PLATFORM_URL`, `CLIENT_ID`/`CLIENT_SECRET` (or `USERNAME`/`PASSWORD`) | Deploying this agent to Itential — `itential/agent.spec.md` Section 0 |
| `PROJECT_ID` | Which FlowAI project this agent gets created in |
| `GATEWAY_CLUSTER` | Which Gateway's wrapper services this agent's 7 tools resolve to |
| `CATALYST_CENTER_HOST`/`_USERNAME`/`_PASSWORD`/`_VERIFY_SSL` | The real Catalyst Center controller the MCP server reads from (and, for this agent, can write to) |
| `CATALYST_CENTER_MCP_URL` | Where the MCP server is reachable once running (default works if you followed `mcp/INSTALL.md` as-is) |

**This agent has real write access** (one of its 7 tools can push a config fix). Use a Catalyst
Center account scoped to only what compliance remediation needs — not a full admin account — and
never deploy this against a production controller without a human genuinely reviewing every
proposal before approving.

## Quick start

1. Fill in `.env` (above).
2. Stand up the MCP server — `mcp/INSTALL.md` Steps 1–3. Shared across all three agents in this
   family (`../catalyst-center-health/`, `../catalyst-center-eox-security/`) if you're setting up
   more than one — no need to run three separate containers.
3. Build the Gateway wrapper services for this agent's 7 tools —
   `itential/agent.spec.md` Section 2's table + wrapper-build recipe (Section 2.1). Skip this if
   you only want to run the agent natively via MCP with no Itential involved (Step 5 below).
4. Deploy — run `itential/agent.spec.md` Section 0's recipe end to end.
5. Delete any test agent you created once you've confirmed it works (the recipe's last step).

## Without Itential

Point any MCP-capable client (Claude Code, Codex, Claude Desktop) at the MCP server from Step 2
above, then use `skills/catalyst-center-remediation/SKILL.md` as the operating procedure. The
same human-approval gate applies regardless of runtime — never let anything call the remediation
tool without a proposal shown first and explicit approval after. See `AGENTS.md` for details and
`tests/missions/` for expected input/output.
