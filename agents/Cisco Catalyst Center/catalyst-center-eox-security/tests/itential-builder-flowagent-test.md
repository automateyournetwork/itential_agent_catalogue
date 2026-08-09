# Test: Deploying via the platform API, from `agent.spec.md`

**Example run, one specific test environment** — the platform, project, cluster, and device names
below are that environment's own values, not requirements. Substitute your own
`$PLATFORM_URL`/`$PROJECT_ID`/`$GATEWAY_CLUSTER` per `agent.spec.md` Section 0; your run will show
your own Catalyst Center controller's real devices.

**Source:** `agents/Cisco/catalyst-center-eox-security/itential/agent.spec.md`, Section 0
**Result: PASS.** Clean run, zero failed calls, correct output.

## Preconditions

- The 12 Gateway wrapper services (`catalyst-center_api_getEoXSummary` and 11 others) already
  exist on cluster `john_capo_cluster` and are discoverable via `/tools`.
- Service account has editor/owner GBAC role on the project, and Gateway `john_capo_cluster` is
  connected with an ACL entry the account belongs to.

## Steps executed

1. **Verify tools** — `GET /tools?referenceIds=<12 refs>` → `total: 12`, all `active: true`.
2. **Create agent** — `POST /agent-project-service/projects/{projId}/agents` with the payload
   assembled directly from `agent.spec.md` Section 1+2+3, named
   `TEST-DELETE-ME Catalyst Center EoX Security Portable Verify` → `200`, agent id
   `041ae07d-9221-4447-b562-88124406a733`.
3. **Run** — `POST run-agent` with `{"agent": "<id>", "inputs": {}}` → session
   `39b035a6-c5fd-4561-9125-9a624e9fa5c0`, `RUNNING`.
4. **Poll** — `GET /agent-session-manager/sessions/{sessionId}` until `status: COMPLETE`
   (~63s, 13 polls at 5s intervals).
5. **Read result** — `GET .../messages?limit=200` (the default page size can truncate
   multi-iteration runs — use `limit=200`), last `inference-succeeded` event.
6. **Delete** — `DELETE /agent-project-service/projects/{projId}/agents/{id}` (project-scoped,
   not agent-scoped).

## Result

`totalToolCallCount: 14`, `durationMs: 63154`, `totalInputTokens: 36371`,
`totalOutputTokens: 3087`.

Against the live sandbox (sw1-sw4, Catalyst 9000 C9KV-UADP-8P, IOS-XE 17.12.1prd9):

- 4 total managed devices, 0 hardware EoX alerts, 4 software EoX alerts — all four on bulletin
  `EOL15518` (IOS-XE 17.12.x): end-of-sale/last-ship 2025-03-30 (already passed),
  end-of-security-support/end-of-life 2028-03-29.
- `api_getSecurityAdvisoryNetworkDevices` and `api_getCountOfNetworkBugDevices` both returned
  HTTP 403 for this service account's Catalyst Center role. The agent correctly surfaced this as
  a finding rather than silently reporting zero advisories/bugs: "This is itself a risk finding —
  if these APIs are inaccessible, this fleet is not being monitored for active CVEs or known
  defects."
- All 4 devices assigned risk tier Medium (end-of-sale passed, end-of-life not yet reached,
  PSIRT/bug status unknown rather than assumed clean).
- No compounding-risk devices reported, correctly, since PSIRT/bug cross-referencing was
  impossible without that data — the agent said so explicitly rather than guessing.

A summary of this same run is also in `../itential/agent.spec.md`'s "Provenance" section.

## What this proves

The instructions run cleanly end-to-end against live data, and the agent's honesty discipline
held under a real permission failure it didn't cause — it named the 403s as a finding instead of
collapsing them into "0 bugs, 0 advisories."

## Cleanup

Test agent (`041ae07d-9221-4447-b562-88124406a733`, "TEST-DELETE-ME Catalyst Center EoX Security
Portable Verify") deleted after this run. Project restored to its original 3 agents.
