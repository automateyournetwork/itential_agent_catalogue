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

## Confirmed `questions` schema per type (2026-09-21, real API calls)

- **`noul`**: `{"type": "noul", "instructions": "..."}` -> answer
  `{"type": "noul", "noul": <0..1 probability>}`.
- **`choice`**: `{"type": "choice", "instructions": "...", "criteria": {"<option>": "<description>", ...}}`
  (criteria is an OBJECT keyed by option name) -> answer includes `choice`,
  `probabilities` (per option), `confidence`.
- **`score`**: `{"type": "score", "instructions": "...", "criteria": [...]}`
  (criteria is an ORDERED LIST of level descriptions, index 0 = lowest --
  **not** an object, and **not** a field called `scale` despite that being
  a reasonable guess; the API's own 422 error names the missing/wrong field
  exactly, worth doing one deliberate bad call first to get the real error
  instead of guessing twice) -> answer includes `score` (weighted position),
  `confidence`, `legend` (index -> description), `probabilities` (per index).

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

**Auth header confirmed working:** `Authorization: Bearer <TYPESAFE_API_KEY>`
-- verified against the live API 2026-09-21 (see Provenance below).

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
#
#    IMPORTANT first-time-only step: `iagctl create secret` encrypts the
#    value CLIENT-SIDE using [secrets].encrypt_key_file in your local
#    ~/.gateway.d/gateway.conf, and the gateway5 SERVER decrypts it at run
#    time using its own GATEWAY_SECRETS_ENCRYPT_KEY_FILE env var -- these
#    are two independent key files that must contain IDENTICAL bytes, or
#    every run fails with "cipher: message authentication failed" (not a
#    permissions error, and not caught at `create secret` time). If this is
#    the first local secret ever created against this Gateway, see
#    `reference-itential-gateway-secrets-key-mismatch` memory / the
#    Provenance section below for how the client and server key files were
#    generated and synced for this deployment.
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

---

## Provenance

Registered and verified end-to-end 2026-09-21 against
`itential-se-poc-dev01.trial.itential.io`, Gateway cluster `john_capo_cluster`
(container `gateway5`). Real API key from `.env`'s `JEV_API_KEY`.

- `referenceId`: `gatewayService:john_capo_cluster:python-script:typesafe-jev_evaluate`
  -- confirmed `active: true` on `GET /tools?name=typesafe` after
  `POST /tools/discover`. (That discover call's overall response was
  `success: false` with an unrelated `E11000 duplicate key` error on a
  pre-existing workflow doc during `loadDbTools:workflows` -- a pre-existing
  platform data issue, not caused by or blocking this tool's registration.)
- Live smoke test result: `{"isError": false, "model": "jev-1.13.0",
  "answers": {"urgent": {"type": "noul", "noul": 0.89}}, "usage":
  {"input_tokens": 282, "output_tokens": 20}}`, `elapsed_time: 4.78s`
  end-to-end through the Gateway (TypeSafe's own claimed ~100ms is just the
  model call; the rest is IAG python-script process/venv overhead per
  invocation -- worth knowing before assuming Jev itself is slow).
- **First-secret-ever gotcha hit and fixed:** this was the first
  `iagctl create secret` ever run against this Gateway deployment. `gateway5`
  had no `GATEWAY_SECRETS_ENCRYPT_KEY_FILE` configured at all (server-side
  decrypt failed outright: "can't decrypt service secrets without a
  GATEWAY_SECRETS_ENCRYPT_KEY_FILE"). Fixed by generating a key file
  (`openssl rand -base64 256`), copying it into the `gateway5-data` named
  volume at `/etc/gateway/gateway_secret.key` (persists across container
  recreates), and adding `GATEWAY_SECRETS_ENCRYPT_KEY_FILE:
  "/etc/gateway/gateway_secret.key"` to `gateway5`'s environment in
  `~/itential-dev-stack/docker-compose.yml` (done via a `-f` override file,
  since that repo's files are root-owned and not writable by the normal
  user account) and recreating just that one container (`docker compose -f
  docker-compose.yml -f <override>.yml --profile gateway5 up -d gateway5`).
  That alone wasn't enough: the client (`iagctl`, via `~/.gateway.d/
  gateway.conf`'s `[secrets] encrypt_key_file`) encrypts a local secret's
  value *client-side* before sending it, using its own key file -- a
  different, independently-generated key file than the one just placed on
  the server produced `cipher: message authentication failed` on every run.
  The real fix was copying the exact same key file to both places (client
  `~/.gateway.d/gateway_secret.key` and server
  `/etc/gateway/gateway_secret.key` inside `gateway5`, owned by `itential`
  uid 100 there, `chmod 400` both sides) and re-creating the secret after
  they matched. This will not recur for any *future* secret on this same
  Gateway now that both key files are in place and persisted -- only hit
  once, for the very first secret.
