# Antares-1B Vulnerability Scanner Agent — FlowAI Agent Spec

A deployable FlowAI agent definition. Nothing below is tied to any specific Itential
Platform instance, project, Gateway cluster, or provider — every value that's specific
to a deployment is a placeholder (`$PLATFORM_URL`, `$PROJECT_ID`, `$GATEWAY_CLUSTER`,
etc.). See "Provenance" at the end for a real worked example.

**API surface note:** this spec targets the `agent-project-service` /
`agent-session-manager` / `model-registry-service` / `/tools` API surface — see
`../../Cisco Catalyst Center/catalyst-center-health/itential/agent.spec.md`'s header
note if your platform's calls don't match what's below.

**Model note:** this agent is designed for Cisco's Antares-1B specifically, not any
general-purpose model. Antares-1B's model card lists general chat/instruction
following as **out of scope** — its actual training is a narrow, bounded terminal
loop over `grep`/`find`/`cat`-style operations for CWE vulnerability localization.
Do not point this agent at a different model expecting the same behavior; do not
point a general-purpose agent at Antares-1B expecting good general chat.

---

## 0. Deployment recipe

```bash
set -a; source .env; set +a

# 1. Auth
TOKEN=$(curl -s -X POST "$PLATFORM_URL/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "client_id=$CLIENT_ID" --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode "grant_type=client_credentials" | jq -r '.access_token')

# 2. Register the repo + 5 services on the Gateway (iagctl client, needs its own
#    `iagctl login admin` first — separate credential from the platform OAuth above)
iagctl create repository antares-vuln-scanner \
  --url https://github.com/automateyournetwork/itential_agent_catalogue --reference main

# repeat this service registration per tool — only the name/filename change
iagctl create service python-script antares-vuln_grep_repo \
  --repository antares-vuln-scanner \
  --filename "agents/Cisco Antares/antares-vuln-scanner/tools/grep_repo.py"
iagctl create service python-script antares-vuln_find_files \
  --repository antares-vuln-scanner \
  --filename "agents/Cisco Antares/antares-vuln-scanner/tools/find_files.py"
iagctl create service python-script antares-vuln_read_file \
  --repository antares-vuln-scanner \
  --filename "agents/Cisco Antares/antares-vuln-scanner/tools/read_file.py"
iagctl create service python-script antares-vuln_submit_vulnerable_files \
  --repository antares-vuln-scanner \
  --filename "agents/Cisco Antares/antares-vuln-scanner/tools/submit_vulnerable_files.py"
iagctl create service python-script antares-vuln_submit_no_vulnerability_found \
  --repository antares-vuln-scanner \
  --filename "agents/Cisco Antares/antares-vuln-scanner/tools/submit_no_vulnerability_found.py"

# confirm each runs cleanly before wiring into an agent
iagctl run service python-script antares-vuln_find_files --set pattern='*.py'

# 3. Confirm the 5 tools are FlowAI-discoverable
curl -s -G "$PLATFORM_URL/tools" --data-urlencode "name=antares-vuln" \
  -H "Authorization: Bearer $TOKEN" | jq '.total'   # expect 5

# 4. Create the agent — payload is Section 1+3 of this doc assembled
curl -s -X POST "$PLATFORM_URL/agent-project-service/projects/$PROJECT_ID/agents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @payload.json

# 5. Run (always async)
curl -s -X POST "$PLATFORM_URL/agent-session-manager/sessions/run-agent" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"agent": "<agent-id>", "inputs": {"cwe": "CWE-78: OS Command Injection"},
       "terminationCallbackSignature": {"location":"none","serviceName":"none","methodName":"none","identifier":"none"}}'

# 6. Poll and read the answer — see the Catalyst Center specs for the full
#    poll/read/delete recipe, identical on this surface.
```

**Preconditions:** your platform service account needs editor/owner GBAC on
`$PROJECT_ID`; `$GATEWAY_CLUSTER` needs `connection_status: connected`; and — new
for this agent — whoever runs the `iagctl create repository`/`create service` calls
needs their own `iagctl login admin` against the Gateway directly. That's a
separate credential from the platform OAuth client above; it's the Gateway's own
local admin account, not anything in `model-registry-service`.

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `Antares-1B Vulnerability Scanner` |
| Description | Locates a described CWE vulnerability class in a small bundled sample codebase, using Cisco Antares-1B's native grep/find/cat-style tool loop |
| Project (namespace) | any FlowAI project you own |
| LLM provider profile | an Ollama provider profile pointed at your own **BF16, unquantized** `antares-1b` build — see this folder's `README.md` for why quantization breaks this specific model |
| Input schema | `{"type":"object","additionalProperties":false,"required":["cwe"],"properties":{"cwe":{"type":"string"}}}` |

---

## 2. Tools

