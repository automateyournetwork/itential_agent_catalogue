"""Network reachability checks."""
import os


def ping_host(host):
    """Ping a host once and return the raw command output.

    host comes straight from user input (a CLI argument here, but the same
    function backs an internal HTTP endpoint elsewhere) and is passed
    directly into a shell command below.
    """
    command = f"ping -c 1 {host}"
    return os.popen(command).read()
