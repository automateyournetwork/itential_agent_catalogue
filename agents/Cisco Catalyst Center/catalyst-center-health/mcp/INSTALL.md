# Installing the Catalyst Center MCP server

This runs entirely independent of Itential. Any MCP client (Claude Code, Codex, Claude Desktop,
`mcp-cli`) can use it once it's up.

## 1. Get the server

Official Cisco server, Apache-2.0, version-coupled to a Catalyst Center release branch — `main`
has no code, only governance files.

```bash
git clone https://github.com/cisco-en-programmability/catc-mcp-oss.git
cd catc-mcp-oss
git checkout release/2.3.7.11   # pin to your controller's version
```

## 2. Curate the tool set (strongly recommended)

The default bundle is 515 tools / ~64,000 tokens of manifest — 12.9x over most agent tool-count
budgets. This agent only needs 5: `api_devices`, `api_retrieveNetworkDevices`,
`api_getDeviceSummary`, `api_getSites`, `api_getSiteAssignedNetworkDevice`.

Point `CATALYST_CENTER_BUNDLED_TOOLS_DIR` at a directory containing only the tool definitions
you want loaded (`tool_loader.load_tools(dir)` — the vendored tree itself is never modified).
See `catalyst_center_mcp/bundled_tools/` in the upstream repo for the definition format, and
`netclaw/workspace/skills/catalyst-center-readonly/` locally for a worked 10-tool curation if
you want a broader reference set.

## 3. Run it (Docker — required, see note below)

This clone needs its own `.env` for `docker compose` — copy the `CATALYST_CENTER_*` values you
already filled in at this repo's root `.env` (see the root `README.md` "Setup" section):

```bash
cat > .env <<EOF
CATALYST_CENTER_HOST=$CATALYST_CENTER_HOST
CATALYST_CENTER_USERNAME=$CATALYST_CENTER_USERNAME
CATALYST_CENTER_PASSWORD=$CATALYST_CENTER_PASSWORD
CATALYST_CENTER_VERIFY_SSL=$CATALYST_CENTER_VERIFY_SSL
CATALYST_CENTER_BUNDLED_TOOLS_DIR=/app/curated
EOF
# (run the repo root's `set -a; source .env; set +a` first so these $VARS expand,
# or just paste the real values in directly)

docker compose up -d --build
```

Serves streamable-HTTP on `http://localhost:7001/v1/mcp` (not stdio — every other typical MCP
server in this ecosystem is stdio; this one ships a Dockerfile specifically because
`pyproject.toml` pins `fastmcp>=2.0.0` unbounded, which resolves to fastmcp 3.x and conflicts
with anything pinning `fastmcp<3`. Running it in its own container sidesteps that entirely —
don't "simplify" this onto a host interpreter shared with other MCP servers.

**No authorization layer of its own** — the server enforces no read-only restriction; safety
here comes from (a) which tools you curate in (the 5 above are all GET) and (b) the Catalyst
Center account's own RBAC. Use a least-privilege, read-only account.

## 4. Point a client at it

**Claude Code** — copy `../mcp/servers.json`'s `catalyst-center` entry into this repo's
`.mcp.json`, or merge it if one already exists.

**Codex** — same server definition, TOML form, in `~/.codex/config.toml`:
```toml
[mcp_servers.catalyst-center]
url = "http://localhost:7001/v1/mcp"
```

**Itential Gateway (iagctl)** — register it as a Gateway-level MCP client:
```bash
iagctl mcp server add catalyst-center "http://host.docker.internal:7001/v1/mcp" \
  --description "Cisco Catalyst Center (DNAC) MCP server"
iagctl mcp tool list catalyst-center
iagctl mcp tool call api_devices catalyst-center --params '{"limit": 5}'
```
Use `host.docker.internal` instead of `localhost` here because Gateway itself runs in a
container. This registration alone is **not enough** for FlowAI to use the tools — see
`../itential/agent.spec.md` for why.
