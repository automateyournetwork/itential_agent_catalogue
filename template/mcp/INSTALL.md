# Installing the {{mcp-server-name}} MCP server

This runs entirely independent of Itential. Any MCP client (Claude Code, Codex, Claude Desktop,
`mcp-cli`) can use it once it's up.

## 1. Get the server

{{git clone / docker pull / npm install — wherever this MCP server actually comes from. If it's
a third-party/vendor server, link it and note the license and any version coupling to the system
it talks to (e.g. "pinned to release/X.Y.Z, targets controller version X.Y").}}

## 2. Curate the tool set (do this if the default bundle is large)

{{If the server ships hundreds of tools and your skill only needs a handful, document the
curation mechanism here — e.g. an env var pointing at a directory of selected tool definitions.
Record: default tool count/token cost vs. curated count/cost, so a future bump is noticed.}}

## 3. Run it

```bash
{{exact run command — docker compose up, npx ..., python -m ..., whatever it actually is}}
```

Note the transport (stdio vs HTTP/SSE) and port if applicable — this must match `servers.json`.

{{Any credential/env var requirements — name them, and where they come from (never hardcode
values in this file).}}

If this server needs credentials (a controller host/username/password, an API key, etc.), add
them to this repo's root `.env.example` — with a comment on what they're for — rather than
inventing a separate, undocumented `.env` just for this step. If the server needs its own `.env`
for its own `docker compose`/run command (because it lives in its own cloned repo, separate from
this one), say so explicitly and show copying the values from the root `.env`:

```bash
{{e.g.: cat > .env <<EOF
SOME_CREDENTIAL=$SOME_CREDENTIAL
EOF}}
```

## 4. Point a client at it

**Claude Code** — copy `servers.json`'s entry into this repo's `.mcp.json`.

**Codex** — same server definition, TOML form, in `~/.codex/config.toml`:
```toml
[mcp_servers.{{mcp-server-name}}]
{{command or url, matching servers.json}}
```

**Itential Gateway (iagctl)** — register it as a Gateway-level MCP client:
```bash
iagctl mcp server add {{mcp-server-name}} "{{command or url}}"
iagctl mcp tool list {{mcp-server-name}}
```
Registering the MCP server on Gateway is **not enough** for FlowAI to use its tools on every
Gateway build — see `../itential/agent.spec.md` Section 2 for the wrapper-service pattern
(written unconditionally, even if the wrapper services already exist wherever you're authoring
this from — the next person may be starting from zero) and `../../../template/CONVERT-AGENT-TO-PORTABLE.md`
Step 4 for the general version of that recipe.
