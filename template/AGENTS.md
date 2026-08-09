# {{AGENT_NAME}}

Reverse-engineered from a live FlowAI agent (`{{SOURCE_AGENT_ID}}`, project "{{SOURCE_PROJECT}}"
on {{SOURCE_PLATFORM_URL}}). This file is plain context for any coding agent (Claude Code, Codex,
Cursor, etc.) working in this folder — it does not require Itential to be present to be useful.

## What this agent does

{{ONE_PARAGRAPH_PLAIN_LANGUAGE_DESCRIPTION — don't just restate the system prompt, explain the
actual job in plain terms: what triggers it, what it reads, what it decides, what it produces.}}

## Source of truth for behavior

The actual system prompt shipped with the live agent is at `itential/agent.spec.md` (Section 3,
"Instructions") — treat that as canonical. This file is orientation, not the prompt itself.

## Tools this agent needs

{{TABLE_OF_TOOLS — name | purpose, one row per tool. If MCP-backed, note which MCP server.}}

## Testing without Itential

1. {{HOW_TO_STAND_UP_ANY_MCP_SERVERS_THIS_AGENT_NEEDS — see mcp/INSTALL.md}}
2. Point any MCP client (Claude Code via `.mcp.json`, Claude Desktop, `iagctl mcp tool call`) at it.
3. Use `skills/{{SKILL_NAME}}/SKILL.md` as the operating procedure.
4. Sample expected input/output pairs are in `tests/missions/`.

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration — provider/model, the exact
tool `referenceId` format this platform expects, and a verified, self-sufficient deploy recipe
(Section 0) that doesn't depend on `itential-builder:flowagent`'s own docs being current.
