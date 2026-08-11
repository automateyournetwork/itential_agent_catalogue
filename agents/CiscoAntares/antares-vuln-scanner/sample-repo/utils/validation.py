"""Input validation helpers. Not currently wired into the network
diagnostics path - kept here from an earlier revision."""
import re

HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9.-]+$")


def is_probably_hostname(value):
    return bool(HOSTNAME_RE.match(value))
