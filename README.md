# markdown_to_flow

Turning FlowAI agents into portable, standard-format definitions — and back — proven end-to-end
against a real live agent.

**Start here:** [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) — what this is, what was proven,
and why it matters.

## What's in this repo

```
agents/Cisco/catalyst-center-health/         — worked example: a real FlowAI agent, reverse-engineered,
                                          rebuilt three independent ways, all three proven identical
agents/Cisco/catalyst-center-remediation/    — sibling agent, the only one with write access (gated on
                                          human approval) — live round-trip verified
agents/Cisco/catalyst-center-eox-security/   — sibling agent — live round-trip verified
agents/Linux/linux-diagnostics/        — read-only host health-check agent, converted from a
                                          non-MCP (native Ansible-playbook) source tool — diagnostics
                                          logic reconstructed from the original's own documented
                                          contract; comms/notification delivery deliberately dropped
template/                              — reusable template + step-by-step playbook for converting
                                          any other FlowAI agent the same way
EXECUTIVE_SUMMARY.md                   — the short version, for anyone who doesn't need the detail
```

## The core idea

An agent's *definition* — what it does, which tools it needs, how it decides things — doesn't
have to live only as platform-specific config. Written as a small set of standard files
(`AGENTS.md`, `SKILL.md`, an MCP server manifest, and a thin platform-specific translation layer),
the same definition can:

- Deploy and run on Itential FlowAI
- Be built and run by Claude Code, Codex, or any other MCP-capable AI tool — **with no Itential
  involved at all** — using the exact same tools
- Move between platforms without being rewritten from scratch each time

`agents/Cisco/catalyst-center-health/` proves this isn't theoretical: the same agent, same tools, same
live sandbox data, run three completely different ways, all three producing the identical correct
answer.

The other two agents in the same live "Cisco Catalyst Center" FlowAI project —
`agents/Cisco/catalyst-center-remediation/` (the only one with write access, gated on human approval)
and `agents/Cisco/catalyst-center-eox-security/` — are now portable too, each with a live round-trip
test against the real platform.

## Using this for another agent

See `template/CONVERT-AGENT-TO-PORTABLE.md`. It's written to be handed directly
to `itential-builder:flowagent` (or Claude Code) as instructions — point it at an existing agent
name/ID and it walks through pulling the live definition, classifying its tools, scaffolding the
folder, and verifying the round trip.

## Setup

```bash
cp .env.example .env   # .env is gitignored — real values never get committed
```

Every deployment recipe in this repo (`agents/Cisco/*/itential/agent.spec.md` Section 0) reads
its values from `.env` — fill these in once and every agent's recipe works as copy/paste. Nothing
in the spec files themselves is specific to any one Itential Platform, project, or Gateway; `.env`
is the only place that's true.

| Variable | What it is | How to find it |
|---|---|---|
| `PLATFORM_URL` | Your Itential Platform base URL | Whatever you use to reach the FlowAI UI |
| `AUTH_METHOD` | `oauth` (service account) or `password` (local login) | Ask your platform admin which your instance supports |
| `CLIENT_ID` / `CLIENT_SECRET` | An oauth `client_credentials` service account | Platform → Admin → Service Accounts (needs editor/owner role on the target project below) |
| `USERNAME` / `PASSWORD` | Only if `AUTH_METHOD=password` instead | Your own platform login |
| `PROJECT_ID` | The FlowAI project (namespace) you're deploying these agents into | Pick or create a project in the FlowAI UI, then `GET $PLATFORM_URL/agent-project-service/projects` to find its `_id` |
| `GATEWAY_CLUSTER` | The `cluster_id` of a Gateway connected to this platform | `GET $PLATFORM_URL/gateway_manager/v1/gateways` — pick one with `connection_status: connected` and a `groups` entry your service account belongs to |
| `CATALYST_CENTER_HOST` / `_USERNAME` / `_PASSWORD` / `_VERIFY_SSL` | Credentials for the actual Cisco Catalyst Center controller these agents read from | Your own Catalyst Center instance — use a least-privilege, read-only account (the remediation agent is the only one that writes, and only after human approval) |
| `CATALYST_CENTER_MCP_URL` | Where the `catalyst-center` MCP server is reachable once it's running | Default `http://host.docker.internal:7001/v1/mcp` works if you followed any agent's `mcp/INSTALL.md` as-is |

## Per-agent setup

The table above covers every variable in `.env` — shared across all three agents in this repo.
What's specific to each one (exact tool count, which wrapper services to build, any RBAC gotchas)
lives in that agent's own `README.md`, not here:

- [`agents/Cisco/catalyst-center-health/README.md`](agents/Cisco/catalyst-center-health/README.md) — read-only, 5 tools
- [`agents/Cisco/catalyst-center-remediation/README.md`](agents/Cisco/catalyst-center-remediation/README.md) — write access (gated), 7 tools
- [`agents/Cisco/catalyst-center-eox-security/README.md`](agents/Cisco/catalyst-center-eox-security/README.md) — read-only, up to 12 tools
- [`agents/Linux/linux-diagnostics/README.md`](agents/Linux/linux-diagnostics/README.md) — read-only, 1 tool, no `.env` variables of its own (needs its own SSH-reachable Ansible inventory instead)

Each follows the same shape: what you need → quick start → running it without Itential at all.
