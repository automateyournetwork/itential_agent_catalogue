import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import ROOT, parse_args, safe_path  # noqa: E402

MAX_MATCHES = 200


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    pattern = args.get("pattern")
    path = args.get("path", ".")

    if not pattern:
        print(json.dumps({"isError": True, "error": "pattern is required"}))
        return

    try:
        search_root = safe_path(path)
        regex = re.compile(pattern)
    except re.error as e:
        print(json.dumps({"isError": True, "error": f"invalid regex: {e}"}))
        return
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return

    matches = []
    for dirpath, _dirnames, filenames in os.walk(search_root):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, ROOT)
            try:
                with open(fpath, "r", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if regex.search(line):
                            matches.append(
                                {"file": rel, "line": lineno, "text": line.rstrip()[:300]}
                            )
                            if len(matches) >= MAX_MATCHES:
                                break
            except (UnicodeDecodeError, IsADirectoryError, PermissionError):
                continue
            if len(matches) >= MAX_MATCHES:
                break
        if len(matches) >= MAX_MATCHES:
            break

    print(
        json.dumps(
            {
                "isError": False,
                "matchCount": len(matches),
                "matches": matches,
                "truncated": len(matches) >= MAX_MATCHES,
            }
        )
    )


if __name__ == "__main__":
    main()
