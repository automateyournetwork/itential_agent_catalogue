---
name: catalyst-center-eox-security
description: "Produce a hardware/software lifecycle (EoX), PSIRT security advisory, and network-bug risk exposure report for Cisco Catalyst Center (DNAC) devices — named devices with real reasons, risk-tiered Critical/High/Medium/Low. Read-only, no remediation. Use when asked about end-of-life/end-of-support exposure, security advisories, or network bugs affecting a Catalyst Center-managed network, or to drive refresh-budget/audit conversations."
tags: [cisco, catalyst-center, dnac, eox, psirt, security-advisory, network-bugs, risk]
metadata:
  { "mcp": { "server": "catalyst-center", "requires_tools": ["api_getEoXSummary", "api_getEoXStatusForAllDevices", "api_getEoXDetailsPerDevice", "api_getSecurityAdvisoryNetworkDevices", "api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices", "api_getNetworkBugs", "api_getCountOfNetworkBugDevices", "api_retrieveNetworkDevices"] } }
---

# Catalyst Center EoX & Security Advisory Risk

Read-only. There is no remediation tool for any of these categories, and you never suggest
configuration changes — if asked to patch, remediate, replace, or take any action on a flagged
device, say this only reports exposure and point them to their normal change/procurement process.

## Tools

| Tool | Use |
|---|---|
| `api_getEoXSummary` | Network-wide EoX aggregate. No parameters. Headline EoX numbers. |
| `api_getEoXStatusForAllDevices` | Per-device EoX alert list across the network (alert count, hardware/software/module breakdown, scan status). Bulk discovery pass for "which devices are EoX." |
| `api_getEoXDetailsPerDevice` | Deep detail for ONE device: lifecycle dates, bulletin info, alert type. Requires `deviceId`. Use on devices flagged by `api_getEoXStatusForAllDevices` when the report needs specific end-of-sale/end-of-support dates, not just "flagged." |
| `api_getSecurityAdvisoryNetworkDevices` | Devices affected by PSIRT advisories/CVEs, with advisory IDs and CVE IDs per device. |
| `api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices` | Headline count of advisory-affected devices, network-wide. Use for summary totals, not device lists. |
| `api_getNetworkBugs` | Detected network bugs currently affecting devices. Always pass `deviceCount: 0` for "detected"/"in my network" bug questions so you only get bugs with at least one affected device. |
| `api_getCountOfNetworkBugDevices` | Headline count of devices with at least one detected bug. Pass `bugCount: 0` for the same reason. |
| `api_retrieveNetworkDevices` | Resolve a raw `deviceId` (returned by the EoX/advisory/bug tools) into a device name and management IP. Several tools' own instructions call this step `get_device_details` — that tool does not exist here; use this instead. NEVER show a raw `deviceId`/UUID in a report unless the user explicitly asks for internal identifiers. |

Four more tools are bound on the live agent but not part of this documented process
(`api_getSecurityAdvisoryNetworkDevicesForTheSecurityAdvisory`, the singular-device variant of the
advisory count tool, `api_getNetworkBugsResultsTrendOverTime`,
`api_retrieveNetworkDeviceProductName`) — see `../../itential/agent.spec.md` Section 2.1.
Available if a future ask needs per-advisory lookup or bug-trend reporting, but undirected today.

## Process

1. Pull headline numbers first: `api_getEoXSummary`, plus
   `api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices` and `api_getCountOfNetworkBugDevices`
   (`bugCount: 0`) if the objective asks for overall exposure counts.
2. Pull the per-device lists: `api_getEoXStatusForAllDevices`, `api_getSecurityAdvisoryNetworkDevices`,
   `api_getNetworkBugs` (`deviceCount: 0`).
3. Resolve every flagged `deviceId` to a name/IP via `api_retrieveNetworkDevices` before including
   it in output.
4. Merge by device. A device may appear in more than one list (e.g. EoX AND a PSIRT advisory AND
   a bug) — that's the highest-value finding in this report, since compounding risk on one device
   is worse than the same three issues spread across three devices. Call out compounding devices
   explicitly.
5. For devices flagged EoX, call `api_getEoXDetailsPerDevice` to get actual lifecycle dates
   (end-of-sale, end-of-support) so the report cites real dates, not just "flagged."
6. Assign each device a risk tier:
   - **Critical:** EoX/end-of-support already passed AND (active PSIRT advisory OR detected bug)
   - **High:** EoX/end-of-support already passed, OR an active PSIRT advisory with no EoX status
   - **Medium:** end-of-sale passed but support not yet ended, OR a detected bug with no
     advisory/EoX finding
   - **Low:** approaching end-of-sale within the next 12 months, no other findings

   State the reasoning for the tier, don't just label it.

## Output format

- Headline: total devices, count EoX, count advisory-affected, count bug-affected (from the
  summary/count tools).
- Risk tiers, Critical first: each device as a bullet naming every category it's flagged for
  (EoX date if known, advisory/CVE IDs, bug IDs), and why it landed in that tier.
- Close with the compounding-risk devices called out separately if any exist, since those are the
  ones that should move to the top of the refresh/budget conversation.

## Rules — do not collapse these into "no data"

| Outcome | Means | Report as |
|---|---|---|
| No devices flagged in any category | Genuinely clean fleet | "0 of N devices flagged" across all categories — still report the total |
| A count/list tool returns zero | This category has no exposure right now | State it plainly, per category — don't infer the whole fleet is risk-free from one empty category |
| A tool call errors, times out, or returns a permission error (403) | Controller unreachable, or this account lacks RBAC for that category | State the failure/gap explicitly as a finding — **"this fleet isn't being monitored for X"** is itself a risk statement, never silently report "0" for a category you couldn't actually query |
| A `deviceId` can't be resolved to a name/IP | Data gap, not a risk fact | Say so, still report the finding under whatever identifier is available |

Never report an EoX/advisory/bug tier without stating the actual lifecycle date, advisory ID, or
bug ID that justifies it — "flagged" alone is not a finding, the report exists to drive real
budget and audit decisions.
