import argparse
import fnmatch
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args, resolve_repo_root  # noqa: E402

OLLAMA_URL = os.environ.get("ANTARES_OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("ANTARES_OLLAMA_MODEL", "antares-1b:latest")
CHUNK_CHAR_BUDGET = int(os.environ.get("ANTARES_CHUNK_CHAR_BUDGET", "3000"))
REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_FILE_PATTERN = "*.py"
VERDICT_LINE_RE = re.compile(r"^\s*FOUND\s*:\s*(\S.*)$", re.IGNORECASE | re.MULTILINE)
CLEAN_LINE_RE = re.compile(r"^\s*CLEAN\s*$", re.IGNORECASE | re.MULTILINE)
MAX_VERDICT_ATTEMPTS = 3


def collect_files(root, pattern):
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if ".git" in dirpath.split(os.sep):
            continue
        for fname in filenames:
            if fnmatch.fnmatch(fname, pattern):
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, root)
                try:
                    with open(fpath, "r", errors="replace") as f:
                        files.append((rel, f.read()))
                except (UnicodeDecodeError, IsADirectoryError, PermissionError):
                    continue
    return sorted(files, key=lambda x: x[0])


def build_chunks(files, budget):
    """Greedily pack whole files into chunks up to `budget` chars. A single
    file larger than the budget gets split across multiple chunks by lines,
    so no chunk ever exceeds the model's usable context.
    """
    chunks = []
    current = []
    current_size = 0

    def flush():
        nonlocal current, current_size
        if current:
            chunks.append(current)
            current = []
            current_size = 0

    for rel, content in files:
        entry = f"=== {rel} ===\n{content}\n"
        if len(entry) > budget:
            lines = content.splitlines(keepends=True)
            piece, piece_size = [], 0
            for line in lines:
                if piece_size + len(line) > budget and piece:
                    flush()
                    chunks.append([(rel, "".join(piece))])
                    piece, piece_size = [], 0
                piece.append(line)
                piece_size += len(line)
            if piece:
                flush()
                chunks.append([(rel, "".join(piece))])
            continue

        if current_size + len(entry) > budget and current:
            flush()
        current.append((rel, content))
        current_size += len(entry)

    flush()
    return chunks


def render_chunk(chunk_files):
    return "\n".join(f"=== {rel} ===\n{content}" for rel, content in chunk_files)


def ask_ollama(cwe, chunk_text, chunk_index, chunk_count):
    prompt = (
        "You are checking ONE chunk of a larger codebase for a specific "
        "vulnerability class. Read only what's below.\n\n"
        f"Vulnerability class to check for: {cwe}\n\n"
        f"This is chunk {chunk_index} of {chunk_count}. It may not contain the "
        "whole picture -- if this chunk alone doesn't show the vulnerability, "
        "say CLEAN for this chunk; other chunks are checked "
        "separately.\n\n"
        "End with exactly one line: either \"FOUND: <file path>\" naming "
        "the specific file in this chunk, or \"CLEAN\". Use exactly one of "
        "those two words as your last line, matching whatever you just "
        "concluded -- do not write FOUND if your own reasoning above just "
        "concluded there's no issue, and don't write CLEAN if you just "
        "identified a real instance.\n\n"
        f"Codebase chunk:\n{chunk_text}"
    )
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3, "top_p": 1.0},
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
    repo = args.get("repo")
    cwe = args.get("cwe")
    pattern = args.get("pattern", DEFAULT_FILE_PATTERN)

    if not repo or not cwe:
        print(json.dumps({"isError": True, "error": "repo and cwe are both required"}))
        return

    try:
        root = resolve_repo_root(repo)
    except Exception as e:
        print(json.dumps({"isError": True, "error": f"could not resolve repo: {e}"}))
        return

    files = collect_files(root, pattern)
    if not files:
        print(json.dumps({"isError": True, "error": f"no files matched pattern {pattern!r}"}))
        return

    chunks = build_chunks(files, CHUNK_CHAR_BUDGET)
    findings = []
    errors = []

    for i, chunk_files in enumerate(chunks, start=1):
        chunk_text = render_chunk(chunk_files)

        # Small local models occasionally ignore the exact-wording instruction
        # and emit a verdict line that's neither "FOUND: ..." nor "CLEAN" (the
        # model's own reasoning can still be correct even when this happens --
        # it's an output-format slip, not a comprehension failure). Retry a
        # few times rather than silently treating an unparseable answer as a
        # real "CLEAN" -- those are not the same thing and must not be
        # conflated when deciding the overall verdict.
        answer = ""
        verdict_match = None
        clean_match = None
        call_error = None
        for attempt in range(1, MAX_VERDICT_ATTEMPTS + 1):
            try:
                answer = ask_ollama(cwe, chunk_text, i, len(chunks))
            except (urllib.error.URLError, TimeoutError, KeyError) as e:
                call_error = str(e)
                break
            verdict_match = VERDICT_LINE_RE.search(answer)
            clean_match = CLEAN_LINE_RE.search(answer)
            if verdict_match or clean_match:
                break

        if call_error:
            errors.append({"chunk": i, "error": call_error})
            continue

        if not verdict_match and not clean_match:
            errors.append(
                {
                    "chunk": i,
                    "error": (
                        f"model did not return a parseable FOUND/CLEAN verdict after "
                        f"{MAX_VERDICT_ATTEMPTS} attempts: {answer.strip()[:300]!r}"
                    ),
                }
            )

        likely_vulnerable = verdict_match is not None
        findings.append(
            {
                "chunk": i,
                "filesInChunk": [rel for rel, _ in chunk_files],
                "likelyVulnerable": likely_vulnerable,
                "claimedFile": verdict_match.group(1).strip() if verdict_match else None,
                "modelAnswer": answer.strip(),
            }
        )

    vulnerable_findings = [f for f in findings if f["likelyVulnerable"]]
    verdict = "vulnerable" if vulnerable_findings else "not_found"

    print(
        json.dumps(
            {
                "isError": False,
                "verdict": verdict,
                "chunkCount": len(chunks),
                "fileCount": len(files),
                "findings": findings,
                "errors": errors,
            }
        )
    )


if __name__ == "__main__":
    main()
