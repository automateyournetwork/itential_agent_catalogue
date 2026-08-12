import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402

OLLAMA_URL = os.environ.get("ANTARES_OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("ANTARES_FIX_OLLAMA_MODEL", "qwen3-coder:latest")
REQUEST_TIMEOUT_SECONDS = 120

CODE_BLOCK_RE = re.compile(r"##\s*Fixed Code\s*```(?:\w+)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
EXPLANATION_RE = re.compile(r"##\s*Explanation\s*\n(.*)", re.DOTALL | re.IGNORECASE)


def ask_ollama(file_path, file_content, cwe, finding_reasoning):
    prompt = (
        "You are a secure-coding assistant. You will be given the full content of a "
        "file, the CWE vulnerability class it contains, and why it's vulnerable. Your "
        "job is to rewrite the file to fix ONLY that vulnerability, changing nothing "
        "else about its behavior, style, or structure than necessary to close the "
        "vulnerability.\n\n"
        "Rules:\n"
        "1. Preserve the function/class names, signatures, and overall structure "
        "unless the fix genuinely requires changing them.\n"
        "2. The fix must actually close the vulnerability, not just look safer. For "
        "OS command injection specifically, that means the untrusted input must "
        "never be interpreted by a shell -- pass it as a literal argument in an "
        "argv-style list (e.g. subprocess.run with a list, no shell=True), don't "
        "just re-quote or \"sanitize\" a string that still gets passed to a shell.\n"
        "3. Output format, exactly these two headings:\n\n"
        "## Fixed Code\n```\n<the ENTIRE corrected file content, ready to write back as-is>\n```\n\n"
        "## Explanation\n<what changed, and specifically why it closes this CWE -- reference "
        "the exact line(s) that were unsafe and what replaces them>\n\n"
        f"File path: {file_path}\n"
        f"Vulnerability class: {cwe}\n"
        f"Why it's vulnerable: {finding_reasoning}\n\n"
        f"File content:\n{file_content}"
    )
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    file_path = args.get("filePath")
    file_content = args.get("fileContent")
    cwe = args.get("cwe")
    finding_reasoning = args.get("findingReasoning", "")

    missing = [k for k in ("filePath", "fileContent", "cwe") if not args.get(k)]
    if missing:
        print(json.dumps({"isError": True, "error": f"missing required: {missing}"}))
        return

    try:
        answer = ask_ollama(file_path, file_content, cwe, finding_reasoning)
    except (urllib.error.URLError, TimeoutError, KeyError) as e:
        print(json.dumps({"isError": True, "error": f"model call failed: {e}"}))
        return

    code_match = CODE_BLOCK_RE.search(answer)
    explanation_match = EXPLANATION_RE.search(answer)

    if not code_match:
        print(
            json.dumps(
                {
                    "isError": True,
                    "error": "model response did not contain a parseable '## Fixed Code' block",
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
                "explanation": explanation,
            }
        )
    )


if __name__ == "__main__":
    main()
