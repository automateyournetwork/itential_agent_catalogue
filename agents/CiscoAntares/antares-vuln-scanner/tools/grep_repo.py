import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args, resolve_repo_root, safe_path  # noqa: E402

MAX_MATCHES = 200


def build_regex(args):
    """Prefer `patterns` (a list of plain literal strings, no regex syntax
    required) over `pattern` (a single regex) - the model has repeatedly
    produced malformed combined regexes, so the literal-list interface
    removes that entire failure mode.
    """
    patterns = args.get("patterns")
    if patterns:
        if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
            raise ValueError("patterns must be a list of strings")
        escaped = [re.escape(p) for p in patterns if p]
        if not escaped:
            raise ValueError("patterns must contain at least one non-empty string")
        return re.compile("|".join(escaped)), {p: re.escape(p) for p in patterns}

    pattern = args.get("pattern")
    if pattern:
        return re.compile(pattern), None

    raise ValueError("either patterns (list of literal strings) or pattern (regex) is required")


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    repo = args.get("repo")
    path = args.get("path", ".")

    try:
        regex, literal_map = build_regex(args)
    except re.error as e:
        print(json.dumps({"isError": True, "error": f"invalid regex: {e}"}))
        return
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return

    try:
        root = resolve_repo_root(repo)
        search_root = safe_path(root, path)
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return
    except Exception as e:
        print(json.dumps({"isError": True, "error": f"could not resolve repo: {e}"}))
        return

    matches = []
    for dirpath, _dirnames, filenames in os.walk(search_root):
        if ".git" in dirpath.split(os.sep):
            continue
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root)
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
