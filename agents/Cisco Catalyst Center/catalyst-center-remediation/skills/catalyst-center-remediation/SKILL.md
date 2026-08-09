---
name: catalyst-center-remediation
description: "Find Cisco Catalyst Center (DNAC) devices out of compliance, explain exactly what's wrong, and propose a remediation for the one issue type this tool can fix (RUNNING_CONFIG drift). Never applies a fix without explicit human approval given in a later turn. Use when asked to find non-compliant devices, config drift, or to remediate compliance issues on a Catalyst Center-managed network."
tags: [cisco, catalyst-center, dnac, compliance, remediation, network]
metadata:
  { "mcp": { "server": "catalyst-center", "requires_tools": ["api_retrieveNetworkDevices", "api_getComplianceStatusCount", "api_getComplianceStatus", "api_getComplianceDetailCount", "api_getComplianceDetail", "api_complianceDetailsOfDevice", "api_complianceRemediation"] } }
---

# Catalyst Center Remediation

The account this runs as has **write access** via `api_complianceRemediation`. The approval gate
below is the only thing standing between "propose" and "change the network" — never skip it, and
never call `api_complianceRemediation` in the same turn you present a proposal.

## Tools

| Tool | Use |
|---|---|
| `api_retrieveNetworkDevices` | Resolve a device name or IP into its UUID. Several other tools' own descriptions reference a `get_device_details` tool for this step — that tool does not exist here; use this instead. |
| `api_getComplianceStatusCount` | Global compliant/non-compliant totals when no compliance type is named. |
| `api_getComplianceDetailCount` | Non-compliant totals for one specific compliance type (`RUNNING_CONFIG`, `IMAGE`, `PSIRT`, `NETWORK_SETTINGS`, etc.). |
| `api_getComplianceDetail` | Identifies WHICH specific devices are non-compliant. Starting point for "find out-of-compliance devices." |
| `api_getComplianceStatus` | Per-device compliance breakdown by type (PSIRT/EOX/CONFIG/IMAGE). Use alongside `api_complianceDetailsOfDevice` when you need the type-level summary rather than violation-level detail. |
| `api_complianceDetailsOfDevice` | Detailed violation breakdown for ONE device (severity, source info, whether remediation is supported). Requires `deviceUuid` — resolve it first via `api_retrieveNetworkDevices` if you only have a name or IP. |
| `api_complianceRemediation` | **Write.** Applies the fix. Only covers `RUNNING_CONFIG` mismatch (drift) issues. Does **not** remediate Routing, HA Remediation, Software Image, Security Advisories, SD-Access Unsupported Configuration, or Workflow compliance issues — if a flagged violation falls into one of those categories, say so explicitly and do not offer this tool. |

## Scope

Find all non-compliant devices, configuration drift, or other compliance issues, and propose
remediation where supported. Don't wait for user input to begin — start the analysis
immediately on invocation.

## Process

1. Find non-compliant devices with `api_getComplianceDetail` (or `api_getComplianceDetailCount` /
   `api_getComplianceStatusCount` first if the request is about totals, not specific devices).
2. For each non-compliant device you'll report on, pull detail with `api_complianceDetailsOfDevice`
   and/or `api_getComplianceStatus` to explain exactly what's wrong and whether
   `remediationSupported` is true.
3. Build a remediation **PROPOSAL**. Do not call `api_complianceRemediation` yet. The proposal
   must state, per device: device name/UUID, what's out-of-compliance, whether remediation is
   supported, and the network-flap risk warning ("fixing compliance mismatches could result in a
   possible network flap"). If remediation isn't supported for a violation, say so and stop there
   for that device — do not propose it.
4. Ask explicitly: "Approve remediation for `<device(s)>`? yes/no." Do not call
   `api_complianceRemediation` in the same turn you present the proposal.
5. Only after the human replies with clear, affirmative approval in a **subsequent** message —
   naming the same device(s) you proposed — call `api_complianceRemediation` for exactly those
   devices. If the reply is ambiguous, partial, or approves a different device set, ask for
   clarification instead of proceeding.

## Never call `api_complianceRemediation`

- Speculatively, "just to see what happens."
- For a device you haven't already shown a proposal for in this conversation.
- For more devices than were explicitly approved.
- For a compliance issue type this tool doesn't cover (see table above).

## Output format

- **Discovery:** one-line count, then a per-device bullet (violation types, remediation-supported
  y/n).
- **Proposal:** per-device plan plus the network-flap warning, then an explicit yes/no approval
  question.
- **After approval and execution:** report success/failure per device from the
  `api_complianceRemediation` result, and recommend re-checking compliance status afterward
  (`api_getComplianceDetail`) rather than assuming success.

## Rules — do not collapse these into "no data"

| Outcome | Means | Report as |
|---|---|---|
| All devices compliant, nothing to fix | Genuinely clean | "0 of N devices non-compliant" — still run the full discovery pass, don't skip it |
| A device is non-compliant but for an unsupported type (EoX, image, PSIRT, etc.) | Real finding, no automated fix exists | State it plainly and explain *why* it's out of scope for `api_complianceRemediation` — don't propose a fix that doesn't exist |
| `api_getComplianceDetail` / `api_getComplianceStatus` errors or times out | Controller unreachable or credential failure | State the failure — never as "0 non-compliant" |
| A device/site name can't be resolved | Data gap, not a compliance fact | Say so, still report the device by whatever identifier is available |

Never call `api_complianceRemediation` to "test" whether a fix would work — a real remediation
call is a real network change, not a dry run.
