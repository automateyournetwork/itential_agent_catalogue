import hashlib
import json
import os
import subprocess

CACHE_DIR = os.environ.get("ANTARES_VULN_CACHE_DIR", "/tmp/antares-vuln-scanner-cache")
CLONE_TIMEOUT_SECONDS = 30


def resolve_repo_root(repo_url):
    """Clone repo_url into a deterministic local cache dir (idempotent) and
    return that dir as the confinement root for this call.

    Uses subprocess with an argument list (never shell=True), so nothing in
    repo_url is ever interpreted by a shell.
    """
    if not repo_url:
        raise ValueError("repo is required")

    key = hashlib.sha256(repo_url.encode("utf-8")).hexdigest()[:16]
    root = os.path.realpath(os.path.join(CACHE_DIR, key))

    if not os.path.isdir(root):
        os.makedirs(CACHE_DIR, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, root],
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise ValueError(f"git clone failed for {repo_url!r}: {result.stderr.strip()[:300]}")

    return root


def safe_path(root, rel_path):
    """Resolve rel_path against root, refusing anything that escapes it."""
    candidate = os.path.realpath(os.path.join(root, rel_path or "."))
    if not (candidate == root or candidate.startswith(root + os.sep)):
        raise ValueError(f"path escapes repo root: {rel_path!r}")
    return candidate


def parse_args(argv):
    # IAG sends every decorator field as --key=value, including unset ones
    # (value ''). Omit those, and JSON-decode the rest so lists/ints survive.
    args = {}
    for item in argv:
        if not item.startswith("--") or "=" not in item:
            continue
        key, _, value = item[2:].partition("=")
        if value == "":
            continue
        try:
            args[key] = json.loads(value)
        except json.JSONDecodeError:
            args[key] = value
    return args
