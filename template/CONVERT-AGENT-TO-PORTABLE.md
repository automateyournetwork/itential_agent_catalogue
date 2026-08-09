# Playbook: Convert an existing FlowAI agent into a portable agent

**Use this by invoking `itential-builder:flowagent` (or Claude Code directly) with a prompt like:**

> "Convert agent `<AGENT_NAME_OR_ID>` in project `<PROJECT_NAME>` on `<PLATFORM_URL>` to a
> portable agent, following `template/CONVERT-AGENT-TO-PORTABLE.md`."

This is a generalized version of the process used to convert the Cisco Catalyst Center Health
Triage Agent — see `agents/Cisco/catalyst-center-health/` in this repo for a fully worked, tested
example of every step below.

**Scaffolding:** copy this whole `template/` directory to `agents/<family>/<agent-slug>/` (or
just `agents/<agent-slug>/` if there's no family grouping). Every file comes along, including
`README.md` — that becomes the new agent's own human-facing setup doc (distinct from `AGENTS.md`,
which orients an AI coding agent working in the folder). Fill in every `{{PLACEHOLDER}}` in every
copied file or remove it; don't leave any behind.

---

## What "portable" means here

A folder that any MCP-capable AI coding tool (Claude Code, Codex, Cursor, a Bedrock agent, etc.)
can pick up and run **without Itential**, using the exact same underlying tools — plus a thin
translation layer that lets the same definition deploy back onto FlowAI. Not every agent can be
made fully portable (see Step 3) — the point is to make the portable *fraction* explicit and
tested, not to force everything.

## Step 0 — Platform API check (do this first, every time)

Before anything else, confirm which API surface the target platform actually uses. Do not assume
the `flowagent` skill's documented `/flowai/*` endpoints work — on at least one confirmed
platform they 404 entirely. Quick check:

```bash
curl -s "$PLATFORM_URL/health/adapters" -H "Authorization: Bearer $TOKEN"   # control: should 200
curl -s "$PLATFORM_URL/flowai/agents" -H "Authorization: Bearer $TOKEN"     # the thing being tested
```

If the second call 404s, use `jq '.paths|keys[]|select(contains("agent"))' openapi.json` to find
the real surface, and consult the compatibility table now embedded in `itential-builder:flowagent`'s
own `SKILL.md` (API Reference section). Record which surface this platform uses in
`itential/agent.spec.md` Section 0 of the output — don't make the next person rediscover this.

## Step 1 — Pull the live agent definition

Find it (name search, or list agents in the target project) and pull its full record: name,
description, `instructions` (or `messages` on older API), `provider`/`llm` config, and — most
important — its full `tools[]` list with `referenceId`s.

```bash
GET /agent-project-service/agents/{agentId}          # newer API
# or
GET /flowai/agents/{agent_id}                        # older API
```

If you get a `403 Forbidden: ... does not have read rights`, the service account making these
calls needs to be added as a **member** of the agent's project — a platform-wide role is not
sufficient; FlowAI project access is a separate ACL. Ask a project owner to add you (viewer is
enough for this step).

## Step 2 — Classify each tool

For every entry in `tools[]`, resolve what it actually is:

| `referenceId` pattern | What it is | Portable? |
|---|---|---|
| `gatewayService:<cluster>:python-script:<name>` wrapping an MCP tool call | A thin wrapper around an external MCP server | **Yes** — pull the wrapper's source (repo it points to), find the MCP server it calls and how |
| `gatewayService:<cluster>:<type>:<name>` running real device/API logic (Ansible, Python, OpenTofu) with no MCP involved | A genuine IAG automation | Partially — the *logic* can be documented as a skill, but it isn't already MCP-shaped; consider wrapping it as one if reuse outside Itential matters |
| `<adapter>//<method>` (adapter tool) | A Platform adapter method (ServiceNow, NetBox, etc.) | Often **yes** if an MCP server already exists for that system (many do — check first) |
| A workflow reference | Itential-native orchestration | **No** — document it as Itential-specific in `itential/agent.spec.md`, don't force a portable equivalent |

If a `gatewayService:*` tool's `referenceId` doesn't resolve via `/tools` (empty result), the
Gateway that hosted it may be disconnected from this platform tenant, or the calling account
lacks access to it — check `GET /gateway_manager/v1/gateways` directly
(`connection_status` and `groups` ACL) rather than assuming the tool never existed.

## Step 3 — Scaffold the folder

Copy this template directory to `agents/<agent-slug>/` and fill in:

