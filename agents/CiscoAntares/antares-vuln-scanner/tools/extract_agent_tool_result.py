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

    # A model that gets its first tool call wrong (extra/invented params,
    # missing schema fields it hallucinates around) can retry the same tool
    # more than once in one session, even when told to call it exactly once.
    # The first attempt's event is real but useless -- its output is a
    # gateway-level error shape ({state, domain, code, message}), not the
    # script's own {result: {stdout}} shape. Always prefer the LAST matching
    # tool-execution event that actually carries a real stdout, so an early
    # failed/malformed attempt never wins over a later successful retry.
    tool_event = None
    for event in messages:
        if event.get("type") != "tool-execution":
            continue
        if tool_name and event.get("data", {}).get("toolName") != tool_name:
            continue
        output = event.get("data", {}).get("output", {})
        if "stdout" not in output.get("result", {}):
            continue
        tool_event = event

    if not tool_event:
        print(
            json.dumps(
                {
                    "isError": True,
                    "error": f"no successful tool-execution event found (toolName={tool_name!r})",
                }
            )
        )
        return

    stdout = tool_event["data"]["output"]["result"]["stdout"]
    print(stdout)


if __name__ == "__main__":
    main()
