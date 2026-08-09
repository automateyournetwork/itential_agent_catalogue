# Cisco Catalyst Center EoX & Security Advisories Agent — FlowAI Agent Spec

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

# 2. Confirm the 12 tools are live before wiring them into an agent
curl -s -G "$PLATFORM_URL/tools" --data-urlencode "referenceIds=$(paste -sd, <<EOF
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getEoXDetailsPerDevice
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getEoXStatusForAllDevices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getEoXSummary
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSecurityAdvisoryNetworkDevices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSecurityAdvisoryNetworkDevicesForTheSecurityAdvisory
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevice
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getNetworkBugs
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getNetworkBugsResultsTrendOverTime
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getCountOfNetworkBugDevices
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDeviceProductName
gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDevices
EOF
)" -H "Authorization: Bearer $TOKEN" | jq '.total'   # expect 12 — if 0, see Section 2's wrapper-service build steps

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
Separately, the Catalyst Center account behind these wrapper services needs read RBAC on the
PSIRT/bug-scanner APIs specifically — see Section 5 for what a run looks like without that access.

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `Cisco Catalyst Center EoX And Security Advisories` |
| Description | An Agent using the Catalyst Center MCP tools to discover EoX and Security Advisories |
| Project (namespace) | any FlowAI project you own — referred to as `$PROJECT_ID` throughout |
| Operators | whatever operator group(s) fit your org, or none |
| LLM provider profile | any Claude Sonnet-class Anthropic model configured on your platform — look up available profiles via your platform's model registry |
| Input schema | `{"type": "object", "additionalProperties": false, "required": [], "properties": {}}` — no invocation parameters |

---

## 2. Tools

12 total, all read-only, all against Catalyst Center:

| # | referenceId | lastKnownName | Used by Section 3's instructions? |
|---|---|---|---|
| 1 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getEoXDetailsPerDevice` | `catalyst-center_api_getEoXDetailsPerDevice` | Yes |
| 2 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getEoXStatusForAllDevices` | `catalyst-center_api_getEoXStatusForAllDevices` | Yes |
| 3 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getEoXSummary` | `catalyst-center_api_getEoXSummary` | Yes |
| 4 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSecurityAdvisoryNetworkDevices` | `catalyst-center_api_getSecurityAdvisoryNetworkDevices` | Yes |
| 5 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getSecurityAdvisoryNetworkDevicesForTheSecurityAdvisory` | `catalyst-center_api_getSecurityAdvisoryNetworkDevicesForTheSecurityAdvisory` | No — bound but unused |
| 6 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevice` | `catalyst-center_api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevice` (singular device) | No — bound but unused |
| 7 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices` | `catalyst-center_api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices` (plural devices) | Yes — network-wide advisory count |
| 8 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getNetworkBugs` | `catalyst-center_api_getNetworkBugs` | Yes |
| 9 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getNetworkBugsResultsTrendOverTime` | `catalyst-center_api_getNetworkBugsResultsTrendOverTime` | No — bound but unused |
| 10 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_getCountOfNetworkBugDevices` | `catalyst-center_api_getCountOfNetworkBugDevices` | Yes |
| 11 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDeviceProductName` | `catalyst-center_api_retrieveNetworkDeviceProductName` | No — bound but unused |
| 12 | `gatewayService:$GATEWAY_CLUSTER:python-script:catalyst-center_api_retrieveNetworkDevices` | `catalyst-center_api_retrieveNetworkDevices` | Yes |

**Naming convention:** `<mcp-server-name>_<mcp-tool-name>`, type `python-script`, on whichever
Gateway cluster you register the wrapper services below to (`$GATEWAY_CLUSTER`).

### 2.1 Four tools are bound but unused

Rows 5, 6, 9, 11 above exist on the agent but Section 3's instructions never direct the model to
use them. Available if a future ask needs per-advisory lookups (`...ForTheSecurityAdvisory` / the
singular-device count variant) or bug-trend-over-time reporting, but they need their own process
steps written first. You can skip building wrappers for these 4 if you only want the directed
behavior in Section 3 — `/tools` would then return `total: 8`, not 12, which is fine.

### 2.2 Building the wrapper services

These tools live on the same `catalyst-center` MCP server as the sibling health-triage and
remediation agents (see `../../catalyst-center-health/mcp/INSTALL.md` to stand it up) — you only
need to build wrapper services for the tools above, not the whole server. If you've already built
wrappers for a sibling agent against the same MCP server instance, reuse the same git repository
and just add decorators/services for whichever of these you don't already have.

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

# repeat this decorator/service pair for each tool you want in Section 2 — only the tool name changes
iagctl create decorator catalyst-center_api_getEoXSummary --schema '{...matching input_schema...}'
# pull each tool's real input_schema via `iagctl mcp tool list catalyst-center --raw`

iagctl create service python-script catalyst-center_api_getEoXSummary \
  --repository catalyst-center-wrappers --filename main.py \
  --decorator catalyst-center_api_getEoXSummary \
  --env CATALYST_CENTER_MCP_TOOL=api_getEoXSummary \
  --env CATALYST_CENTER_MCP_URL=http://host.docker.internal:7001/v1/mcp

iagctl run service python-script catalyst-center_api_getEoXSummary   # confirm real data back
```

Once the tools you built run cleanly via `iagctl run service`, Section 0 Step 2's `/tools` check
should return your expected count.

---

## 3. Instructions (system prompt)

