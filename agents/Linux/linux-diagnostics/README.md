# Linux Diagnostics — Setup & Quick Start

Runs a read-only Linux host health-check sweep and returns an OK/WARNING/CRITICAL report. See
`AGENTS.md` for the full plain-language orientation, `itential/agent.spec.md` for the deployable
FlowAI spec, and `skills/linux-diagnostics/SKILL.md` for the portable operating procedure this
agent (and any non-Itential MCP client) follows.

Unlike the Cisco agents in this repo, this one has no email/Slack delivery step — it only returns
the report. See `itential/agent.spec.md` Provenance for why that was dropped from the original.

## What you need

Fill in this repo's root `.env` (copy from `.env.example` if you haven't already — see the root
`README.md` "Setup" section for the shared variables every agent in this repo needs:
`PLATFORM_URL`, auth, `PROJECT_ID`, `GATEWAY_CLUSTER`).

This agent has no controller-specific credentials of its own (unlike the Cisco agents' Catalyst
Center host/user/pass) — its only external dependency is SSH access from wherever the
`linux-diagnostics` MCP server runs to whatever Linux hosts you point it at.

| Variable | Needed for |
|---|---|
| `PLATFORM_URL`, `CLIENT_ID`/`CLIENT_SECRET` (or `USERNAME`/`PASSWORD`) | Deploying this agent to Itential — `itential/agent.spec.md` Section 0 |
| `PROJECT_ID` | Which FlowAI project this agent gets created in |
| `GATEWAY_CLUSTER` | Which Gateway's wrapper service this agent's tool resolves to |
| — | No agent-specific `.env` variables — SSH/inventory config lives in your own Ansible inventory file, see `mcp/INSTALL.md` |

## Quick start

1. Fill in `.env` (above).
2. Set up an Ansible inventory covering the hosts you want diagnostics on — `mcp/INSTALL.md` Step 2.
3. Stand up the MCP server — `mcp/INSTALL.md` Steps 1–3.
4. Build the Gateway wrapper service for this agent's tool — `itential/agent.spec.md` Section 2's
   tool table + wrapper-build recipe. Skip this if you only want to run the agent natively via MCP
   with no Itential involved (see `AGENTS.md` "Testing without Itential").
5. Deploy — run `itential/agent.spec.md` Section 0's recipe end to end.
6. Delete any test agent you created once you've confirmed it works (the recipe's last step).

## Without Itential

Point any MCP-capable client (Claude Code, Codex, Claude Desktop) at the MCP server from Step 3
above, then use `skills/linux-diagnostics/SKILL.md` as the operating procedure. No Gateway, no
wrapper services, no Itential Platform involved — see `AGENTS.md` for details and
`tests/missions/` for the expected input/output shape.

## A note on the diagnostics logic itself

`ansible/linux_diagnostics.yml` and `mcp/server.py` are a **reconstruction** of the original
production playbook's behavior (same metrics, same thresholds, same output contract), not the
verbatim original — see `itential/agent.spec.md` Provenance for exactly what evidence this is
based on and how to swap in the real playbook if you have Gateway-admin access to pull it.
