import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import parse_args  # noqa: E402


def main():
    """Terminal tool for the Jev Assessment Summarizer agent. Call exactly
    once with a short, human-readable summary combining the Proposer's
    proposal and Jev's structured pre/post-check assessment -- for display
    as plain text in a Work Center ViewData task (which is why this exists
    at all: dumping Jev's raw JSON straight into a ViewData string field
    that the platform validates as an object broke Work Center's own
    Approve/Reject submission -- see agent.spec.md).
    """
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    summary = args.get("summary")

    if not summary:
        print(json.dumps({"isError": True, "error": "missing required: ['summary']"}))
        return

    print(json.dumps({"isError": False, "summary": summary}))


if __name__ == "__main__":
    main()
