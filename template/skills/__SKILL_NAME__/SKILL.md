---
name: {{skill-name-kebab-case}}
description: "{{One sentence: what this skill does, when to use it, read-only or not. This is the ONLY text an agent sees before deciding to load the full skill — make it specific enough to trigger correctly.}}"
tags: [{{tag1}}, {{tag2}}]
metadata:
  { "mcp": { "server": "{{mcp-server-name}}", "requires_tools": ["{{tool1}}", "{{tool2}}"] } }
---

# {{Skill Title}}

{{Scope statement — e.g. "Read-only. Never call a tool that creates/updates/deletes, even if one
is reachable through the underlying server — state exactly what's out of scope and why.}}

## Tools

| Tool | Use |
|---|---|
| `{{tool_name}}` | {{what it returns, when to call it, "primary source" or "fallback only"}} |

## {{Domain-specific decision rule, e.g. "Health threshold" / "Compliance rule" / "Risk threshold"}}

{{The exact, unambiguous rule this skill uses to classify/decide — copy the real rule from the
live agent's instructions verbatim, don't paraphrase it into something looser.}}

## Process

1. {{First tool call and what scope it covers}}
2. {{Decision/filter step}}
3. {{Enrichment step — which fallback tools, in what order, and why}}
4. {{Output assembly step}}

## Output format

- {{Exact format rules — the live agent's instructions almost certainly already specify this
  precisely; copy it rather than summarizing}}

## Rules — do not collapse these into "no data"

{{This table is not optional. Every skill needs an explicit distinction between "genuinely
nothing wrong" and "couldn't tell" — copy this pattern:}}

| Outcome | Means | Report as |
|---|---|---|
| {{everything checks out}} | Genuinely fine | {{exact wording}} |
| {{empty/zero result}} | {{what a zero actually means for this system — not the same as "nothing exists"}} | {{how to phrase it, naming which system answered}} |
| {{tool errors/times out}} | {{system unreachable or credential failure}} | State the failure explicitly — never silently reinterpret as "clean" |
| {{a lookup can't resolve}} | Data gap, not a fact about the thing being checked | {{placeholder wording}}, still report the item |

{{Add any domain-specific "don't conflate X with Y" rule here — e.g. "a controller's last-known
status is not live device truth."}}
