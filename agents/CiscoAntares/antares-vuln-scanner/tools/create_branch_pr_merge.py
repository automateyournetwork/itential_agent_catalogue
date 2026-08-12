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
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402

CLONE_TIMEOUT_SECONDS = 30
GIT_TIMEOUT_SECONDS = 20
GH_API_TIMEOUT_SECONDS = 30
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_API_BASE = "https://api.github.com"


def slugify(text, max_len=30):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:max_len] or "fix"


def owner_repo_from_url(url):
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?/?$", url)
    if not match:
        raise RuntimeError(f"could not parse owner/repo from {url!r}")
    return match.group(1), match.group(2)


def authed_clone_url(url):
    if not GH_TOKEN:
        return url
    return re.sub(r"^https://", f"https://x-access-token:{GH_TOKEN}@", url)


def run(cmd, cwd, timeout, step):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"{step} failed: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def gh_api(method, path, body=None):
    if not GH_TOKEN:
        raise RuntimeError("GH_TOKEN is not set -- cannot call the GitHub API")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{GH_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=GH_API_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} -> {e.code}: {detail[:500]}")


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
        owner, repo_name = owner_repo_from_url(repo)
        run(["git", "clone", "--depth", "1", authed_clone_url(repo), clone_dir], workdir, CLONE_TIMEOUT_SECONDS, step)

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
        default_branch = run(
            ["git", "remote", "show", "origin"], clone_dir, GIT_TIMEOUT_SECONDS, step
        )
        base_match = re.search(r"HEAD branch:\s*(\S+)", default_branch)
        base_branch = base_match.group(1) if base_match else "main"
        pr = gh_api(
            "POST",
            f"/repos/{owner}/{repo_name}/pulls",
            {"title": pr_title, "body": pr_body, "head": branch, "base": base_branch},
        )
        pr_url = pr["html_url"]
        pr_number = pr["number"]

        step = "merge PR"
        gh_api(
            "PUT",
            f"/repos/{owner}/{repo_name}/pulls/{pr_number}/merge",
            {"merge_method": "squash"},
        )

        print(json.dumps({"isError": False, "branch": branch, "prUrl": pr_url, "merged": True}))
    except (subprocess.TimeoutExpired, RuntimeError) as e:
        print(json.dumps({"isError": True, "step": step, "error": str(e)}))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
