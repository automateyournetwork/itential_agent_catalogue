import argparse
import fnmatch
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import ROOT, parse_args, safe_path  # noqa: E402

MAX_RESULTS = 500


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    pattern = args.get("pattern", "*")
    path = args.get("path", ".")

    try:
        search_root = safe_path(path)
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return

    results = []
    for dirpath, _dirnames, filenames in os.walk(search_root):
        for fname in filenames:
            if fnmatch.fnmatch(fname, pattern):
                rel = os.path.relpath(os.path.join(dirpath, fname), ROOT)
                results.append(rel)
                if len(results) >= MAX_RESULTS:
                    break
        if len(results) >= MAX_RESULTS:
            break

    print(json.dumps({"isError": False, "count": len(results), "files": sorted(results)}))


if __name__ == "__main__":
    main()
