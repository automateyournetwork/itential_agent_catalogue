# Linux Diagnostics — Conversion Test Report

## What was actually verified live

A temporary test agent (`TEST - Linux Diagnostics Portability Verification (delete me)`,
`03016fe6-c514-46fd-a0e2-5a461069bd63`) was created directly in the real "Linux Operations"
FlowAI project, wired to the **actual production** `gatewayService:<cluster>:ansible-playbook:linux-diagnostics`
tool (not this repo's reconstruction), run to completion, and deleted afterward — a genuine
round-trip against live infrastructure, per the conversion playbook's Step 5.

It did not produce a clean diagnostics report. It surfaced something more useful for this
conversion: real internals of the production service that weren't documented anywhere else
accessible (see `tests/missions/invalid-inventory.json` for the full evidence trail):

- The tool's real parameter is a registered Automation Gateway **inventory reference**, not an
  arbitrary hostname — both guesses (`"demo-linux"`, `"all"`) 404'd with
  `Inventory '<value>' not found`.
- The real playbook path is `linux_patch_check/linux_diagnostics.yml`, confirmed from raw Ansible
  JSON-callback output captured in a third attempt that got further (empty inventory) before
  failing at a dynamic-inventory-resolution step (`ansible.builtin.add_host` + `from_json`).
- The agent under test handled the failure correctly at every step — it never reported a false
  "0 hosts degraded," it quoted the real tool error, and it asked for a valid inventory reference
  instead of guessing further.

**This is real, positive evidence for the agent's failure-handling behavior** (Section 5,
acceptance criterion 4), even though it's not evidence the reconstructed diagnostics logic in
`../ansible/linux_diagnostics.yml` / `../mcp/server.py` produces correct output — that logic was
never exercised against the real production tool, because the real tool's own inventory couldn't
be resolved from outside its Gateway.

## What was NOT verified live

- The reconstructed `run_diagnostics` MCP tool (`../mcp/server.py`) has not been run against a
  real Linux host. `tests/missions/happy-path.json` documents the *expected* shape based on the
  contract this folder implements, not an observed result — treat it as a contract test to write
  real assertions against once you have a test host, not as proof the reconstruction is correct.
- The Gateway wrapper-service build in `../itential/agent.spec.md` Section 2.2 has not been built
  or run via `iagctl` — it follows the exact same pattern already proven to work for the Cisco
  agents in this repo, but hasn't been independently confirmed for this specific tool.

## Why the gap exists, and how to close it

Getting further requires one of:
1. A real, SSH-reachable Linux host (or a small local VM/container) and an Ansible inventory file
   pointing at it, to actually run `../ansible/linux_diagnostics.yml` and confirm its output
   matches `../mcp/server.py`'s expectations end to end.
2. `iagctl` Gateway-admin credentials for the environment this was converted from, to pull the
   real `linux_patch_check` repository and either diff it against this reconstruction or replace
   the reconstruction outright (see `../mcp/INSTALL.md` Section 5).

Either would upgrade `happy-path.json` from "expected shape" to "observed, verified result," the
same status the Cisco family's test missions already have.
