# Linux Diagnostics Agent — FlowAI Agent Spec

A deployable FlowAI agent definition. Nothing below is tied to any specific Itential Platform
instance, project, Gateway cluster, or provider — every value that's specific to a deployment is
a placeholder (`$PLATFORM_URL`, `$PROJECT_ID`, `$GATEWAY_CLUSTER`, etc.). Fill these in once in
this repo's root `.env` (copy from `.env.example` — see the root `README.md` "Setup" section),
not by hand in the commands below. See "Provenance" at the end for where this definition
originally came from and what's a reconstruction vs. verified-live.

**API surface note:** this spec targets the `agent-project-service` / `agent-session-manager` /
`model-registry-service` / `/tools` API surface — same as `agents/Cisco/*`. See
`agents/Cisco/catalyst-center-health/itential/agent.spec.md`'s header note if your platform's
calls don't match what's below.

**Scope note:** this is a diagnostics-only, platform-agnostic agent. The original live agent this
was reverse-engineered from also delegated email/Slack delivery to a separate "Comms Agent" and
two Itential-native workflows — that delivery mechanism is intentionally NOT reproduced here. This
spec's agent (and `../skills/linux-diagnostics/SKILL.md`) only runs diagnostics and returns a
report; wiring that report into a notification channel is left entirely to whatever deploys this,
Itential or not. See Section 4 and Provenance for the full original agent this was scoped down
from.

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

# 2. Confirm the tool is live before wiring it into an agent
curl -s -G "$PLATFORM_URL/tools" \
  --data-urlencode "referenceIds=gatewayService:$GATEWAY_CLUSTER:python-script:linux-diagnostics" \
  -H "Authorization: Bearer $TOKEN" | jq '.total'   # expect 1 — if 0, see Section 2's wrapper-service build steps

# 3. Create — payload is Section 1+3 of this doc assembled; tools[] from Section 2's table
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects/$PROJECT_ID/agents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @payload.json

# 4. Run (always async — no sync equivalent)
curl -s -X POST "$PLATFORM_URL/agent-session-manager/sessions/run-agent" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"agent": "<agent-id-from-step-3>", "inputs": {"inventory": "<your-inventory-group-or-hosts>"},
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
`$PROJECT_ID` (viewer → `403 does not have write rights`), and `$GATEWAY_CLUSTER` shows
`connection_status: connected` with a `groups` ACL entry your service account belongs to
(`GET $PLATFORM_URL/gateway_manager/v1/gateways`). Separately, whatever inventory group/host list
you pass as `inventory` must already exist and be SSH-reachable from wherever the
`linux-diagnostics` wrapper service actually executes `ansible-playbook` — see `mcp/INSTALL.md`.

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `Linux Diagnostics` |
| Description | Runs comprehensive Linux host health diagnostics (disk, memory, CPU, swap, inodes, services, failed systemd units, OOM events, zombie processes) and returns a classified report. Read-only, platform-agnostic — no email/Slack delivery. |
| Project (namespace) | any FlowAI project you own — referred to as `$PROJECT_ID` throughout |
| Operators | whatever operator group(s) fit your org, or none |
| LLM provider profile | any Claude Sonnet-class Anthropic model configured on your platform — look up available profiles via your platform's model registry |
| Input schema | `{"type": "object", "additionalProperties": false, "required": ["inventory"], "properties": {"inventory": {"type": "string", "description": "An inventory group name or comma-separated host list (Ansible shorthand, e.g. \"host1,host2,\") to run diagnostics against. Must reference a real, SSH-reachable inventory — arbitrary hostnames that aren't registered anywhere will fail at the tool level, not silently no-op."}}}` |

---

## 2. Tools

Exactly 1, read-only:

| # | referenceId | lastKnownName |
|---|---|---|
| 1 | `gatewayService:$GATEWAY_CLUSTER:python-script:linux-diagnostics` | `linux-diagnostics` |

**Naming convention:** `<mcp-server-name>_<tool-name>` is the Cisco-family convention, but this
MCP server only exposes one tool (`run_diagnostics`) so the Gateway service is just named after
the server itself — adjust to your own naming convention if it conflicts with something else in
your environment.

### 2.1 Why a wrapper service is needed at all

Same reason as the Cisco agents: registering an MCP server on Gateway
(`iagctl mcp server add`) makes its tools callable via `iagctl mcp tool call`, but doesn't
automatically make them visible to FlowAI as agent tools on every Gateway build. Check:

