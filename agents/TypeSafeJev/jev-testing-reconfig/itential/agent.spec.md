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

## 4. The workflow (`reconfig_workflow.json` in this directory)

Built 2026-09-21. `Jev Testing - R1-R2-SW1-SW2 Reconfig`
(`7e186156-b550-4030-960f-bec53fe99881`), created via
`POST /automation-studio/automations` (NOT `/automation-studio/workflows`,
which only supports `GET`/`HEAD` — the body must be wrapped in a top-level
`{"automation": {...}}` key with `type: "automation"`, `canvasVersion: 3`,
and a `groups: []` array, or the create call 500s with a schema dump that
is itself the most useful error message you'll get from this endpoint).

**Chain:** `runAgent(Proposer)` → `query` sessionId → `runService`
(`antares-vuln_extract_agent_tool_result` — the CiscoAntares tool is
generic, reused as-is, no new extraction tool needed) → `query`
`result.stdout` (raw proposal JSON string) → `runService`
(`typesafe-jev_evaluate`, pre-check) → `query` `result.stdout` → `ViewData`
(Work Center approval, `body`=raw proposal string, `variables`=raw Jev
string) → on approve, `runAgent(Pusher v2)` with `inputs.approved_devices`
= the same raw proposal string, unchanged → same
extract/query/Jev-post-check chain → `workflow_end`. On reject, or on any
of the two critical `query` extraction steps failing to resolve, transitions
straight to `workflow_end` instead.

**Why raw JSON strings are passed through untouched at every hop instead of
parsing into objects and rebuilding them:** avoids ever needing a
JSON-stringify step, which this platform's `WorkFlowEngine` doesn't appear
to expose as a task (only `parse`, string→object, confirmed elsewhere in
this repo). `query`'s own path-extraction returns whatever's at that path
as-is; since Jev's own `state` field and an agent's own `inputs.*` string
field both happily accept a raw JSON string as their value, there was never
a need to touch the data at all between extraction and its next consumer.

**`AgentSessionManager.runAgent` vs `FlowAI.callAgent`:** tested both as
throwaway probe workflows before committing to an architecture.
`FlowAI.callAgent` (referencing an agent by plain name) exists as a task
type in the UI and even in another real project's workflow on this same
platform instance, but creating it here returns
`"errors":[{"task":"...","message":"Package not found"}]` — confirms the
`itential-builder:flowagent` skill's own warning that the classic
`/flowai/*` surface 404s on this platform build; that workflow example
apparently doesn't actually work here despite existing.
`AgentSessionManager.runAgent` (`actor: "job"`, `agent` = the
agent-project-service UUID, not a name) creates and *runs* cleanly — a real
probe job spent 5+ real minutes in `status: "running"` calling out to the
agent, confirming it isn't a fast, silent no-op.

**Pusher v2, not v1:** the original Pusher agent
(`a4c953d1-b381-4162-9a91-e16eb85ce9e5`) expected `approved_devices` to be
pre-extracted down to just the `devices` sub-object — which would have
needed a workflow-level JSON-stringify step that doesn't cleanly exist here.
Rather than fight that, a second agent,
`R1-R2-SW1-SW2 Reconfig Pusher (v2)` (`38c873f8-36bd-4fae-a49e-d9fb1150daf7`),
was created instead, accepting the Proposer's *entire* raw payload
(`summary`/`current_state`/`devices`) unchanged and told to use only
`.devices` itself. v1 is a harmless orphan, left in the project rather than
force-deleted (agent-project-service agents can't be deleted via the API
anyway) — do not wire it into anything.

**Still open / not yet done:** an actual live end-to-end run of this
workflow (Proposer → Jev pre-check → real human click in Work Center →
Pusher → Jev post-check) — built and validated piece-by-piece
(`runAgent` task type confirmed live, `automations` create endpoint
confirmed, Proposer agent confirmed working standalone) but not yet run as
one continuous job.
