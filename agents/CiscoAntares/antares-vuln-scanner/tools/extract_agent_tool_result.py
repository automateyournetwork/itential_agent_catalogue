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
REQUEST_TIMEOUT_SECONDS = 30


def http_json(method, url, token=None, form_body=None):
    headers = {}
    data = None
    if form_body is not None:
        data = urllib.parse.urlencode(form_body).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
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


def main():
    """Bridge between a real agent session and the deterministic extraction
    chain that already exists for the equivalent runService call.

    An agent's own final answer is the model paraphrasing a tool's result in
    its own words -- not safe to regex-parse for structured fields. The
    actual ground truth is the tool-call event in the session's own message
    history, which carries the tool's exact stdout untouched. This prints
    that stdout back out unchanged, so it can be fed into the same
    query/parse chain that a direct runService call would produce.
    """
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    session_id = args.get("sessionId")
    tool_name = args.get("toolName")

    if not session_id:
        print(json.dumps({"isError": True, "error": "missing required: ['sessionId']"}))
        return

    try:
        token = get_platform_token()
        messages = http_json(
            "GET",
            f"{PLATFORM_URL}/agent-session-manager/sessions/{session_id}/messages",
            token=token,
        )
    except (urllib.error.URLError, KeyError) as e:
        print(json.dumps({"isError": True, "error": f"session lookup failed: {e}"}))
        return

    tool_event = None
    for event in messages:
        if event.get("type") != "tool-execution":
            continue
        if tool_name and event.get("data", {}).get("toolName") != tool_name:
            continue
        tool_event = event
        break

    if not tool_event:
        print(
            json.dumps(
                {"isError": True, "error": f"no tool-execution event found (toolName={tool_name!r})"}
            )
        )
        return

    stdout = tool_event.get("data", {}).get("output", {}).get("result", {}).get("stdout", "")
    print(stdout)


if __name__ == "__main__":
    main()
