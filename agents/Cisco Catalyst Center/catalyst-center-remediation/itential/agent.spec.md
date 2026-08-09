# Cisco Catalyst Center Remediation Agent — FlowAI Agent Spec

A deployable FlowAI agent definition. Nothing below is tied to any specific Itential Platform
instance, project, Gateway cluster, or provider — every value that's specific to a deployment is
a placeholder (`$PLATFORM_URL`, `$PROJECT_ID`, `$GATEWAY_CLUSTER`, etc.). Fill these in once in
this repo's root `.env` (copy from `.env.example` — see the root `README.md` "Setup" section),
not by hand in the commands below — Section 0's recipe sources `.env` directly. See "Provenance"
at the end for where this definition originally came from, and
`../../catalyst-center-health/itential/agent.spec.md` for more detail on this API surface if your
platform's calls don't match what's below.

---

## 0. Deployment recipe

```bash
# Pulls PLATFORM_URL, CLIENT_ID, CLIENT_SECRET, PROJECT_ID, GATEWAY_CLUSTER from .env —
# see .env.example and README.md "Setup" for what each one is and how to find it.
set -a; source .env; set +a

# 1. Auth (oauth client_credentials)
TOKEN=$(curl -s -X POST "$PLATFORM_URL/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "client_id=$CLIENT_ID" --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode "grant_type=client_credentials" | jq -r '.access_token')

# 2. Confirm the 7 tools are live before wiring them into an agent
curl -s -G "$PLATFORM_URL/tools" --data-urlencode "referenceIds=$(paste -sd, <<EOF
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDevices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceStatusCount
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceStatus
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceDetailCount
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceDetail
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_complianceRemediation
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_complianceDetailsOfDevice
EOF
)" -H "Authorization: Bearer $TOKEN" | jq '.total'   # expect 7 — if 0, see Section 2's wrapper-service build steps

# 3. Create — payload is Section 1+3 of this doc assembled; tools[] from Section 2's table
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects/$PROJECT_ID/agents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @payload.json

# 4. Run (always async — no sync equivalent)
curl -s -X POST "$PLATFORM_URL/agent-session-manager/sessions/run-agent" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"agent": "<agent-id-from-step-3>", "inputs": {},
       "terminationCallbackSignature": {"location":"none","serviceName":"none","methodName":"none","identifier":"none"}}'

# 5. Poll until status != RUNNING
curl -s "$PLATFORM_URL/agent-session-manager/sessions/<sessionId>" -H "Authorization: Bearer $TOKEN"

# 6. Read the answer — use limit=200, the default page size can truncate multi-iteration runs
curl -s -G "$PLATFORM_URL/agent-session-manager/sessions/<sessionId>/messages" \
  --data-urlencode "limit=200" -H "Authorization: Bearer $TOKEN"
  # last `type: "inference-succeeded"` event's `text` field is the final answer

# 7. Delete a test agent when done — DELETE is project-scoped, not agent-scoped:
curl -s -X DELETE "$PLATFORM_URL/agent-project-service/projects/$PROJECT_ID/agents/<agent-id>" \
  -H "Authorization: Bearer $TOKEN"
```

**Preconditions this recipe assumes:** your service account has editor/owner GBAC role on
`$PROJECT_ID`, and `$GATEWAY_CLUSTER` shows `connection_status: connected` with a `groups` ACL
entry your service account belongs to (`GET $PLATFORM_URL/gateway_manager/v1/gateways`).

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `Cisco Catalyst Center Remediation Agent (Speculative)` |
| Description | This uses the Catalyst Center MCP tools to find and suggest remediations |
| Project (namespace) | any FlowAI project you own — referred to as `$PROJECT_ID` throughout |
| Operators | whatever operator group(s) fit your org, or none |
| LLM provider profile | any Claude Sonnet-class Anthropic model configured on your platform — look up available profiles via your platform's model registry |
| Input schema | `{"type": "object", "additionalProperties": false, "required": [], "properties": {}}` — no invocation parameters |
| Write access | **Yes** — the only agent in this family that can mutate the network (`api_complianceRemediation`), gated on same-turn-forbidden / next-turn-required human approval |

---

## 2. Tools

Exactly 7 tools. 6 read-only, 1 write (`api_complianceRemediation`):

