import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args, safe_path  # noqa: E402

MAX_CHARS = 6000


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    path = args.get("path")
    start_line = args.get("start_line")
    end_line = args.get("end_line")

    if not path:
        print(json.dumps({"isError": True, "error": "path is required"}))
        return

    try:
        fpath = safe_path(path)
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return

    if not os.path.isfile(fpath):
        print(json.dumps({"isError": True, "error": f"not a file: {path}"}))
        return

    with open(fpath, "r", errors="replace") as f:
        lines = f.readlines()

    lo = max(1, int(start_line)) if start_line else 1
    hi = min(len(lines), int(end_line)) if end_line else len(lines)
    selected = "".join(lines[lo - 1 : hi])

    truncated = False
    if len(selected) > MAX_CHARS:
        selected = selected[:MAX_CHARS]
        truncated = True

    print(
        json.dumps(
            {
                "isError": False,
                "path": path,
                "startLine": lo,
                "endLine": hi,
                "content": selected,
                "truncated": truncated,
            }
        )
    )


if __name__ == "__main__":
    main()
