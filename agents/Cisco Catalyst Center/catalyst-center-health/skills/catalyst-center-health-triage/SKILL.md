---
name: catalyst-center-health-triage
description: "Triage Cisco Catalyst Center (DNAC) device health — find degraded devices, resolve their site and role, and produce a per-site report. Read-only. Use when asked what's unhealthy on a Catalyst Center-managed network, or to reconcile controller health against a specific site/device scope."
tags: [cisco, catalyst-center, dnac, health, assurance, network]
metadata:
  { "mcp": { "server": "catalyst-center", "requires_tools": ["api_devices", "api_retrieveNetworkDevices", "api_getDeviceSummary", "api_getSites", "api_getSiteAssignedNetworkDevice"] } }
---

# Catalyst Center Health Triage

Read-only. Never call a tool that creates, updates, deletes, or remediates anything, even if one
is reachable through the MCP server this skill uses — the server exposes far more than these 5
operations; nothing outside this list is in scope.

## Tools

| Tool | Use |
|---|---|
| `api_devices` | DNA Assurance device intent API. Returns each device's `overallHealth` score (0–10), issue count, and site/location fields. **Primary source.** |
| `api_retrieveNetworkDevices` | Basic device inventory (role, family, reachability status, management IP). Use to enrich a flagged device with role/type when `api_devices` doesn't have it. |
| `api_getDeviceSummary` | Brief per-device summary. Use only when drilling into a specific flagged device for more detail. |
| `api_getSites` | Converts a `siteId` into a readable site hierarchy name (`nameHierarchy`). Use when a flagged device's site comes back as a raw ID. |
| `api_getSiteAssignedNetworkDevice` | Confirms which site a device is assigned to. Fallback only, if `api_devices` and `api_getSites` don't resolve a clear site. |

## Health threshold

A device is **degraded** if:
- `overallHealth` score is below 7 (0–10 scale), OR
- it has one or more open issues reported by `api_devices`.

## Process

1. Call `api_devices` for health scores across the requested scope (all devices, or a specific
   site/device list if the objective names one).
2. Identify every device below the threshold.
3. For each flagged device, resolve site and role: use fields already on the `api_devices`
   record if present; otherwise call `api_retrieveNetworkDevices` for role, and `api_getSites`
   (or `api_getSiteAssignedNetworkDevice` as a fallback) to resolve the site name.
4. Produce a summary grouped by site: device name, issue count/description, role.

## Output format

- One-line overall count: "X of Y devices degraded."
- A section per site, each device as a bullet: `device_name (role) — score: N/10, issues: <summary>`
- If a site or role genuinely cannot be resolved after the fallback tools, say
  `(site/role unresolved)` rather than guessing.
- Close with a "Needs attention first" line naming the 1–3 worst devices, if any exist.

## Rules — do not collapse these into "no data"

An empty or all-healthy result from `api_devices` is not automatically good news, and a
tool error is not automatically "no devices." Distinguish:

| Outcome | Means | Report as |
|---|---|---|
| All devices ≥ 7, no issues | Genuinely healthy | "0 of Y devices degraded" |
| `api_devices` returns zero devices | This controller manages none | State which controller, not "network is empty" |
| A tool call errors/times out | Controller unreachable or credential failure | State the failure — never as "0 degraded" |
| Site/role can't be resolved | Data gap, not a health fact | `(site/role unresolved)`, still report the device |

Never call a device down because Catalyst Center couldn't reach it — `overallHealth` and
`reachabilityHealth` are the controller's last observation, not live device state.
