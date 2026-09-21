# Jev Testing — Reconfig Proposer / Pusher — FlowAI Agent Spec

Two FlowAI agents living in the **Jev Testing** project
(`b9b11d73-d94e-4efa-9e11-6260400975db`), built to be wrapped in an
Operations Manager workflow with a human-approval gate in between them
(not built yet — see "Next" at the end). Targets the `agent-project-service`
/ `agent-session-manager` / `model-registry-service` / `/tools` API surface,
same as `../../CiscoAntares/antares-vuln-scanner/itential/agent.spec.md`.

**Why two agents instead of one:** tool access = blast radius. The Proposer
has zero tools capable of changing a device — it is structurally incapable
of pushing configuration, not just prompt-discouraged from it. The Pusher
only exists to push an already-approved proposal and can't run at all until
a human clicks Approve in Work Center (once the workflow wrapping these
agents is built). See `../../CiscoAntares/antares-vuln-scanner/AGENTS.md`
"Safety design" for the same reasoning applied elsewhere in this repo.

**Why both raw-state-passthrough tools (`reconfig-submit-proposal`,
`reconfig-submit-push-result`) require `current_state`/`post_state`
alongside the agent's own proposal/results:** an agent's own prose is not
safe to trust for structured downstream use (same lesson as
`extract_agent_tool_result.py`'s docstring). Jev's pre/post validation and
the human reviewer both need the actual pyATS tool output, not the model's
paraphrase of it.

---

## 0. Deployment recipe (what was actually run, 2026-09-21)

```bash
set -a; source .env; set +a
TOKEN=$(curl -s -X POST "$PLATFORM_URL/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "client_id=$CLIENT_ID" --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode "grant_type=client_credentials" | jq -r '.access_token')

# 1. pyATS MCP testbed already pointed at DevNet Sandbox (10.10.20.171-174) --
#    see ../../../../.claude memory reference-pyats-mcp-testbed. Requires the
#    "DevNet CML" AnyConnect VPN connected locally.

# 2. Register the repo + 2 submit-tool services on the Gateway (reuses the
#    typesafe-jev repository registered for ../jev-tool/ -- same GitHub repo)
iagctl create decorator reconfig-submit-proposal --schema @decorators/reconfig-submit-proposal.json
iagctl create decorator reconfig-submit-push-result --schema @decorators/reconfig-submit-push-result.json
iagctl create service python-script reconfig-submit-proposal \
  --repository typesafe-jev \
  --filename "agents/TypeSafeJev/jev-testing-reconfig/tools/submit_proposal.py" \
  --decorator reconfig-submit-proposal
iagctl create service python-script reconfig-submit-push-result \
  --repository typesafe-jev \
  --filename "agents/TypeSafeJev/jev-testing-reconfig/tools/submit_push_result.py" \
  --decorator reconfig-submit-push-result

# 3. Activate on /tools
curl -s -X POST "$PLATFORM_URL/tools/discover" -H "Authorization: Bearer $TOKEN"

# 4. Create the Jev Testing project
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Jev Testing", "description": "..."}'
# -> _id: b9b11d73-d94e-4efa-9e11-6260400975db

# 5. Create both agents (payloads = Section 1+2/1+3 of this doc, saved as
#    proposer_payload.json / pusher_payload.json in this same directory)
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects/b9b11d73-d94e-4efa-9e11-6260400975db/agents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @proposer_payload.json
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects/b9b11d73-d94e-4efa-9e11-6260400975db/agents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @pusher_payload.json

# 6. Run the Proposer (no inputs needed)
curl -s -X POST "$PLATFORM_URL/agent-session-manager/sessions/run-agent" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"agent": "<proposer-id>", "inputs": {},
       "terminationCallbackSignature": {"location":"none","serviceName":"none","methodName":"none","identifier":"none"}}'

# 7. Run the Pusher (after human approval, once the workflow exists) with:
#    {"agent": "<pusher-id>", "inputs": {"approved_devices": "<the Proposer's own devices JSON, unchanged>"}, ...}
```

**Preconditions:** DevNet CML VPN connected (pyATS reachability); Gateway
cluster `john_capo_cluster` connected; TypeSafe `typesafe-jev_evaluate` tool
already registered (see `../jev-tool/README.md`) for the workflow's Jev
pre/post-check steps (not called by either agent directly — that's a
workflow-level `runService` task, not an agent tool, so a confused model
can't skip it or call it early).

---

## 1. Overview — shared

| Field | Value |
|---|---|
| Project (namespace) | `Jev Testing` (`b9b11d73-d94e-4efa-9e11-6260400975db`) |
| LLM provider profile | `anthropic-selab-gw`, model `claude-sonnet-5` (`ee6592c1-4c65-4132-ad0a-a1ed1dfe90f5`) — note this profile's own `gatewayCluster` is `selab-iag5-standalone` (just relays the Anthropic API call outbound); the agents' **tools** all reference `john_capo_cluster` instead (where pyATS/Jev actually live) — confirmed these two clusters can be mixed freely on one agent, same as the existing `CWE Finder (Antares-1B)` agent in this same platform instance does (Ollama profile + `john_capo_cluster` tools). |
| Target devices | R1, R2 (IOS-XE routers), SW1, SW2 (IOS-XE switches) — Cisco DevNet Sandbox, `10.10.20.171-174`, CSR1kv |

## 2. Reconfig Proposer

| # | referenceId | Purpose |
|---|---|---|
| 1 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_device_health` | current device health/state |
| 2 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_show_running_config` | current full running-config |
| 3 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_get_neighbors` | real CDP/LLDP topology, don't guess cabling |
| 4 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_learn_feature` | structured feature snapshots if needed |
| 5 | `gatewayService:john_capo_cluster:python-script:reconfig-submit-proposal` | terminate: submit proposal (never pushes) |

Input schema: none required (`{"type":"object","additionalProperties":false,"required":[],"properties":{}}`).
Full instructions: see `proposer_payload.json`'s `instructions` field (the
target design translated from the user's own requirements — RoS, VLANs
10/20 + 30/40, Rapid-PVST+ L2 best practices, R1-R2 /31, OSPF underlay +
iBGP overlay, CDP everywhere except the management interface).

Agent id (this deployment): `0d1c5fee-cbbc-4d8d-abd0-0b4b8b315379`

## 3. Reconfig Pusher

| # | referenceId | Purpose |
|---|---|---|
| 1 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_configure_with_diff` | push + diff, keeps rollback snapshot |
| 2 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_rollback_config` | restore pre-change state on a bad diff |
| 3 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_device_health` | resample after push |
| 4 | `gatewayService:john_capo_cluster:python-script:pyats_pyats_get_neighbors` | resample CDP/LLDP after push |
| 5 | `gatewayService:john_capo_cluster:python-script:reconfig-submit-push-result` | terminate: submit real push results |

Input schema: `{"approved_devices": string}` (required) — the Proposer's own
`devices` JSON, passed through unchanged after human approval; the Pusher's
own instructions forbid deviating from it.

Agent id (this deployment): `a4c953d1-b381-4162-9a91-e16eb85ce9e5`

---

## Next (not built yet)

The Operations Manager workflow wrapping both agents with a `ViewData`
(Work Center) approval gate between them, plus the two `typesafe-jev_evaluate`
`runService` calls (pre-push and post-push). See `../jev-tool/README.md`
for the confirmed Jev `questions` schema (`score` type needs `criteria` as
an ORDERED LIST of level descriptions, not an object — confirmed empirically
2026-09-21, differs from the `choice` type's object-keyed `criteria`).
