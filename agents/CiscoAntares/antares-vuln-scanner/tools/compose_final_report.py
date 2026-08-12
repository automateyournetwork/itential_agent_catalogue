import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo_utils import parse_args  # noqa: E402

PLATFORM_URL = os.environ.get("ITENTIAL_PLATFORM_URL", "")
CLIENT_ID = os.environ.get("ITENTIAL_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("ITENTIAL_CLIENT_SECRET", "")
PROJECT_ID = os.environ.get("ITENTIAL_PROJECT_ID", "")
WORKFLOW_NAME = os.environ.get("ITENTIAL_WORKFLOW_NAME", "CWE Find-Fix-Approve-Ship")
APPROVAL_TASK_NAME = os.environ.get("APPROVAL_TASK_NAME", "ViewData")
REQUEST_TIMEOUT_SECONDS = 30


def http_json(method, url, token=None, form_body=None, json_body=None):
    headers = {}
    data = None
    if form_body is not None:
        data = urllib.parse.urlencode(form_body).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_platform_token():
    return http_json(
        "POST",
        f"{PLATFORM_URL}/oauth/token",
        form_body={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )["access_token"]


def get_approver(token):
    """Best-effort: resolve who completed the manual approval task and when.
    Returns (username, iso_timestamp) or (None, None) if unavailable -- this
    must never raise and block the report, since approval attribution is a
    nice-to-have, not the critical fact (the PR itself is).

    There is no reliable way for a running job to learn its own job id from
    inside the workflow (job variables only cover values the workflow itself
    declared), so instead of requiring the caller to pass one in, we look up
    the most recently completed approval task across all jobs of this
    workflow. Fine for a single-operator demo; would need a real job id if
    multiple runs could be in flight concurrently.
    """
    try:
        query = urllib.parse.urlencode({"equals[name]": APPROVAL_TASK_NAME, "limit": 100})
        resp = http_json(
            "GET", f"{PLATFORM_URL}/operations-manager/tasks?{query}", token=token
        )
        candidates = [
            item
            for item in resp.get("data", [])
            if item.get("status") == "complete"
            and item.get("job", {}).get("name") == WORKFLOW_NAME
            and item.get("metrics", {}).get("user")
        ]
        if not candidates:
            return None, None
        latest = max(candidates, key=lambda item: item["metrics"].get("start_time", ""))
        metrics = latest["metrics"]
        user_id = metrics.get("user")
        end_time_ms = metrics.get("end_time")

        username = user_id
        if PROJECT_ID:
            projects = http_json(
                "GET", f"{PLATFORM_URL}/agent-project-service/projects?limit=200", token=token
            )
            for item in projects.get("data", {}).get("items", []):
                if item.get("_id") != PROJECT_ID:
                    continue
                for member in item.get("members", []):
                    if member.get("reference") == user_id:
                        username = member.get("username", user_id)
                break

        iso_ts = None
        if end_time_ms:
            import datetime

            iso_ts = datetime.datetime.utcfromtimestamp(end_time_ms / 1000).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
        return username, iso_ts
    except (urllib.error.URLError, KeyError, ValueError, TypeError):
        return None, None


def main():
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    cwe = args.get("cwe", "")
    file_path = args.get("filePath", "")
    finding_reasoning = args.get("findingReasoning", "")
    fix_explanation = args.get("fixExplanation", "")
    pr_url = args.get("prUrl", "")
    branch = args.get("branch", "")
    merged = args.get("merged", False)

    approved_by, approved_at = (None, None)
    if PLATFORM_URL and CLIENT_ID and CLIENT_SECRET:
        try:
            token = get_platform_token()
            approved_by, approved_at = get_approver(token)
        except (urllib.error.URLError, KeyError):
            approved_by, approved_at = None, None

    lines = [
        "# CWE Find-Fix-Approve-Ship — Run Report",
        "",
        "## Vulnerability",
        f"- **Class:** {cwe}",
        f"- **File:** `{file_path}`",
        f"- **Why it's vulnerable:** {finding_reasoning}",
        "",
        "## Proposed Fix (Qwen3-Coder)",
        fix_explanation or "_No explanation captured._",
        "",
        "## Approval",
        f"- **Approved by:** {approved_by or 'unknown (could not resolve approver from job history)'}",
        f"- **Approved at:** {approved_at or 'unknown'}",
        "",
        "## Shipped",
        f"- **Branch:** `{branch}`" if branch else "- **Branch:** _not created_",
        f"- **Pull Request:** {pr_url}" if pr_url else "- **Pull Request:** _not created_",
        f"- **Merged:** {'Yes' if merged else 'No'}",
    ]
    final_report = "\n".join(lines)

    print(
        json.dumps(
            {
                "isError": False,
                "finalReport": final_report,
                "approvedBy": approved_by,
                "approvedAt": approved_at,
            }
        )
    )


if __name__ == "__main__":
    main()
