# Cisco Catalyst Center Health Triage Agent — FlowAI Agent Spec

A deployable FlowAI agent definition. Nothing below is tied to any specific Itential Platform
instance, project, Gateway cluster, or provider — every value that's specific to a deployment is
a placeholder (`$PLATFORM_URL`, `$PROJECT_ID`, `$GATEWAY_CLUSTER`, etc.). Fill these in once in
this repo's root `.env` (copy from `.env.example` — see the root `README.md` "Setup" section),
not by hand in the commands below — Section 0's recipe sources `.env` directly. See "Provenance"
at the end for where this definition originally came from.

**API surface note:** this spec targets the `agent-project-service` / `agent-session-manager` /
`model-registry-service` / `/tools` API surface. Some Itential Platform builds instead expose an
older `/flowai/agents`-style API — if `$PLATFORM_URL/agent-project-service/...` 404s for you,
check `jq '.paths|keys[]|select(contains("agent"))' openapi.json` against your own platform to
find the equivalent calls, and consult the `itential-builder:flowagent` skill's own compatibility
notes.

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

# 2. Confirm the 5 tools are live before wiring them into an agent
curl -s -G "$PLATFORM_URL/tools" --data-urlencode "referenceIds=$(paste -sd, <<EOF
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_devices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDevices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getDeviceSummary
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSites
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSiteAssignedNetworkDevice
EOF
)" -H "Authorization: Bearer $TOKEN" | jq '.total'   # expect 5 — if 0, see Section 2's wrapper-service build steps

# 3. Create — payload is Section 1+3 of this doc assembled; tools[] from Section 2's table
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects/$PROJECT_ID/agents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @payload.json

# 4. Run (always async — no sync equivalent)
curl -s -X POST "$PLATFORM_URL/agent-session-manager/sessions/run-agent" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"agent": "<agent-id-from-step-3>", "inputs": {},
       "terminationCallbackSignature": {"location":"none","serviceName":"none","methodName":"none","identifier":"none"}}'
  # terminationCallbackSignature is documented as optional but omitting it fails validation in
  # practice on this API surface — always send the placeholder object above.

# 5. Poll until status != RUNNING
curl -s "$PLATFORM_URL/agent-session-manager/sessions/<sessionId>" -H "Authorization: Bearer $TOKEN"

# 6. Read the answer — use limit=200, the default page size can truncate multi-iteration runs
curl -s -G "$PLATFORM_URL/agent-session-manager/sessions/<sessionId>/messages" \
  --data-urlencode "limit=200" -H "Authorization: Bearer $TOKEN"
  # last `type: "inference-succeeded"` event's `text` field is the final answer, not a
  # `conclusion` field

# 7. Delete a test agent when done — DELETE is project-scoped, not agent-scoped:
curl -s -X DELETE "$PLATFORM_URL/agent-project-service/projects/$PROJECT_ID/agents/<agent-id>" \
  -H "Authorization: Bearer $TOKEN"
```

**Preconditions this recipe assumes:** your service account has editor/owner GBAC role on
`$PROJECT_ID` (viewer → `403 does not have write rights`), and `$GATEWAY_CLUSTER` shows
`connection_status: connected` with a `groups` ACL entry your service account belongs to
(`GET $PLATFORM_URL/gateway_manager/v1/gateways`).

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `Cisco Catalyst Center Health Triage Agent` |
| Description | This agent uses the Cisco Community Official MCP for Catalyst Center |
| Project (namespace) | any FlowAI project you own — referred to as `$PROJECT_ID` throughout |
| Operators | whatever operator group(s) fit your org, or none |
| LLM provider profile | any Claude Sonnet-class Anthropic model configured on your platform — look up available profiles via your platform's model registry (`GET $PLATFORM_URL/model-registry-service/...` or the FlowAI UI's provider picker) |
| Input schema | `{"type": "object", "additionalProperties": false, "required": [], "properties": {}}` — no invocation parameters; the objective is entirely in the instructions |

---

## 2. Tools

Exactly 5, all read-only, all against Catalyst Center:

| # | referenceId | lastKnownName |
|---|---|---|
| 1 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_devices` | `catalyst-center_api_devices` |
| 2 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDevices` | `catalyst-center_api_retrieveNetworkDevices` |
| 3 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getDeviceSummary` | `catalyst-center_api_getDeviceSummary` |
| 4 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSites` | `catalyst-center_api_getSites` |
| 5 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSiteAssignedNetworkDevice` | `catalyst-center_api_getSiteAssignedNetworkDevice` |

**Naming convention:** `<mcp-server-name>_<mcp-tool-name>`, type `python-script`, on whichever
Gateway cluster you register the wrapper services below to (`$GATEWAY_CLUSTER`).

### 2.1 Why a wrapper service is needed at all

Registering an MCP server on Gateway (`iagctl mcp server add`) makes its tools callable via
`iagctl mcp tool call`, but that alone does not make them discoverable to FlowAI as agent tools on
every Gateway build — behavior here has been observed to vary (some builds auto-bridge every MCP
tool into the Gateway services catalog under `id: "mcptool/<server>"`; others require an explicit
wrapper). Check both before assuming either way:

```bash
iagctl get services --raw | grep catalyst-center   # look for mcptool/catalyst-center entries
```

If nothing appears, or if you want a hand-cleaned decorator schema (MCP's raw `input_schema` often
carries `anyOf`/`null` wrapping that makes for a messier LLM-facing tool contract than a
hand-written one), build the wrapper services below. **Also required either way:** the Gateway
itself must be connected to your specific platform tenant — check
`GET $PLATFORM_URL/gateway_manager/v1/gateways`; a registered-but-disconnected Gateway (or one your
service account lacks `groups` ACL for) makes any of its tools — bridged or wrapped — invisible to
FlowAI, independent of anything MCP-related.

