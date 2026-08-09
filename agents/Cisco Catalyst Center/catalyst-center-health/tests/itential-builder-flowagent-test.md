# Test: Deploying via `itential-builder:flowagent`, from `agent.spec.md`

**Example run, one specific test environment** — the platform, project, cluster, and device names
below are that environment's own values, not requirements. Substitute your own
`$PLATFORM_URL`/`$PROJECT_ID`/`$GATEWAY_CLUSTER` per `agent.spec.md` Section 0; your run will show
your own Catalyst Center controller's real devices.

**Source:** `agents/Cisco/catalyst-center-health/itential/agent.spec.md`, Section 0
**Result: PASS.** Clean run, zero failed calls, correct output on the first attempt.

## Preconditions

- The 5 Gateway wrapper services (`catalyst-center_api_devices` and 4 others) already exist on
  cluster `john_capo_cluster` and are discoverable via `/tools` — built once, reused by every run.
- Service account has editor/owner GBAC role on the project, and is a member of a group with
  access to the Gateway (see `agent.spec.md` Section 0 preconditions).

## Steps executed

1. **Verify tools** — `GET /tools?referenceIds=<5 refs>` → `total: 5`, all `active: true`.
2. **Create agent** — `POST /agent-project-service/projects/{projId}/agents` with the payload
   assembled directly from `agent.spec.md` (name, `instructions`, `provider.profile`/`model`,
   `tools[].referenceId`) → `200`, agent created.
3. **Run** — `POST /agent-session-manager/sessions/run-agent` with `{"agent": "<id>", "inputs": {}}`
   → `200`, session returned immediately in `RUNNING` state.
4. **Poll** — `GET /agent-session-manager/sessions/{sessionId}` until `status: COMPLETE` (~17s).
5. **Read result** — `GET /agent-session-manager/sessions/{sessionId}/messages`, last
   `inference-succeeded` event.

## Result

```
0 of 4 devices degraded.

sw1 (10.10.20.175) — 10/10, 0 issues, REACHABLE
sw2 (10.10.20.176) — 10/10, 0 issues, REACHABLE
sw3 (10.10.20.177) — 10/10, 0 issues, REACHABLE
sw4 (10.10.20.178) — 10/10, 0 issues, REACHABLE

Needs attention first: None.
```

`totalToolCallCount: 1`, `durationMs: 16745`, `totalInputTokens: 12661`,
`totalOutputTokens: 593`. Matches `tests/no-args-happy-path.json` exactly.

## Why this works cleanly now

Earlier iterations of this exercise found the `itential-builder:flowagent` skill's own
documented API (`/flowai/*`) 404s on this platform, which uses a newer surface
(`agent-project-service` / `agent-session-manager` / `model-registry-service` / `/tools`). Two
fixes were made and are why this run required zero discovery or troubleshooting:

1. `agent.spec.md` Section 0 now contains the exact, verified-working request sequence for this
   platform directly — no dependency on the skill's own API reference being current.
2. The `itential-builder:flowagent` skill's `SKILL.md` was also patched with a compatibility
   note and endpoint-mapping table, for any agent build that doesn't already have a Section-0-style
   spec to follow.

## Cleanup

Test agent (`285bee93-e6c9-4e41-b96b-541498528e85`, "Portable Agent Reference Verification")
deleted after this run. Project restored to its original 3 agents.