```bash
iagctl get services --raw | grep linux-diagnostics   # look for mcptool/linux-diagnostics entries
```

If nothing appears, build the wrapper service below.

### 2.2 Building the wrapper service

Uses the same generic wrapper script pattern as the Cisco agents (official MCP Python SDK,
`streamablehttp_client` + `ClientSession`) — pointed at `../mcp/server.py` (this repo's own MCP
server) instead of a third-party one:

```python
import argparse, asyncio, json, os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("LINUX_DIAGNOSTICS_MCP_URL", "http://host.docker.internal:7002/v1/mcp")
TOOL_NAME = os.environ.get("LINUX_DIAGNOSTICS_MCP_TOOL", "run_diagnostics")

def parse_unknown_args(argv):
    # IAG sends every decorator field as --key=value, including unset ones (value '').
    # Omit those — the MCP server's typed schema rejects '' for non-string fields.
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
iagctl create repository linux-diagnostics-wrapper --url <your-repo-url> --reference main

iagctl create decorator linux-diagnostics \
  --schema '{"type":"object","properties":{"inventory":{"type":"string"}},"required":["inventory"],"additionalProperties":false}'
  # matches run_diagnostics' real input_schema — pull it directly via
  # `iagctl mcp tool list linux-diagnostics --raw` once the MCP server is registered, rather than
  # trusting this copy if the tool's signature ever changes

iagctl create service python-script linux-diagnostics \
  --repository linux-diagnostics-wrapper --filename main.py \
  --decorator linux-diagnostics \
  --env LINUX_DIAGNOSTICS_MCP_TOOL=run_diagnostics \
  --env LINUX_DIAGNOSTICS_MCP_URL=http://host.docker.internal:7002/v1/mcp

iagctl run service python-script linux-diagnostics --set inventory=<your-test-group>
# confirm real data back before wiring into an agent
```

Once this runs cleanly via `iagctl run service`, Section 0 Step 2's `/tools` check should return
`total: 1`.

### 2.3 Alternative: deploy the Ansible playbook as a native Gateway service instead

If you don't need MCP portability and just want this on Itential, IAG supports
`ansible-playbook`-type services natively — you could register `../ansible/linux_diagnostics.yml`
directly as `gatewayService:$GATEWAY_CLUSTER:ansible-playbook:linux-diagnostics` instead of going
through the MCP wrapper above, the same shape the *original* production service used (see
Provenance). This spec documents the MCP-wrapped path as primary because that's what makes the
diagnostics logic usable outside Itential too (Claude Code, Codex, etc.) — the native path is a
valid shortcut if you only care about the Itential side.

---

## 3. Instructions (system prompt)

```
You are a Linux Infrastructure Diagnostics Specialist. Your job is to run
comprehensive health checks across a Linux host inventory and return a clear,
classified report. You are strictly read-only — the only tool you have runs
read-only commands on target hosts, and you never suggest or attempt any
remediation yourself.

Tools you have:
- run_diagnostics — runs the diagnostics collection against a target
  inventory group or host list. Takes one argument, inventory (string) — an
  Ansible inventory group name or comma-separated host list. Returns raw
  per-host metrics: uptime, memory, swap, CPU load, disk usage per mount,
  inode usage per mount, expected-service status, failed systemd units, OOM
  kill events in the last 24 hours, zombie process count. It does NOT
  classify anything — that's your job, using the thresholds below.

Health thresholds — apply per host, per metric:
DISK (per mount):        WARNING > 80% used,  CRITICAL > 90% used
MEMORY free:              WARNING < 256 MB,    CRITICAL < 64 MB
SWAP used:                WARNING > 50%,       CRITICAL > 90%
CPU LOAD (1m / cores):    WARNING > 2.0,       CRITICAL > 5.0
INODES (per mount):       WARNING > 80% used,  CRITICAL > 90% used
SERVICES:                 WARNING if any expected service inactive,
                           CRITICAL if sshd is not running
FAILED SYSTEMD UNITS:     WARNING if 1 or more in failed state
OOM EVENTS (last 24h):    CRITICAL if any detected
ZOMBIE PROCESSES:         WARNING if count > 0

A host's overall status is the worst of any individual metric. A host that
comes back unreachable is CRITICAL regardless of any other field.

Process:
1. Call run_diagnostics with inventory set to the value provided in the
   objective.
2. For each host returned: if reachable is false, classify CRITICAL with the
   stated reason and skip metric evaluation for that host. Otherwise, apply
   every threshold above and record which ones were breached.
3. Assign each host's overall status as the worst individual metric result.
4. If the tool call itself fails (isError: true, no hosts returned), report
   that failure explicitly — do not report "0 of 0 hosts degraded" as if
   that were a clean result. A failed inventory resolution or unparseable
   playbook output is a tool failure, not evidence of a healthy fleet.

Output format:
- Start with a one-line overall count: "X of Y hosts degraded" (degraded =
  WARNING or CRITICAL).
- Then a section per status tier, CRITICAL first, each host as a bullet:
  "hostname — status: LEVEL, triggered by: <metric list with values>".
- OK hosts can be a single summary line each — no need to enumerate every
  clean metric.
- End with a "Needs attention first" line naming the 1-3 worst hosts, if any.
- This report is your final output. Do not attempt to send email or Slack
  notifications yourself — you have no tool for that in this deployment.
```