### 2.2 Building the wrapper services

One script, driven by two env vars, backs all 5 services — using the official MCP Python SDK
(`streamablehttp_client` + `ClientSession`, not hand-rolled JSON-RPC; the transport is
SSE-based streamable-HTTP with a session handshake that's easy to get subtly wrong by hand):

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

The empty-string omission handling matters in practice, not just in theory — a version without it
forwards `offset=''` and the MCP server's pydantic validation rejects it.

**Push this script (plus a `requirements.txt` with `mcp`) to a git repository your own Gateway can
clone.** Gateway does not support local/`file://` repositories — it needs a real remote (any git
host you control: GitHub, GitLab, your own git server). Then, once registered:

```bash
iagctl create repository catalyst-center-wrappers \
  --url <your-repo-url> --reference main

iagctl create decorator catalyst-center_api_devices --schema '{...matching input_schema...}'
# repeat per tool — pull each tool's real input_schema via `iagctl mcp tool list catalyst-center --raw`

iagctl create service python-script catalyst-center_api_devices \
  --repository catalyst-center-wrappers --filename main.py \
  --decorator catalyst-center_api_devices \
  --env CATALYST_CENTER_MCP_TOOL=api_devices \
  --env CATALYST_CENTER_MCP_URL=http://host.docker.internal:7001/v1/mcp
# repeat per tool — only CATALYST_CENTER_MCP_TOOL and the service/decorator name change

iagctl run service python-script catalyst-center_api_devices --set limit=5   # confirm real data back
```

Repeat the decorator/service pair for the remaining 4 tools
(`api_retrieveNetworkDevices`, `api_getDeviceSummary`, `api_getSites`,
`api_getSiteAssignedNetworkDevice`). Once all 5 run cleanly via `iagctl run service`, Section 0
Step 2's `/tools` check should return `total: 5`.

---

## 3. Instructions (system prompt)

```
You are a Network Health Triage agent for Cisco Catalyst Center. Your job is to
find degraded devices and explain where they are. Use ONLY the tools listed
below. You are strictly read-only — never call any tool that creates, updates,
deletes, or remediates anything, even if one appears in context.

Tools you have:
- api_devices — DNA Assurance device intent API. Returns each device's
  overallHealth score (0-10), issue count, and site/location fields. This is
  your primary source for health data.
- api_retrieveNetworkDevices — basic device inventory (role, family,
  reachability status, management IP). Use to enrich a flagged device with
  role and type when api_devices doesn't have it.
- api_getDeviceSummary — brief per-device summary. Use only when drilling into
  a specific flagged device for more detail.
- api_getSites — converts a siteId into a readable site hierarchy name
  (nameHierarchy). Use when a flagged device's site comes back as a raw ID.
- api_getSiteAssignedNetworkDevice — confirms which site a device is assigned
  to. Use only as a fallback if api_devices and api_getSites don't resolve a
  clear site for a flagged device.

Health threshold: a device is "degraded" if its overallHealth score is below
7 (on a 0-10 scale), OR if it has one or more open issues reported by
api_devices.

Process:
1. Call api_devices to get health scores for all devices (or the requested
   scope, if the objective specifies sites or device names).
2. Identify every device below the health threshold.
3. For each flagged device, resolve its site name and role:
   fields already on the api_devices record if present; otherwise call
   api_retrieveNetworkDevices for role, and api_getSites (or
   api_getSiteAssignedNetworkDevice as a fallback) to resolve the site name.
4. Produce a summary grouped by site, listing: device name,
   issue count/description, and role.

Output format:
- Start with a one-line overall count: "X of Y devices degraded"
- Then a section per site, each device as a bullet: "device_name (role) —
  score: N/10, issues: <summary>"
- If a site or role genuinely cannot be resolved after trying the fallback
  tools, say "(site/role unresolved)" rather than guessing.
- End with a short "Needs attention first" line naming the 1-3 worst devices,
  if any exist.
```

This should be functionally identical to `../skills/catalyst-center-health-triage/SKILL.md` — if
they diverge, one of them is wrong; figure out which and fix it, don't maintain two different
versions of the same procedure.

---

## 4. Related agents

Two sibling agents exist in this same family, using the same Catalyst Center MCP server: a
read/write **Remediation** agent (`../../catalyst-center-remediation/`, gated on human approval)
and a read-only **EoX & Security Advisories** agent (`../../catalyst-center-eox-security/`). Each
is deployed independently — there's no dependency between them beyond sharing the same MCP server
and Gateway wrapper-service pattern.

---

## 5. Acceptance criteria for a deployed agent

1. Create call succeeds with this name/description/provider/instructions/inputSchema.
2. All 5 wrapper services exist as Gateway services and are FlowAI-discoverable (`/tools` returns
   them for their `referenceId`s).
3. A no-argument invocation returns a report matching the output format in Section 3, against
   your own Catalyst Center controller's real devices.
4. An unreachable/misconfigured MCP server produces a stated failure — not a false "0 of N
   degraded."

---

## Provenance

This spec was originally authored by reverse-engineering a working example agent on an Itential
Platform trial instance, then generalized so it can be deployed on any Itential Platform +
Gateway + this MCP server. `../tests/` has an example verification run captured during that
process — real evidence that this deployment recipe and instructions work end-to-end, but tied to
that one environment's specific project/cluster/sandbox values. Your own run will use your own
`$PLATFORM_URL`/`$PROJECT_ID`/`$GATEWAY_CLUSTER` and will show your own Catalyst Center
controller's real devices, not the ones named in that example.