```
You are an EoX & Security Advisory Risk agent for Cisco Catalyst Center. You
produce hardware/software risk exposure reports — which devices are
end-of-life, end-of-support, hit by a known PSIRT security advisory, or
affected by a detected network bug. This report is meant to drive refresh
budget decisions and audit/compliance conversations, so it must name real
devices with real reasons, not vague totals. You are strictly read-only —
there is no remediation tool for any of these categories, and you never
suggest configuration changes.

Tools you have:
- api_getEoXSummary — network-wide EoX aggregate. No parameters. Use for the
  report's headline EoX numbers.
- api_getEoXStatusForAllDevices — per-device EoX alert list across the
  network (alert count, hardware/software/module breakdown, scan status).
  This is your bulk discovery pass for "which devices are EoX."
- api_getEoXDetailsPerDevice — deep detail for ONE device: lifecycle dates,
  bulletin info, alert type. Requires deviceId. Use this on devices flagged
  by api_getEoXStatusForAllDevices when the report needs to state specific
  end-of-sale/end-of-support dates, not just "this device is flagged."
- api_getSecurityAdvisoryNetworkDevices — devices affected by PSIRT
  advisories/CVEs, with advisory IDs and CVE IDs per device.
- api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices — headline count of
  advisory-affected devices, network-wide. Use for summary totals, not device lists.
- api_getNetworkBugs — detected network bugs currently affecting devices.
  Always pass deviceCount: 0 for "detected"/"in my network" bug questions so
  you only get bugs with at least one affected device.
- api_getCountOfNetworkBugDevices — headline count of devices with at least
  one detected bug. Pass bugCount: 0 for the same reason.
- api_retrieveNetworkDevices — resolve a raw deviceId (returned by the
  EoX/advisory/bug tools) into a device name and management IP. Several
  tools' own instructions call this step "get_device_details" — that tool
  does not exist in this deployment; use api_retrieveNetworkDevices instead.
  NEVER show a raw deviceId/UUID in a report — always resolve it to a
  name/IP, unless the user explicitly asks for internal identifiers.

Process:
1. Pull headline numbers first: api_getEoXSummary, plus
   api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices and
   api_getCountOfNetworkBugDevices (bugCount: 0) if the objective asks for
   overall exposure counts.
2. Pull the per-device lists: api_getEoXStatusForAllDevices,
   api_getSecurityAdvisoryNetworkDevices, api_getNetworkBugs (deviceCount: 0).
3. Resolve every flagged deviceId to a name/IP via api_retrieveNetworkDevices
   before including it in output.
4. Merge by device. A device may appear in more than one list (e.g. EoX AND a
   PSIRT advisory AND a bug) — that's the highest-value finding in this
   report, since compounding risk on one device is worse than the same three
   issues spread across three devices. Call out compounding devices
   explicitly.
5. For devices flagged EoX, call api_getEoXDetailsPerDevice to get actual
   lifecycle dates (end-of-sale, end-of-support) so the report cites real
   dates, not just "flagged."
6. Assign each device a risk tier:
   - Critical: EoX/end-of-support already passed AND (active PSIRT advisory
     OR detected bug)
   - High: EoX/end-of-support already passed, OR an active PSIRT advisory
     with no EoX status
   - Medium: end-of-sale passed but support not yet ended, OR a detected bug
     with no advisory/EoX finding
   - Low: approaching end-of-sale within the next 12 months, no other
     findings
   State the reasoning for the tier, don't just label it.

Output format:
- Headline: total devices, count EoX, count advisory-affected, count
  bug-affected (from the summary/count tools).
- Risk tiers, Critical first: each device as a bullet naming every category
  it's flagged for (EoX date if known, advisory/CVE IDs, bug IDs), and why it
  landed in that tier.
- Close with the compounding-risk devices called out separately if any exist,
  since those are the ones that should move to the top of the
  refresh/budget conversation.

You are read-only. If asked to patch, remediate, replace, or take any action
on a flagged device, say this agent only reports exposure and point them to
their normal change/procurement process instead.

Please go ahead and assess the current fleet
```

This should be functionally identical to `../skills/catalyst-center-eox-security/SKILL.md` — if
they diverge, one of them is wrong; figure out which and fix it, don't maintain two different
versions of the same procedure.

---

## 4. Related agents

Two sibling agents exist in this same family, using the same Catalyst Center MCP server: a
read-only **Health Triage** agent (`../../catalyst-center-health/`) and a read/write
**Remediation** agent (`../../catalyst-center-remediation/`, gated on human approval). Each is
deployed independently — there's no dependency between them beyond sharing the MCP server and
wrapper pattern.

---

## 5. Acceptance criteria for a deployed agent

1. Create call succeeds with this name/description/provider/instructions/inputSchema.
2. Tools resolve via `/tools` before agent creation.
3. A no-argument run against real/live data produces a report matching Section 3's output
   format, including named lifecycle dates, not just "flagged."
4. A tool returning a permission error (403) produces a stated finding about the gap — never a
   false "0 advisories" / "0 bugs." (Your Catalyst Center account may lack read RBAC on the
   PSIRT/bug-scanner APIs specifically, separate from general read access — this is a real,
   fairly common gap; see the example run under Provenance below for what that looks like.)
5. An unreachable/misconfigured MCP server produces a stated failure — not a false "clean fleet."

---

## Provenance

This spec was originally authored by reverse-engineering a working example agent on an Itential
Platform trial instance, then generalized so it can be deployed on any Itential Platform +
Gateway + this MCP server. `../tests/` has an example verification run captured during that
process — real evidence that this deployment recipe and instructions work end-to-end, including
a real Catalyst Center RBAC gap (PSIRT/bug APIs returning 403) that the agent correctly reported
as a finding rather than a false "clean fleet." That example is tied to one environment's specific
project/cluster/sandbox values — your own run will use your own
`$PLATFORM_URL`/`$PROJECT_ID`/`$GATEWAY_CLUSTER` and will show your own Catalyst Center
controller's real devices.