| # | referenceId | lastKnownName | Write? |
|---|---|---|---|
| 1 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDevices` | `catalyst-center_api_retrieveNetworkDevices` | No |
| 2 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceStatusCount` | `catalyst-center_api_getComplianceStatusCount` | No |
| 3 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceStatus` | `catalyst-center_api_getComplianceStatus` | No |
| 4 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceDetailCount` | `catalyst-center_api_getComplianceDetailCount` | No |
| 5 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getComplianceDetail` | `catalyst-center_api_getComplianceDetail` | No |
| 6 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_complianceRemediation` | `catalyst-center_api_complianceRemediation` | **Yes** |
| 7 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_complianceDetailsOfDevice` | `catalyst-center_api_complianceDetailsOfDevice` | No |

**Naming convention:** `<mcp-server-name>_<mcp-tool-name>`, type `python-script`, on whichever
Gateway cluster you register the wrapper services below to (`$GATEWAY_CLUSTER`).

### 2.1 Building the wrapper services

These tools live on the same `catalyst-center` MCP server as the sibling health-triage and
EoX/security agents (see `../../catalyst-center-health/mcp/INSTALL.md` to stand it up) — you only
need to build wrapper services for the 7 tools above, not the whole server. If you've already
built wrappers for a sibling agent against the same MCP server instance, reuse the same git
repository and just add decorators/services for whichever of these 7 you don't already have.

The wrapper script is generic — one script, driven by two env vars, can back any tool on this MCP
server:

```python
import argparse, asyncio, json, os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("CATALYST_CENTER_MCP_URL", "http://host.docker.internal:7001/v1/mcp")
TOOL_NAME = os.environ["CATALYST_CENTER_MCP_TOOL"]

def parse_unknown_args(argv):
    # IAG sends every decorator field as --key=value, including unset ones
    # (value ''). Omit those — the MCP server's typed schema rejects '' for
    # int/bool/array fields. JSON-decode the rest so types survive.
    args = {}
    for item in argv:
        if not item.startswith("--") or "=" not in item:
            continue
        key, _, value = item[2:].partition("=")
        if value == "":
            continue
        try:
            args[key] = json.loads(value)
        except json.JSONDecodeError:
            args[key] = value
    return args

async def call_tool(params):
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(TOOL_NAME, params)

def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    result = asyncio.run(call_tool(parse_unknown_args(unknown)))
    text = [b.text for b in result.content if hasattr(b, "text")]
    print(json.dumps({"isError": result.isError, "content": text}))

if __name__ == "__main__":
    main()
```

Push this script (plus a `requirements.txt` with `mcp`) to a git repository your own Gateway can
clone (local/`file://` repos aren't supported), then:

```bash
iagctl create repository catalyst-center-wrappers \
  --url <your-repo-url> --reference main

# repeat this decorator/service pair for each of the 7 tools in Section 2 — only the tool name changes
iagctl create decorator catalyst-center_api_complianceRemediation --schema '{...matching input_schema...}'
# pull each tool's real input_schema via `iagctl mcp tool list catalyst-center --raw`

iagctl create service python-script catalyst-center_api_complianceRemediation \
  --repository catalyst-center-wrappers --filename main.py \
  --decorator catalyst-center_api_complianceRemediation \
  --env CATALYST_CENTER_MCP_TOOL=api_complianceRemediation \
  --env CATALYST_CENTER_MCP_URL=http://host.docker.internal:7001/v1/mcp

iagctl run service python-script catalyst-center_api_complianceRemediation --set deviceUuid=<test-uuid>
# confirm real data back before wiring into an agent — especially important here, since this
# tool writes to the network; know exactly what it does before an agent can call it
```

Once all 7 run cleanly via `iagctl run service`, Section 0 Step 2's `/tools` check should return
`total: 7`.

---

## 3. Instructions (system prompt)

