# {{AGENT_NAME}} — FlowAI Agent Spec

A deployable FlowAI agent definition. Nothing below should be tied to any specific Itential
Platform instance, project, Gateway cluster, or provider — every value that's specific to a
deployment belongs in this repo's root `.env` (see `.env.example`), referenced here as a
placeholder (`$PLATFORM_URL`, `$PROJECT_ID`, `$GATEWAY_CLUSTER`, etc.), never hardcoded. See
"Provenance" at the end for where this definition originally came from, if it was reverse-engineered
from a real example.

**Before filling this in, run Step 0 of `../../../template/CONVERT-AGENT-TO-PORTABLE.md`** —
confirm whether this platform uses the classic `/flowai/*` API or the newer
`agent-project-service` / `agent-session-manager` / `model-registry-service` / `/tools` surface.
Everything below assumes you've done that and know which one applies here.

---

## 0. Deployment recipe

Don't just copy `itential-builder:flowagent`'s own docs verbatim — confirm each call actually
works against a real platform first, then paste the real, working version here, parameterized so
it reads from `.env` rather than any one platform's literal values. This section existing at all
is what makes this spec self-sufficient even if the skill's own reference drifts.

If this agent needs new variables beyond `PLATFORM_URL`/`CLIENT_ID`/`CLIENT_SECRET`/`PROJECT_ID`/
`GATEWAY_CLUSTER` (already in the root `.env.example`), add them there too — don't invent a
parallel, undocumented env var.

```bash
# Pulls PLATFORM_URL, CLIENT_ID, CLIENT_SECRET, PROJECT_ID, GATEWAY_CLUSTER (and any
# agent-specific vars you added to .env.example) from .env.
set -a; source .env; set +a

# 1. Auth
{{exact working auth call for this platform — oauth client_credentials or /login}}

# 2. Confirm tools are live before wiring them into an agent
{{exact working tool-discovery call, using $GATEWAY_CLUSTER in referenceIds — expect N; if 0,
  see Section 2's wrapper-service build steps}}

# 3. Create — payload is Section 1+3 of this doc assembled; tools[] from Section 2's table
{{exact working create-agent call, using $PLATFORM_URL/$PROJECT_ID}}

# 4. Run
{{exact working run call}}

# 5. Poll
{{exact working poll call}}

# 6. Read the answer
{{exact working call + which field actually holds the agent's final text — use a generous
  page-size param if the API paginates; a small default can silently truncate multi-iteration runs}}

# 7. Delete a test agent when done
{{exact working delete call — confirm whether DELETE is project-scoped or agent-scoped on this
  platform; don't assume it mirrors the GET/POST shape}}
```

**Preconditions this recipe assumes:** {{list them — GBAC role needed on $PROJECT_ID, Gateway
connection/ACL group for $GATEWAY_CLUSTER, anything else that isn't obvious from the calls alone}}

---

## 1. Overview

| Field | Value |
|---|---|
| Agent name | `{{AGENT_NAME}}` |
| Description | {{description}} |
| Project (namespace) | any FlowAI project you own — referred to as `$PROJECT_ID` throughout |
| Operators | whatever operator group(s) fit your org, or none |
| LLM provider profile | {{describe generically — e.g. "any Claude Sonnet-class Anthropic model configured on your platform" — don't hardcode a profile/model UUID from the platform you authored this on}} |
| Input schema | {{paste the real inputSchema — most triage-style agents take none}} |

---

## 2. Tools

| # | referenceId | lastKnownName | Portable? (see Step 2 of the playbook) |
|---|---|---|---|
| 1 | `gatewayService:$GATEWAY_CLUSTER:python-script:{{name}}` | `{{name}}` | {{yes/no + which MCP server if yes}} |

{{If any tool doesn't resolve via /tools, document what you checked and what the actual blocker
was (disconnected Gateway vs. ACL vs. genuinely deleted) — as a general troubleshooting note, not
as "this platform's Gateway was disconnected on this date," which won't be true for the next
person's deployment.}}

### 2.1 Building the wrapper services (if MCP-backed)

{{If Step 2 of the playbook classified these tools as MCP-wrapper tools, document the generic
wrapper-build recipe here — do this even if the wrapper services already exist in whatever
environment you're authoring this from. Whoever deploys this next may be starting from zero:
- The wrapper script itself (parameterized by env vars, so one script can back every tool on the
  MCP server — see `../../catalyst-center-health/itential/agent.spec.md` Section 2.1 for a worked
  example you can adapt)
- Instructions to push it to **their own** git repository (Gateway needs a real remote — local/
  `file://` repos aren't supported), not a link to a personal repo of yours
- The `iagctl create repository` / `create decorator` / `create service python-script` sequence,
  generalized with `{{tool name}}` placeholders
- How to verify each one (`iagctl run service python-script <name> --set <field>=<value>`) before
  wiring it into an agent}}

---

## 3. Instructions (system prompt)

```
{{paste the EXACT instructions field, don't paraphrase — this is what actually runs. If the
source agent's instructions have any bugs (wrong tool name, truncated text, etc.), fix them here
— this section should be the clean, working version, not a warts-and-all transcript. If you want
to preserve the original for the record, put it in Provenance at the end, not here.}}
```

This should be functionally identical to `../skills/{{SKILL_NAME}}/SKILL.md` — if they diverge,
one of them is wrong; figure out which and fix it, don't maintain two different versions of the
same procedure.

---

## 4. Related agents

{{Table or short list of sibling agents, if this one is part of a family — helps future readers
understand scope boundaries between them. Link by relative folder path, not by ID — IDs are
specific to whatever platform they happened to exist on.}}

---

## 5. Acceptance criteria for a deployed agent

1. Create call succeeds with this name/description/provider/instructions/inputSchema.
2. All tools resolve via `/tools` (or platform equivalent) before agent creation.
3. A run against real/live data produces output matching `../tests/missions/*.json`.
4. A failure case (unreachable tool, empty result, credential error, permission error) produces
   an honest stated failure — not a false "everything's fine."

---

## Provenance

{{Optional. If this spec was reverse-engineered from a real live agent, note that here — platform
type, roughly when, what was found — without baking that platform's specific hostname/project/
cluster into the sections above. If you captured a real verification run during authoring, link
it here and in `../tests/`, clearly labeled as one example environment's evidence, not a
requirement.}}