| File | Source of truth |
|---|---|
| `README.md` | The agent's own setup/quick-start doc for a human: which `.env` variables it needs, step-by-step deploy, running it without Itential. The root `README.md` links here rather than repeating agent-specific detail — keep the split that way |
| `AGENTS.md` | The agent's purpose, in plain language, for an AI coding agent working in this folder — write this fresh, don't just restate `instructions`. Distinct from `README.md`: orientation vs. setup |
| `skills/<skill-name>/SKILL.md` | Generalize `instructions` into reusable procedure + an explicit honesty/edge-case table (see the worked example — don't skip this; it's what makes the skill safe to reuse) |
| `mcp/servers.json` + `INSTALL.md` | Only if Step 2 found MCP-backed tools. One entry per distinct MCP server (an agent may use more than one) |
| `itential/agent.spec.md` | The full FlowAI payload (verbatim `instructions`, `provider`, `tools[]`) **plus a Section 0 recipe** — the exact working request sequence, so the spec is self-sufficient even if `itential-builder:flowagent`'s own docs drift again |
| `tests/missions/*.json` | Run each tool directly first (per the `flowagent` skill's own Step 5 guidance), capture real input/output, before wiring anything into an agent |

**Genericize as you go — this is not optional.** The source agent you're converting has a real
platform URL, project ID, Gateway cluster name, and provider/model IDs baked into its live
record. None of those belong in the portable spec as literal values — replace them with
placeholders (`$PLATFORM_URL`, `$PROJECT_ID`, `$GATEWAY_CLUSTER`, "any Claude Sonnet-class
provider profile") throughout `itential/agent.spec.md`'s Section 0 recipe, tool `referenceId`s,
and Overview table, so the spec deploys on *any* Itential Platform + Gateway, not just the one you
happened to reverse-engineer it from. Keep the real values you captured during conversion as
labeled evidence (an "example run" in `tests/`, or a short "Provenance" note at the end of the
spec) — that's valuable proof it actually works — but don't let them leak into the sections
someone else's build will literally copy into a payload.

Note this cuts against Step 0's advice to "record which surface this platform uses" — record the
*API shape* (which endpoints, which fields) as reusable knowledge, but not *this platform's own*
hostname/project/cluster as if it were required.

## Step 4 — Document the Gateway wrapper build, even if you don't need to run it yourself

Write this section into `itential/agent.spec.md` (or `mcp/INSTALL.md`) **unconditionally** — don't
skip it just because the wrapper services already exist in the environment you're converting
from. Whoever picks up this folder next may be starting from zero: no MCP server running, no
Gateway wrapper services, nothing. If the only build steps that exist are the ones that happened
to work in your environment, the folder isn't actually portable yet, no matter how clean the
spec's instructions are.

Registering an MCP server on Gateway does **not** automatically make its tools visible to
FlowAI on every build (behavior has been observed to vary — see the worked example's
`itential/agent.spec.md` for how to check whether your Gateway build auto-bridges MCP tools or
needs an explicit wrapper). Document, generically, however it needs to work for this MCP server:

1. `iagctl mcp server add <name> <url-or-command>` — confirm live: `iagctl mcp tool list <name>`
2. Write one wrapper script using the official MCP Python SDK (`streamablehttp_client` +
   `ClientSession` for HTTP transport — don't hand-roll the JSON-RPC/session handshake, it's
   easy to get subtly wrong). **Omit unset decorator fields** rather than forwarding them as
   empty strings — IAG sends every declared field as `--key=value` even when unset, and typed
   MCP schemas reject `''` for int/bool/array fields.
3. Push the script + `requirements.txt` to a git repo Gateway can clone (local/file:// repos are
   not supported — needs a real remote).
4. `iagctl create repository` / `create decorator` (schema = the MCP tool's real `input_schema`,
   simplified — drop `anyOf`/`null` wrapping) / `create service python-script` per tool.
5. Test each with `iagctl run service python-script <name> --set <field>=<value>` before wiring
   into an agent.

## Step 5 — Round-trip verification (don't skip)

1. Confirm all tools discoverable: `GET /tools?referenceIds=<all your referenceIds>` → count
   matches. **This is necessary but not sufficient** — it only proves the tools exist, not that
   the instructions call them by the right name. Also diff every `api_*`/tool-name token
   mentioned in the `instructions` text against `tools[].lastKnownName`. A mismatch here can crash
   the agent outright (`Unknown sanitized tool name`, zero tool calls) the moment the model tries
   to use the wrong name. Don't assume the original agent's instructions are internally consistent
   just because it's already live.
2. Create a **new**, differently-named test agent from `itential/agent.spec.md`'s payload.
3. Run it with no arguments, poll to completion, read the final answer.
4. Compare against `tests/missions/*.json`'s expected output.
5. **Delete the test agent.** Don't leave test agents live in a shared project.
6. If you have MCP-capable tooling locally (Claude Code, Codex), also run the `SKILL.md`
   procedure natively — no Itential involved — and confirm the same answer. This is the actual
   portability proof, not just "the FlowAI version works."
7. Write a test report to `tests/` documenting both runs.

## Known gotchas (found the hard way — don't rediscover these)

- **Skill and MCP config edits don't hot-reload.** Both load once per Claude Code session; a fix
  to a `SKILL.md` or a new `.mcp.json` needs a session reload to take effect, not just a
  re-invocation.
- **Platform role ≠ project access ≠ Gateway access.** These are three separate ACL layers on at
  least this platform version. A 403 tells you *that* access is missing, not *which* layer.
- **`terminationCallbackSignature` on `run-agent`** is documented as optional but a request
  omitting it fails validation in practice on the newer API — always send a placeholder object.
- **`GET .../sessions/{id}/messages` paginates with a small default limit** that silently
  truncates multi-iteration runs (observed: 11 of 21 real events returned with no `limit` param).
  Always pass `?limit=200` (or higher) before concluding a run has no final answer — the "missing"
  `inference-succeeded` event is very likely just off the end of page one, not actually absent.
- **Agent `DELETE` is project-scoped, not agent-scoped**, on this API surface:
  `DELETE /agent-project-service/projects/{projId}/agents/{agentId}` works;
  `DELETE /agent-project-service/agents/{agentId}` (mirroring the `GET` shape) 404s.
- **A hard-failed session (`FAILED`, `errorCategory: "inference_failure"`) can still mean the
  agent's *design* is fine** — check whether the error is a tool-name mismatch (see Step 5.1)
  before concluding the agent itself needs a rework. Reproduce the failure with the verbatim
  original instructions first so you have a documented before/after, rather than fixing blind.
