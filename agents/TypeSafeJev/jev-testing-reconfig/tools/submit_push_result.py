import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import parse_args  # noqa: E402

REQUIRED_DEVICES = {"R1", "R2", "SW1", "SW2"}


def _as_dict(value, field_name):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"{field_name} is not valid JSON: {e}")
    raise ValueError(f"{field_name} must be a JSON object or object-as-string")


def main():
    """Terminal tool for the Reconfig Pusher agent. Call exactly once, after
    pushing the human-approved config to all four devices AND resampling
    their state (pyats_device_health / pyats_get_neighbors) afterward.
    Like submit_proposal.py, this captures the raw resampled state and raw
    per-device push results, not the agent's prose -- that raw state is
    what gets handed to Jev for the post-push probability-of-success check.
    """
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    summary = args.get("summary")
    post_state_raw = args.get("post_state")
    results_raw = args.get("results")

    if not summary:
        print(json.dumps({"isError": True, "error": "missing required: ['summary']"}))
        return
    if not post_state_raw:
        print(json.dumps({"isError": True, "error": "missing required: ['post_state']"}))
        return
    if not results_raw:
        print(json.dumps({"isError": True, "error": "missing required: ['results']"}))
        return

    try:
        post_state = _as_dict(post_state_raw, "post_state")
        results = _as_dict(results_raw, "results")
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return

    missing = REQUIRED_DEVICES - set(results.keys())
    if missing:
        print(
            json.dumps(
                {
                    "isError": True,
                    "error": f"results is missing required device(s): {sorted(missing)}",
                }
            )
        )
        return

    for name, entry in results.items():
        if not isinstance(entry, dict) or "success" not in entry:
            print(
                json.dumps(
                    {
                        "isError": True,
                        "error": f"results.{name} must be an object with at least 'success' (boolean)",
                    }
                )
            )
            return

    print(
        json.dumps(
            {
                "isError": False,
                "summary": summary,
                "post_state": post_state,
                "results": results,
            }
        )
    )


if __name__ == "__main__":
    main()
