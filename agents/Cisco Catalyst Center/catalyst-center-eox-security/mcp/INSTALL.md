# Installing the Catalyst Center MCP server

This runs entirely independent of Itential. Any MCP client (Claude Code, Codex, Claude Desktop,
`mcp-cli`) can use it once it's up. **Same server and container as
`../../catalyst-center-health/mcp/INSTALL.md`** — if you already have that one running for a
sibling agent, point this agent's client at the same `http://localhost:7001/v1/mcp` instance and
skip straight to curating the tool set (Step 2) or, if it's already curated broadly enough, skip
straight to Step 4.

## 1. Get the server

Official Cisco server, Apache-2.0, version-coupled to a Catalyst Center release branch — `main`
has no code, only governance files.

```bash
git clone https://github.com/cisco-en-programmability/catc-mcp-oss.git
cd catc-mcp-oss
git checkout release/2.3.7.11   # pin to your controller's version
```

## 2. Curate the tool set (strongly recommended)

The default bundle is 515 tools / ~64,000 tokens of manifest. This agent needs 8 (12 if you also
want the 4 bound-but-unused tools documented in `../itential/agent.spec.md` §2.1):
`api_getEoXSummary`, `api_getEoXStatusForAllDevices`, `api_getEoXDetailsPerDevice`,
`api_getSecurityAdvisoryNetworkDevices`, `api_getCountOfSecurityAdvisoriesAffectingTheNetworkDevices`,
`api_getNetworkBugs`, `api_getCountOfNetworkBugDevices`, `api_retrieveNetworkDevices`.

Point `CATALYST_CENTER_BUNDLED_TOOLS_DIR` at a directory containing only the tool definitions you
want loaded (`tool_loader.load_tools(dir)` — the vendored tree itself is never modified). If
you're running this agent alongside `catalyst-center-health` or `catalyst-center-remediation`
against the same MCP server instance, you can union all three tool sets into one curated
directory rather than running three separate containers.

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

Serves streamable-HTTP on `http://localhost:7001/v1/mcp` (not stdio — see
`../../catalyst-center-health/mcp/INSTALL.md` for why this server specifically requires its own
container rather than a shared host interpreter).

**The Catalyst Center account behind `CATALYST_CENTER_USERNAME`/`PASSWORD` needs read RBAC on the
PSIRT/Security-Advisory and Bug-Scanner APIs specifically**, in addition to the general read
access `catalyst-center-health` needs. This was *not* true during this agent's own verification
run — `api_getSecurityAdvisoryNetworkDevices` and `api_getCountOfNetworkBugDevices` both returned
403 against the live sandbox. The skill handles that gracefully (reports it as a finding), but
confirm this account's role includes those scopes before expecting a complete report.

## 4. Point a client at it

**Claude Code** — copy `../mcp/servers.json`'s `catalyst-center` entry into this repo's
`.mcp.json`, or merge it if one already exists (e.g. alongside a sibling agent's entry — they're
the same server).

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
iagctl mcp tool call api_getEoXSummary catalyst-center --params '{}'
```
Use `host.docker.internal` instead of `localhost` here because Gateway itself runs in a
container. This registration alone is **not enough** for FlowAI to use the tools — see
`../itential/agent.spec.md` for the wrapper-service pattern this deployment actually uses.
