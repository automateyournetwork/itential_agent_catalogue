import argparse
import fnmatch
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args, resolve_repo_root, safe_path  # noqa: E402

MAX_RESULTS = 500


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    repo = args.get("repo")
    pattern = args.get("pattern", "*")
    path = args.get("path", ".")

    try:
        root = resolve_repo_root(repo)
        search_root = safe_path(root, path)
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return
    except Exception as e:  # git clone failures, timeouts, etc.
        print(json.dumps({"isError": True, "error": f"could not resolve repo: {e}"}))
        return

    results = []
    for dirpath, _dirnames, filenames in os.walk(search_root):
        if ".git" in dirpath.split(os.sep):
            continue
        for fname in filenames:
            if fnmatch.fnmatch(fname, pattern):
                rel = os.path.relpath(os.path.join(dirpath, fname), root)
                results.append(rel)
                if len(results) >= MAX_RESULTS:
                    break
        if len(results) >= MAX_RESULTS:
            break

    print(json.dumps({"isError": False, "count": len(results), "files": sorted(results)}))


if __name__ == "__main__":
    main()
