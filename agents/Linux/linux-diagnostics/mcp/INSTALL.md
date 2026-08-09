# Installing the Linux Diagnostics MCP server

This runs entirely independent of Itential. Any MCP client (Claude Code, Codex, Claude Desktop,
`mcp-cli`) can use it once it's up.

**Different from the Cisco agents' MCP setup:** those wrap an existing third-party MCP server
(Cisco's own `catc-mcp-oss`). There is no upstream vendor MCP server for Linux diagnostics — this
one (`server.py`) *is* the implementation, running `../ansible/linux_diagnostics.yml` itself. See
`../itential/agent.spec.md` "Provenance" for why this had to be built from scratch rather than
pulled from the original deployment.

## 1. Prerequisites

- Python 3.10+
- SSH access from wherever this server runs to the target Linux hosts (key-based auth configured
  in your Ansible inventory — `ansible_ssh_private_key_file` / `ansible_user` per host or group)
- `ansible-core` installed (in `requirements.txt` — this is enough; no extra collections needed,
  the playbook only uses `ansible.builtin.*` modules)

## 2. Set up an inventory

The `run_diagnostics` tool's `inventory` argument is passed straight through to `ansible-playbook
-i`. Point it at:

- A static inventory file: `-i inventory.ini`, and pass a group name from that file as the tool
  argument (e.g. `"webservers"`)
- Or a comma-separated host list directly as the argument (Ansible shorthand): `"host1,host2,"`
  (trailing comma required for a single host with no inventory file)

```ini
# example inventory.ini
[webservers]
web1.example.com
web2.example.com

[webservers:vars]
ansible_user=svc-diagnostics
ansible_ssh_private_key_file=/path/to/key.pem
```

Set `ANSIBLE_INVENTORY=/path/to/inventory.ini` in the server's environment so bare group names
resolve, or pass the file path directly as part of the `inventory` argument each call.

## 3. Run it

```bash
cd agents/Linux/linux-diagnostics/mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ANSIBLE_INVENTORY=/path/to/inventory.ini   # optional — only needed for bare group names
python3 server.py
```

Serves streamable-HTTP on `http://localhost:7002/v1/mcp` by default (FastMCP's default port —
override by passing `port=` to `mcp.run(...)` in `server.py` if 7002 is taken).

**No authorization layer of its own** — same posture as the Cisco MCP server: safety comes from
which hosts your inventory/SSH credentials can actually reach, and those credentials should be
least-privilege (this tool only runs read commands — `cat`, `df`, `systemctl status/--failed`,
`journalctl -k`, `ps` — nothing in `linux_diagnostics.yml` writes to the target host).

## 4. Point a client at it

**Claude Code** — copy `../mcp/servers.json`'s `linux-diagnostics` entry into this repo's
`.mcp.json`, or merge it if one already exists.

**Codex** — same server definition, TOML form, in `~/.codex/config.toml`:
```toml
[mcp_servers.linux-diagnostics]
url = "http://localhost:7002/v1/mcp"
```

**Itential Gateway (iagctl)** — register it as a Gateway-level MCP client, same pattern as the
Cisco agents (see `../itential/agent.spec.md` Section 2 for the full wrapper-service build):
```bash
iagctl mcp server add linux-diagnostics "http://host.docker.internal:7002/v1/mcp" \
  --description "Linux host diagnostics (this repo's own implementation)"
iagctl mcp tool list linux-diagnostics
iagctl mcp tool call run_diagnostics linux-diagnostics --params '{"inventory": "webservers"}'
```
Use `host.docker.internal` instead of `localhost` here because Gateway itself runs in a container.
This registration alone is **not enough** for FlowAI to use the tool — see
`../itential/agent.spec.md` Section 2.1 for why (same gotcha as the Cisco agents).

## 5. If you'd rather use the real production playbook instead of this reconstruction

If you have `iagctl` Gateway-admin access to the environment this was converted from, you can pull
the actual playbook this agent's production Gateway service runs (`linux_patch_check` repository,
`linux_diagnostics.yml` — real path confirmed via a live test run, see Provenance in
`../itential/agent.spec.md`) and swap it in for `../ansible/linux_diagnostics.yml`, keeping this
`server.py` wrapper as-is (it only cares about the JSON callback shape, not which playbook
produced it). That would give you the verbatim original logic instead of this from-scratch
equivalent.
