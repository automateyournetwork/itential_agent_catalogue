import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import parse_args  # noqa: E402

TYPESAFE_API_BASE = os.environ.get("TYPESAFE_API_BASE", "https://api.typesafe.ai")
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
REQUEST_TIMEOUT_SECONDS = 30


def main():
    """Gateway IAG wrapper around TypeSafe's native Jev/System One endpoint
    (POST /v1/systemone). Not OpenAI-compatible -- this is a direct pass-
    through of TypeSafe's own {state, model, questions} -> {answers, usage}
    schema, not a chat-completions translation. See this folder's README.md
    for why it's wired this way (Itential Model Registry has no provider
    type for this schema; this tool lets a chat-based FlowAI agent call Jev
    as a fast structured-decision sub-tool instead).
    """
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    state = args.get("state")
    questions_raw = args.get("questions")
    model = args.get("model") or "jev-latest"

    if not state:
        print(json.dumps({"isError": True, "error": "missing required: ['state']"}))
        return
    if not questions_raw:
        print(json.dumps({"isError": True, "error": "missing required: ['questions']"}))
        return
    if not TYPESAFE_API_KEY:
        print(json.dumps({"isError": True, "error": "TYPESAFE_API_KEY is not set on this service"}))
        return

    # parse_args already JSON-decodes any value that parses as JSON, so
    # questions may arrive already-parsed (a real dict) or as a raw string --
    # handle both rather than assuming the caller's exact wire format.
    if isinstance(questions_raw, str):
        try:
            questions = json.loads(questions_raw)
        except json.JSONDecodeError as e:
            print(json.dumps({"isError": True, "error": f"questions is not valid JSON: {e}"}))
            return
    else:
        questions = questions_raw

    payload = json.dumps({"state": state, "model": model, "questions": questions}).encode("utf-8")
    req = urllib.request.Request(
        f"{TYPESAFE_API_BASE}/v1/systemone",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            # Assumed standard bearer auth -- TypeSafe's docs didn't confirm
            # the exact header at the time this was written. Verify against
            # your TypeSafe dashboard/quickstart; swap for an X-API-Key
            # header here if that's what it actually expects.
            "Authorization": f"Bearer {TYPESAFE_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        print(json.dumps({"isError": True, "error": f"TypeSafe API HTTP {e.code}: {detail}"}))
        return
    except urllib.error.URLError as e:
        # Do NOT let a network/connectivity failure look like a real Jev
        # answer -- a caller must be able to tell "Jev evaluated and said
        # no" apart from "couldn't reach Jev at all". Same trap documented
        # for the Ollama-down case in the CWE pipeline: a swallowed network
        # error and a genuine negative result must never look identical.
        print(json.dumps({"isError": True, "error": f"TypeSafe API unreachable: {e.reason}"}))
        return
    except json.JSONDecodeError as e:
        print(json.dumps({"isError": True, "error": f"TypeSafe API returned non-JSON response: {e}"}))
        return

    print(
        json.dumps(
            {
                "isError": False,
                "model": body.get("model", model),
                "answers": body.get("answers", {}),
                "usage": body.get("usage", {}),
            }
        )
    )


if __name__ == "__main__":
    main()
