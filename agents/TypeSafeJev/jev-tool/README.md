# TypeSafe Jev — Gateway Tool (Phase 1)

Wraps TypeSafe AI's Jev / System One model (`POST https://api.typesafe.ai/v1/systemone`)
as a single Itential Automation Gateway (IAG) `python-script` service, so a
FlowAI agent (or a workflow) can call it as a **tool**, not as a Model
Registry LLM provider.

## Why a tool, not a Model Registry provider

Jev is not OpenAI-compatible: no `/chat/completions`, no `messages` array,
no free text out. Its native contract is `{state, model, questions} ->
{answers, usage}`, where `questions` is a map of typed decisions
(`choice` / `score` / `noul`) evaluated in parallel against `state`. Every
integration checked while researching this (TypeSafe's own docs, liteLLM's
pass-through, OpenRouter's SDK guide) preserves that native shape rather
than translating it -- there's no clean lossless mapping onto chat turns.

Itential's Model Registry providers (Claude/OpenAI/Ollama/Databricks) are
fixed adapters that all assume a `/chat/completions`-shaped backend -- the
Gateway's own `LlmInvoke` path hard-codes that call shape regardless of
provider (confirmed empirically debugging an Ollama provider profile; see
`reference-gateway-ollama-relay` memory). There's no "custom schema"
provider slot to register Jev into directly.

So: Jev becomes a **Gateway tool** a chat-based agent can call mid-conversation
for fast, cheap, calibrated structured sub-decisions (routing, triage,
scoring) -- not a swap-in replacement for the agent's own LLM.

## What's here

- `tools/jev_evaluate.py` -- the IAG python-script service. Pure stdlib
  (`urllib`), no `requirements.txt` needed.
- `tools/_util.py` -- shared `--key=value` CLI-arg parser (same pattern as
  `../../CiscoAntares/antares-vuln-scanner/tools/_repo_utils.py`).
- `decorators/typesafe-jev_evaluate.json` -- input-validation schema for the
  service (`state`, `questions`, `model`).

## Output shape

```json
{"isError": false, "model": "jev-1.13.0", "answers": {"...": {...}}, "usage": {...}}
```
or, on any failure (bad input, network error, non-2xx from TypeSafe):
```json
{"isError": true, "error": "..."}
```
A network failure is always `isError: true`, never a silently-empty
`answers` -- don't let "couldn't reach Jev" look like "Jev evaluated and
said no" (same trap as the Ollama-down case in the CWE pipeline).

**Assumption to verify:** the script sends `Authorization: Bearer
<TYPESAFE_API_KEY>`. TypeSafe's docs didn't confirm the exact auth header
at the time this was written -- confirm against your TypeSafe dashboard/
quickstart before the first live call; swap for `X-API-Key` in
`jev_evaluate.py` if that's what it actually expects.

## Testing directly (no Itential needed)

```bash
cd tools
export TYPESAFE_API_KEY=sk-...
python3 jev_evaluate.py \
  --state='Help! My payouts have been failing for 3 days.' \
  --questions='{"urgent":{"type":"noul","instructions":"Is this urgent?"}}'
```

## Registering on the Gateway (Phase 1)

```bash
# 1. Repository (points at this same GitHub repo -- reuses the same
#    pattern as antares-vuln-scanner, one repo entry, --filename per service)
iagctl create repository typesafe-jev \
  --url https://github.com/automateyournetwork/itential_agent_catalogue \
  --reference main

# 2. Decorator (input schema)
iagctl create decorator typesafe-jev_evaluate \
  --schema @decorators/typesafe-jev_evaluate.json

# 3. Secret -- run this yourself in an interactive terminal so the key
#    never lands in chat/logs (same reason `iagctl login` can't be run for
#    you -- see the itential-builder:iag skill)
iagctl create secret typesafe-api-key --prompt-value

# 4. Service
iagctl create service python-script typesafe-jev_evaluate \
  --repository typesafe-jev \
  --filename "agents/TypeSafeJev/jev-tool/tools/jev_evaluate.py" \
  --decorator typesafe-jev_evaluate \
  --secret name=typesafe-api-key,type=env,target=TYPESAFE_API_KEY \
  --description "TypeSafe Jev structured-decision evaluation (POST /v1/systemone)"

# 5. Smoke test
iagctl run service python-script typesafe-jev_evaluate \
  --set state='Help! My payouts have been failing for 3 days.' \
  --set questions='{"urgent":{"type":"noul","instructions":"Is this urgent?"}}'
```

Then, on the platform side, activate it so FlowAI can discover it:
```
POST /tools/discover
```
A freshly-created service/decorator can show up on `/tools` as
`active: false` until this is called -- a known gotcha, not a sign
something's broken.

## Next (Phase 2, not yet built)

Build a FlowAI agent that calls this tool alongside pyATS-based tools --
e.g. Jev triages/scores parsed pyATS output fast and cheap, the agent's own
LLM handles the open-ended reasoning and narration around it. Not started
yet; this folder only covers the Gateway tool + registration.
