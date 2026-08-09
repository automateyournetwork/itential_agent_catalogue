# {{AGENT_NAME}} — Setup & Quick Start

{{One sentence: what this agent does.}} See `AGENTS.md` for the full plain-language orientation,
`itential/agent.spec.md` for the deployable FlowAI spec, and `skills/{{SKILL_NAME}}/SKILL.md` for
the portable operating procedure this agent (and any non-Itential MCP client) follows.

## What you need

Fill in this repo's root `.env` (copy from `.env.example` if you haven't already — see the root
`README.md` "Setup" section for the shared variables every agent in this repo needs:
`PLATFORM_URL`, auth, `PROJECT_ID`, `GATEWAY_CLUSTER`).

{{If this agent's MCP server needs its own credentials beyond the shared ones (a controller
host/username/password, an API key, etc.), list them here and confirm they're also documented in
the root `.env.example` — don't introduce an undocumented variable.}}

| Variable | Needed for |
|---|---|
| `PLATFORM_URL`, `CLIENT_ID`/`CLIENT_SECRET` (or `USERNAME`/`PASSWORD`) | Deploying this agent to Itential — `itential/agent.spec.md` Section 0 |
| `PROJECT_ID` | Which FlowAI project this agent gets created in |
| `GATEWAY_CLUSTER` | Which Gateway's wrapper services this agent's tools resolve to |
| {{agent-specific vars, if any}} | {{what they're for}} |

## Quick start

1. Fill in `.env` (above).
2. Stand up the MCP server this agent needs — `mcp/INSTALL.md` Steps 1–3.
3. Build the Gateway wrapper services for this agent's tools — `itential/agent.spec.md` Section
   2's tool table + wrapper-build recipe. Skip this if you only want to run the agent natively via
   MCP with no Itential involved (see `AGENTS.md` "Testing without Itential").
4. Deploy — run `itential/agent.spec.md` Section 0's recipe end to end.
5. Delete any test agent you created once you've confirmed it works (the recipe's last step).

## Without Itential

Point any MCP-capable client (Claude Code, Codex, Claude Desktop) at the MCP server from Step 2
above, then use `skills/{{SKILL_NAME}}/SKILL.md` as the operating procedure. No Gateway, no
wrapper services, no Itential Platform involved — see `AGENTS.md` for details and
`tests/missions/` for expected input/output.
