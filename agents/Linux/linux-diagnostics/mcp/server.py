"""
Linux Diagnostics MCP server.

Exposes one tool, `run_diagnostics`, that runs ../ansible/linux_diagnostics.yml against a target
inventory and returns structured per-host results (raw metrics — no OK/WARNING/CRITICAL
classification; that happens in ../skills/linux-diagnostics/SKILL.md).

Unlike the catalyst-center MCP server (an existing upstream server this repo just wraps), there is
no upstream vendor MCP server for Linux diagnostics — this server *is* the implementation. See
../itential/agent.spec.md "Provenance" for why (the original Gateway service's real playbook
source wasn't accessible during conversion) and what real evidence this reconstruction is based
on.

Streamable-HTTP transport, matching every other MCP server in this repo (host.docker.internal from
inside Gateway's own container, localhost for a local MCP client).
"""
import json
import os
import subprocess

from mcp.server.fastmcp import FastMCP

PLAYBOOK_PATH = os.environ.get(
    "LINUX_DIAGNOSTICS_PLAYBOOK",
    os.path.join(os.path.dirname(__file__), "..", "ansible", "linux_diagnostics.yml"),
)
ANSIBLE_TIMEOUT_SECONDS = int(os.environ.get("LINUX_DIAGNOSTICS_TIMEOUT", "120"))

mcp = FastMCP("linux-diagnostics")


def _percent_used(mount):
    total = mount.get("size_total") or 0
    available = mount.get("size_available") or 0
    if not total:
        return None
    return round((total - available) / total * 100, 1)


def _build_host_report(host, task_hosts_by_name):
    """Pull this host's final `diagnostics_result` set_fact out of the play's task list."""
    result = None
    for task in task_hosts_by_name:
        host_data = task.get("hosts", {}).get(host)
        if host_data and "diagnostics_result" in host_data.get("ansible_facts", {}):
            result = host_data["ansible_facts"]["diagnostics_result"]
    if result is None:
        return None
    disks = [
        {
            "mount": m.get("mount"),
            "percent_used": _percent_used(m),
        }
        for m in result.get("disks_raw", [])
        if m.get("size_total")
    ]
    result["disks"] = disks
    result.pop("disks_raw", None)
    return result


@mcp.tool()
def run_diagnostics(inventory: str) -> dict:
    """Run the Linux diagnostics playbook against an inventory group or comma-separated host list.

    Args:
        inventory: An Ansible inventory reference — a group name from your inventory file/source,
            or a comma-separated host list (Ansible's `host1,host2,` shorthand — note the trailing
            comma required for a single host with no inventory file).

    Returns:
        {"isError": bool, "hosts": [...], "raw": {...}} — `hosts` is one entry per host actually
        reached (see docstring note on unreachable hosts below); `raw` is the full Ansible JSON
        callback output for debugging.
    """
    env = os.environ.copy()
    env["ANSIBLE_STDOUT_CALLBACK"] = "json"
    env["ANSIBLE_HOST_KEY_CHECKING"] = "False"

    proc = subprocess.run(
        ["ansible-playbook", "-i", inventory, PLAYBOOK_PATH, "-e", f"target_hosts={inventory}"],
        capture_output=True,
        text=True,
        timeout=ANSIBLE_TIMEOUT_SECONDS,
        env=env,
    )

    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "isError": True,
            "error": "ansible-playbook did not return parseable JSON — see stderr",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }

    all_tasks = [t for play in raw.get("plays", []) for t in play.get("tasks", [])]
    stats = raw.get("stats", {})

    hosts = []
    for host in stats.keys():
        report = _build_host_report(host, all_tasks)
        if report is not None:
            hosts.append(report)
        elif stats[host].get("unreachable"):
            hosts.append({"hostname": host, "reachable": False, "reason": "Host unreachable"})
        elif stats[host].get("failures"):
            hosts.append(
                {
                    "hostname": host,
                    "reachable": False,
                    "reason": "Playbook failed before completing diagnostics collection for this host — see raw for details",
                }
            )

    return {
        "isError": proc.returncode != 0 and not hosts,
        "hosts": hosts,
        "raw": raw,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
