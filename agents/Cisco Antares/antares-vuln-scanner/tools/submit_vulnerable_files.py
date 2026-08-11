import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    files = args.get("files")
    reasoning = args.get("reasoning", "")

    if not files or not isinstance(files, list):
        print(
            json.dumps(
                {"isError": True, "error": "files must be a non-empty list of relative paths"}
            )
        )
        return

    print(json.dumps({"isError": False, "verdict": "vulnerable", "files": files, "reasoning": reasoning}))


if __name__ == "__main__":
    main()
