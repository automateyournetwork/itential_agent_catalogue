import json


def parse_args(argv):
    # IAG sends every decorator field as --key=value, including unset ones
    # (value ''). Omit those, and JSON-decode the rest so lists/dicts/ints
    # survive. A boolean-typed decorator field with value true is sent as a
    # bare --key flag (no '='), not --key=true -- treat that as True.
    # Copied from ../../CiscoAntares/antares-vuln-scanner/tools/_repo_utils.py
    # (kept local here since this tool has no repo-cloning code to share it with).
    args = {}
    for item in argv:
        if not item.startswith("--"):
            continue
        if "=" not in item:
            args[item[2:]] = True
            continue
        key, _, value = item[2:].partition("=")
        if value == "":
            continue
        try:
            args[key] = json.loads(value)
        except json.JSONDecodeError:
            args[key] = value
    return args
