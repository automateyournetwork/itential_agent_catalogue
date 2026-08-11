import json
import os

ROOT = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sample-repo")
)


def safe_path(rel_path):
    """Resolve rel_path against ROOT, refusing anything that escapes it.

    This is the whole sandbox: these tools never shell out, so there's no
    injection surface, and every path is confined to ROOT before any file
    operation touches disk.
    """
    candidate = os.path.realpath(os.path.join(ROOT, rel_path or "."))
    if not (candidate == ROOT or candidate.startswith(ROOT + os.sep)):
        raise ValueError(f"path escapes repo root: {rel_path!r}")
    return candidate


def parse_args(argv):
    # IAG sends every decorator field as --key=value, including unset ones
    # (value ''). Omit those, and JSON-decode the rest so lists/ints survive.
    args = {}
    for item in argv:
        if not item.startswith("--") or "=" not in item:
            continue
        key, _, value = item[2:].partition("=")
        if value == "":
            continue
        try:
            args[key] = json.loads(value)
        except json.JSONDecodeError:
            args[key] = value
    return args
