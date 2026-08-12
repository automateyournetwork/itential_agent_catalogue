import argparse
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402

CODE_BLOCK_RE = re.compile(r"##\s*Fixed Code\s*```(?:\w+)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
EXPLANATION_RE = re.compile(r"##\s*Explanation\s*\n(.*)", re.DOTALL | re.IGNORECASE)


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    file_path = args.get("filePath")

    # Prefer base64 -- the agent's raw final answer is multi-line and full
    # of backticks/quotes (a markdown fenced code block), which can crash
    # runService's CLI-parsing ("EOF found when expecting closing quote").
    answer_b64 = args.get("answerBase64")
    answer = args.get("answer")
    if answer_b64:
        try:
            answer = base64.b64decode(answer_b64).decode("utf-8")
        except Exception as e:
            print(json.dumps({"isError": True, "error": f"invalid answerBase64: {e}"}))
            return

    if not answer:
        print(json.dumps({"isError": True, "error": "missing required: ['answer']"}))
        return

    code_match = CODE_BLOCK_RE.search(answer)
    explanation_match = EXPLANATION_RE.search(answer)

    if not code_match:
        print(
            json.dumps(
                {
                    "isError": True,
                    "error": "agent answer did not contain a parseable '## Fixed Code' block",
                    "rawAnswer": answer,
                }
            )
        )
        return

    fixed_code = code_match.group(1).rstrip("\n") + "\n"
    explanation = explanation_match.group(1).strip() if explanation_match else ""

    print(
        json.dumps(
            {
                "isError": False,
                "filePath": file_path,
                "fixedCode": fixed_code,
                "fixedCodeBase64": base64.b64encode(fixed_code.encode("utf-8")).decode("ascii"),
                "explanation": explanation,
                "explanationBase64": base64.b64encode(explanation.encode("utf-8")).decode("ascii"),
            }
        )
    )


if __name__ == "__main__":
    main()