```
You are a Compliance Remediation agent for Cisco Catalyst Center. You find
non-compliant devices, explain exactly what's wrong, and propose a fix — but
you NEVER apply a fix without a human explicitly approving it in this same
conversation turn. The account you run as has write access, so this approval
gate is the only thing standing between "propose" and "change the network."

Goals: find all non-compliant devices, configuration drift, or other issues,
and suggest the remediation for each. Do not wait for user input before
starting the analysis.

Tools you have, and when to use each (each tool's own description below is
detailed and authoritative for its parameters — read it before calling):
- api_retrieveNetworkDevices — resolve a device name or IP into its UUID.
  Several other tools' own descriptions reference a "get_device_details" tool
  for this step; that tool does not exist in this deployment — use
  api_retrieveNetworkDevices instead whenever you only have a name or IP.
- api_getComplianceStatusCount — global compliant/non-compliant totals when no
  compliance type is named.
- api_getComplianceDetailCount — non-compliant totals for a specific
  compliance type (RUNNING_CONFIG, IMAGE, PSIRT, NETWORK_SETTINGS, etc.).
- api_getComplianceDetail — identifies WHICH specific devices are
  non-compliant. This is your starting point for "find out-of-compliance
  devices."
- api_complianceDetailsOfDevice — detailed violation breakdown for ONE device
  (severity, source info, whether remediation is supported). Requires
  deviceUuid — resolve it first via api_retrieveNetworkDevices if you only
  have a name or IP.
- api_getComplianceStatus — per-device compliance breakdown by type
  (PSIRT/EOX/CONFIG/IMAGE). Use alongside api_complianceDetailsOfDevice when
  you need the type-level summary rather than violation-level detail.
- api_complianceRemediation — applies the fix. Only covers RUNNING_CONFIG
  mismatch (drift) issues. It does NOT remediate Routing, HA Remediation,
  Software Image, Security Advisories, SD-Access Unsupported Configuration,
  or Workflow compliance issues — if a flagged violation falls into one of
  those categories, say so explicitly and do not offer this tool.

Process:
1. Find non-compliant devices with api_getComplianceDetail (or
   api_getComplianceDetailCount/api_getComplianceStatusCount first if the
   request is about totals, not specific devices).
2. For each non-compliant device you'll report on, pull detail with
   api_complianceDetailsOfDevice and/or api_getComplianceStatus to explain
   exactly what's wrong and whether remediationSupported is true.
3. Build a remediation PROPOSAL. Do not call api_complianceRemediation yet.
   The proposal must state, per device: device name/UUID, what's
   out-of-compliance, whether remediation is supported, and the
   network-flap risk warning ("fixing compliance mismatches could result in
   a possible network flap"). If remediation isn't supported for a
   violation, say so and stop there for that device — do not propose it.
4. Ask explicitly: "Approve remediation for <device(s)>? yes/no."
   Do not call api_complianceRemediation in the same turn you present the
   proposal.
5. Only after the human replies with clear, affirmative approval in a
   subsequent message — naming the same device(s) you proposed — call
   api_complianceRemediation for exactly those devices. If the reply is
   ambiguous, partial, or approves a different device set, ask for
   clarification instead of proceeding.

Never call api_complianceRemediation:
- speculatively, "just to see what happens"
- for a device you haven't already shown a proposal for in this conversation
- for more devices than were explicitly approved
- for a compliance issue type this tool doesn't cover (see above)

Output format:
- Discovery: one-line count, then a per-device bullet (violation types,
  remediation-supported y/n).
- Proposal: per-device plan plus the network-flap warning, then an explicit
  yes/no approval question.
- After approval and execution: report success/failure per device from the
  api_complianceRemediation result, and recommend re-checking compliance
  status afterward (api_getComplianceDetail) rather than assuming success.
```

This should be functionally identical to `../skills/catalyst-center-remediation/SKILL.md` — if
they diverge, one of them is wrong; figure out which and fix it, don't maintain two different
versions of the same procedure.

---

## 4. Related agents

Two sibling agents exist in this same family, using the same Catalyst Center MCP server: a
read-only **Health Triage** agent (`../../catalyst-center-health/`) and a read-only **EoX &
Security Advisories** agent (`../../catalyst-center-eox-security/`). Each is deployed
independently — there's no dependency between them beyond sharing the MCP server and wrapper
pattern. This is the only one of the three with write access.

---

## 5. Acceptance criteria for a deployed agent

1. Create call succeeds with this name/description/provider/instructions/inputSchema.
2. All 7 tools resolve via `/tools` before agent creation.
3. A no-argument run against real/live data produces a discovery report — states a real count,
   never silence.
4. The agent never calls `api_complianceRemediation` without a prior proposal shown in the same
   session AND explicit human approval in a later turn naming the same device(s).
5. An unreachable/misconfigured MCP server produces a stated failure — not a false "0 issues."

---

## Provenance

This spec was originally authored by reverse-engineering a working example agent on an Itential
Platform trial instance, then generalized so it can be deployed on any Itential Platform +
Gateway + this MCP server. `../tests/` has an example verification run captured during that
process — real evidence that this deployment recipe and instructions work end-to-end (including
the human-approval safety gate holding correctly), but tied to that one environment's specific
project/cluster/sandbox values. Your own run will use your own
`$PLATFORM_URL`/`$PROJECT_ID`/`$GATEWAY_CLUSTER` and will show your own Catalyst Center
controller's real devices.
