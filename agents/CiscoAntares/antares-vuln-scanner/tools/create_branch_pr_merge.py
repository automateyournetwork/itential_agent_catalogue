import argparse
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402

CLONE_TIMEOUT_SECONDS = 30
GIT_TIMEOUT_SECONDS = 20
GH_TIMEOUT_SECONDS = 30


def slugify(text, max_len=30):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:max_len] or "fix"


def run(cmd, cwd, timeout, step):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"{step} failed: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    repo = args.get("repo")
    file_path = args.get("filePath")
    cwe = args.get("cwe", "")
    commit_message = args.get("commitMessage") or f"Fix {cwe or 'vulnerability'} in {file_path}"
    pr_title = args.get("prTitle") or commit_message
    pr_body = args.get("prBody") or f"Automated fix for {cwe}."

    # Prefer base64 -- the platform's runService task has been observed to
    # mangle multi-line, quote-containing CLI args ("EOF found when expecting
    # closing quote"), which plain source code triggers constantly. Base64 is
    # always a plain alphanumeric string, so it can never hit that bug.
    new_content_b64 = args.get("newContentBase64")
    new_content = args.get("newContent")
    if new_content_b64:
        try:
            new_content = base64.b64decode(new_content_b64).decode("utf-8")
        except Exception as e:
            print(json.dumps({"isError": True, "step": "decode", "error": f"invalid newContentBase64: {e}"}))
            return

    missing = [k for k, v in (("repo", repo), ("filePath", file_path), ("newContent", new_content)) if not v]
    if missing:
        print(json.dumps({"isError": True, "step": "validate", "error": f"missing required: {missing}"}))
        return

    workdir = tempfile.mkdtemp(prefix="antares-fix-")
    clone_dir = os.path.join(workdir, "repo")
    step = "clone"
    try:
        run(["git", "clone", "--depth", "1", repo, clone_dir], workdir, CLONE_TIMEOUT_SECONDS, step)

        # Scoped to this clone only, not --global -- the environment running
        # this script (a Gateway container) has no git identity configured,
        # and this must work regardless of what's set up on the host.
        step = "configure git identity"
        run(["git", "config", "user.email", "antares-cwe-bot@users.noreply.github.com"], clone_dir, GIT_TIMEOUT_SECONDS, step)
        run(["git", "config", "user.name", "Antares CWE Bot"], clone_dir, GIT_TIMEOUT_SECONDS, step)

        branch = f"fix/{slugify(cwe or file_path)}-{secrets.token_hex(3)}"
        step = "create branch"
        run(["git", "checkout", "-b", branch], clone_dir, GIT_TIMEOUT_SECONDS, step)

        step = "write file"
        target = os.path.realpath(os.path.join(clone_dir, file_path))
        if not target.startswith(os.path.realpath(clone_dir) + os.sep):
            raise RuntimeError(f"{step} failed: filePath escapes repo root: {file_path!r}")
        with open(target, "w") as f:
            f.write(new_content)

        step = "commit"
        run(["git", "add", file_path], clone_dir, GIT_TIMEOUT_SECONDS, step)
        run(["git", "commit", "-m", commit_message], clone_dir, GIT_TIMEOUT_SECONDS, step)

        step = "push"
        run(["git", "push", "-u", "origin", branch], clone_dir, GIT_TIMEOUT_SECONDS, step)

        step = "create PR"
        pr_url = run(
            ["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--head", branch],
            clone_dir,
            GH_TIMEOUT_SECONDS,
            step,
        )

        step = "merge PR"
        run(["gh", "pr", "merge", branch, "--squash", "--delete-branch"], clone_dir, GH_TIMEOUT_SECONDS, step)

        print(json.dumps({"isError": False, "branch": branch, "prUrl": pr_url, "merged": True}))
    except (subprocess.TimeoutExpired, RuntimeError) as e:
        print(json.dumps({"isError": True, "step": step, "error": str(e)}))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
