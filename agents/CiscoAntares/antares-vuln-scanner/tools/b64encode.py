import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402


def main():
    """Base64-encodes arbitrary text.

    Exists because runService has a real platform bug: multi-line,
    quote-containing string params (a raw agent answer, source code,
    markdown) can crash it with "EOF found when expecting closing quote"
    while still reporting status: complete. The workaround used everywhere
    else in this pipeline is to base64-encode any such text before it
    becomes a runService param -- this is the one general-purpose place to
    do that for text that doesn't already come out of a script that can
    encode it itself (e.g. an agent's own final answer).
    """
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    text = args.get("text", "")
    print(json.dumps({"isError": False, "encoded": base64.b64encode(text.encode("utf-8")).decode("ascii")}))


if __name__ == "__main__":
    main()