Exactly 5, all pure-Python (no shell-out, no subprocess — see `AGENTS.md` "Safety
design"):

| # | referenceId | lastKnownName | Purpose |
|---|---|---|---|
| 1 | `gatewayService:$GATEWAY_CLUSTER:python-script:antares-vuln_find_files` | `antares-vuln_find_files` | list files by glob pattern |
| 2 | `gatewayService:$GATEWAY_CLUSTER:python-script:antares-vuln_grep_repo` | `antares-vuln_grep_repo` | regex search across file contents |
| 3 | `gatewayService:$GATEWAY_CLUSTER:python-script:antares-vuln_read_file` | `antares-vuln_read_file` | read a file or line range |
| 4 | `gatewayService:$GATEWAY_CLUSTER:python-script:antares-vuln_submit_vulnerable_files` | `antares-vuln_submit_vulnerable_files` | terminate: report finding(s) |
| 5 | `gatewayService:$GATEWAY_CLUSTER:python-script:antares-vuln_submit_no_vulnerability_found` | `antares-vuln_submit_no_vulnerability_found` | terminate: report clean |

### 2.1 Why these are pure Python, not real shelled-out grep/find/cat

Cisco's own model card recommends running the model's shell commands inside an
ephemeral, network-disabled, resource-capped container per invocation — real
sandboxing for a real arbitrary-command surface. This spec sidesteps needing that
infrastructure entirely: `find_files`/`grep_repo`/`read_file` are hand-written
Python re-implementations of exactly the primitives the model needs, each
confined to the bundled `sample-repo/` directory via `tools/_repo_utils.py`'s
`safe_path()` (any path that would escape the sample root raises before touching
disk). There is no shell invocation anywhere in these scripts, so there is no
injection surface to sandbox against. If you later point this agent at an
arbitrary, larger real-world repository instead of the bundled sample, revisit
this — at that point Cisco's container-sandboxing guidance becomes load-bearing
again, not optional.

### 2.2 One repository, no separate wrapper repo needed

Unlike the Catalyst Center MCP-wrapper agents, there's no external MCP server
here — the tool scripts and the target sample codebase both live in this same
GitHub repository, side by side (`tools/` and `sample-repo/`). One
`iagctl create repository` call backs all 5 services; only `--filename` differs
per service.

---

## 3. Instructions (system prompt)

```
You are a security vulnerability localization agent. You have access to a small
codebase and a small set of terminal-style tools for exploring it. Your job is
to determine whether the codebase contains an instance of the vulnerability
class described below, and if so, exactly which file(s).

Tools you have:
- find_files(pattern, path) — list files under the repo matching a glob
  pattern (e.g. "*.py"). Use this to get oriented.
- grep_repo(pattern, path) — search file contents for a regex pattern across
  the repo, returning matching file/line/text. Use this to locate code that
  looks relevant to the vulnerability class (e.g. shell execution, string
  formatting into commands, unsanitized input).
- read_file(path, start_line, end_line) — read a file (or a line range of
  one) to confirm what a grep hit actually does before deciding.
- submit_vulnerable_files(files, reasoning) — call this ONCE, when you are
  confident, with the list of relative file paths that contain the
  vulnerability and your reasoning. This ends the task.
- submit_no_vulnerability_found(reasoning) — call this ONCE if, after a
  reasonable search, you find no instance of this vulnerability class. This
  ends the task.

Process:
1. Use find_files and/or grep_repo to locate code that could plausibly relate
   to the vulnerability class described below.
2. Use read_file to confirm what any candidate code actually does — a
   suggestive grep hit is not proof; confirm the actual data flow (does
   untrusted input actually reach the dangerous operation unsanitized?).
3. You have at most 15 tool calls total before you must submit. Work
   efficiently — don't re-read the same file twice or grep for near-duplicate
   patterns.
4. Call exactly one of the two submit tools to finish. Never finish without
   calling one of them.

Vulnerability to locate: {{cwe}}
```

This should be functionally identical to `../skills/antares-vuln-scan/SKILL.md` — if
they diverge, one of them is wrong; figure out which and fix it.

---

## 4. Related agents

Not part of the Cisco Catalyst Center family (`../../Cisco Catalyst Center/`) despite
living in the same GitHub repo and the same FlowAI project for now — those agents
call structured Catalyst Center APIs; this one exercises a fundamentally different
tool-calling shape (terminal-style exploration) because that's what its specific
model was trained on. Don't generalize patterns between the two families without
checking which shape actually applies.

---

## 5. Acceptance criteria for a deployed agent

1. Create call succeeds with this name/description/provider/instructions/inputSchema.
2. All 5 tools resolve via `/tools` before agent creation.
3. A run with `cwe: "CWE-78: OS Command Injection"` correctly identifies
   `diagnostics/network.py` via `submit_vulnerable_files`, with reasoning that
   references the actual unsanitized string interpolation into `os.popen`, not
   just "it mentions ping."
4. A run with an unrelated CWE (e.g. a vulnerability class genuinely absent from
   the sample repo) correctly calls `submit_no_vulnerability_found` rather than
   forcing a false positive onto an unrelated decoy file.
5. The agent never exceeds ~15 tool calls without submitting.

---

## Provenance

Built and tested end-to-end against `itential-se-poc-dev01.trial.itential.io`,
Gateway cluster `john_capo_cluster`, Ollama provider profile `Cisco Antares 1B`
running a locally-converted BF16 `antares-1b:latest` build. This spec followed two
earlier, harder-won findings from the same session: (1) the community F16 GGUF of
this model produces `@@@@@@@@@@...` garbage output due to Granite 4.0's hybrid
Mamba/attention architecture saturating in F16 — a from-scratch BF16 conversion is
required; and (2) a first attempt at reusing the Catalyst Center EoX agent's
12-tool, multi-stage business-report prompt against this model produced only 3 of
12 tool calls before trailing off mid-`<think>` block with no final report — a 1.8B
model tuned narrowly for vulnerability localization cannot reliably drive a long
generic-business-report tool sequence, which is why this agent's tool set and
prompt are deliberately narrow and bounded instead.
