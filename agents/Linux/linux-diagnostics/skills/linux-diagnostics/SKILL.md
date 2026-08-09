---
name: linux-diagnostics
description: "Run comprehensive Linux host health diagnostics (disk, memory, CPU, swap, inodes, services, failed systemd units, OOM events, zombie processes) and classify each host OK/WARNING/CRITICAL. Read-only — never modifies target hosts."
tags: [linux, diagnostics, infrastructure, health-check]
metadata:
  { "mcp": { "server": "linux-diagnostics", "requires_tools": ["run_diagnostics"] } }
---

# Linux Diagnostics

Read-only. `run_diagnostics` only executes read commands on target hosts (`cat`, `df`,
`systemctl status`/`--failed`, `journalctl -k`, `ps`) — never call it expecting it to fix
anything, and never pair it with a remediation tool in the same agent without a human approval
gate, the same discipline the Cisco Catalyst Center Remediation agent uses for writes.

This skill produces a **report only**. Delivering that report by email, Slack, ticket, or any
other channel is orchestration specific to whatever platform/tool is running this skill — not
part of the portable procedure. An Itential FlowAI deployment of this same skill may wire that up
as a separate delegation step (see `../../itential/agent.spec.md` Section 4); a standalone MCP
client just returns the text.

## Tools

| Tool | Use |
|---|---|
| `run_diagnostics` | Runs the diagnostics collection across a target inventory group or host list. Returns raw per-host metrics — no classification. Requires `inventory` (an Ansible inventory group name or comma-separated host list, e.g. `"webservers"` or `"host1,host2,"`). This is the ONLY tool this skill uses. |

## Health thresholds

Apply these per host, per metric. A host is:
- **OK** — no threshold below breached, no anomalies.
- **WARNING** — at least one soft threshold breached.
- **CRITICAL** — at least one hard threshold breached, OR the host was unreachable, OR any OOM
  kill event occurred in the last 24 hours.

| Metric | WARNING | CRITICAL |
|---|---|---|
| Disk (per mount) | > 80% used | > 90% used |
| Memory (RAM) free | < 256 MB free | < 64 MB free |
| Swap used | > 50% used | > 90% used |
| CPU load average (1m ÷ core count) | > 2.0 | > 5.0 |
| Inodes (per mount) | > 80% used | > 90% used |
| Expected services | any expected service inactive | `sshd` not running |
| Failed systemd units | 1 or more in failed state | — |
| OOM kill events (last 24h) | — | any detected |
| Zombie processes | count > 0 | — |

A host that CRITICAL-fails on unreachability has none of the other metrics available — report it
as CRITICAL / "Host unreachable", don't attempt to infer or default the other fields.

## Process

1. Call `run_diagnostics` with `inventory` set to the requested scope (a specific group/host list
   if named in the objective; otherwise ask which inventory to target — this skill has no
   "default" scope of its own, unlike a live Itential deployment which may hardcode one).
2. For each host in the response:
   - If `reachable: false`, classify CRITICAL, reason "Host unreachable" (or whatever `reason`
     the tool returned), and skip the metric checks below for that host — there's nothing to
     apply thresholds to.
   - Otherwise, apply every threshold in the table above and record which ones were breached.
3. Assign the host's overall status as the worst of any individual metric's classification (a
   single CRITICAL metric makes the whole host CRITICAL, even if every other metric is OK).
4. Build the report grouped by status (CRITICAL hosts first), including which specific metrics
   triggered each classification — not just the final verdict.

## Output format

- Start with a one-line overall count: "X of Y hosts degraded" (degraded = WARNING or CRITICAL).
- Then a section per status tier (CRITICAL, then WARNING, then OK), each host as a bullet:
  "hostname — status: LEVEL, triggered by: <metric list with actual values>".
- For OK hosts, a single-line summary is enough (no need to list every clean metric).
- End with a "Needs attention first" line naming the 1-3 worst hosts, if any exist.
- This is your final output — do not attempt to email, Slack, or otherwise deliver it yourself
  unless the tool you're running under has its own delivery mechanism wired in separately.

## Rules — do not collapse these into "no data"

| Outcome | Means | Report as |
|---|---|---|
| All thresholds pass | Genuinely healthy host | "OK" with the metric values, not silence |
| `run_diagnostics` returns `reachable: false` | Host is down or unreachable via SSH, not "clean" | CRITICAL — "Host unreachable", never omit the host from the report |
| `run_diagnostics` returns `isError: true` with no `hosts` | The tool itself failed (bad inventory reference, playbook error) before reaching any host | State the tool failure explicitly, per the "raw" field's error detail — never report "0 of 0 hosts degraded" as if that meant a clean fleet |
| An inventory group/host name doesn't resolve | Ansible/inventory configuration gap, not a fact about host health | Say the inventory reference couldn't be resolved and name it; don't guess a substitute host name |

A "0 of 0 hosts degraded" headline with an empty `hosts` list is a **tool failure signature**, not
a clean bill of health — always check `isError` and the `raw` field before reporting zero findings.