This should be functionally identical to `../skills/linux-diagnostics/SKILL.md` — if they
diverge, one of them is wrong; figure out which and fix it, don't maintain two different versions
of the same procedure.

---

## 4. Related agents

The live "Linux Operations" project this was reverse-engineered from has 4 sibling agents not
covered by this conversion: **Linux Patch Readiness**, **Linux Patch - Report & Notify**,
**Linux Patch - Assess & Sync LCM**, and **Linux Patch - Execute & Update LCM** (the only write
agent in that family — applies patches and updates Lifecycle Manager records). None of those were
in scope here; this folder only covers the diagnostics agent, scoped down to remove its original
dependency on a project-specific "Comms Agent" and two Itential-native notification workflows (see
Provenance).

---

## 5. Acceptance criteria for a deployed agent

1. Create call succeeds with this name/description/provider/instructions/inputSchema.
2. The wrapper service exists as a Gateway service and is FlowAI-discoverable (`/tools` returns it
   for its `referenceId`).
3. A run with a valid, SSH-reachable `inventory` value returns a report matching the output format
   in Section 3, with real per-host metrics from the target hosts.
4. A run with an invalid/unresolvable `inventory` value, or an unreachable target host, produces a
   stated failure or CRITICAL/"unreachable" finding — never a false "0 of 0 hosts degraded" /
   "all clear."

---

## Provenance

This spec was reverse-engineered from a live "Linux Diagnostics" FlowAI agent (Linux Operations
project) on an Itential Platform trial instance. Two things in this reconstruction are worth
being explicit about:

**The diagnostics logic (`../ansible/linux_diagnostics.yml`, `../mcp/server.py`) is a
reconstruction, not the original source.** The original agent's tool was
`gatewayService:<cluster>:ansible-playbook:linux-diagnostics` — a native IAG Ansible-playbook
service, not an MCP-wrapped one. Pulling its actual playbook source requires `iagctl` Gateway-admin
login credentials that weren't available during this conversion. What *is* real evidence: a live
test run against that actual production service (inputs `inventory: "demo-linux"` and
`inventory: "all"`, both guessed) returned `404 Inventory '<value>' not found` — confirming the
tool's real parameter is a registered Automation Gateway inventory reference, not an arbitrary
hostname string, which is why this spec's Input Schema description calls that out explicitly. A
third attempt (empty inventory) got further and returned real raw Ansible JSON-callback output
revealing the actual playbook path (`linux_patch_check/linux_diagnostics.yml`), an SSH-key
injection step (`tasks/prepare_ssh.yml`) before host resolution, and a dynamic-inventory build
step (`ansible.builtin.add_host` + `from_json` filter) that failed before reaching any actual
metric-collection tasks. This conversion's playbook and MCP server were written from scratch to
match the metrics/thresholds the original agent's own instructions document it collecting — see
`../mcp/INSTALL.md` Section 5 for how to swap in the real playbook if you have Gateway-admin
access to pull it.

**The email/Slack delivery step was deliberately removed, not just left undocumented.** The
original agent delegated to a separate "Comms Agent" (which itself called two Itential-native
workflow tasks — `send_email` and a Slack notification workflow). This spec's agent has no
delivery mechanism at all; it only returns the diagnostics report. This was an explicit scoping
decision for this conversion, not a portability gap — the point of this agent is to be a clean,
platform-agnostic diagnostics tool that any caller (human, another agent, a workflow) can route
output from however it needs to.
