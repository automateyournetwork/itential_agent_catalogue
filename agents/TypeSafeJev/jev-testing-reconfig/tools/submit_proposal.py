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
    """Terminal tool for the Reconfig Proposer agent. Call exactly once, when
    the proposal is ready. Captures BOTH the raw device state the proposal
    was based on AND the proposed changes -- not the agent's own prose --
    so the workflow can hand real telemetry to Jev and to the human
    reviewer, not a paraphrase (same reasoning as this repo's
    extract_agent_tool_result: an agent's own summary is not safe to trust
    for structured downstream use).
    """
    _, unknown = argparse.ArgumentParser().parse_known_args()
    args = parse_args(unknown)
    summary = args.get("summary")
    current_state_raw = args.get("current_state")
    devices_raw = args.get("devices")

    if not summary:
        print(json.dumps({"isError": True, "error": "missing required: ['summary']"}))
        return
    if not current_state_raw:
        print(json.dumps({"isError": True, "error": "missing required: ['current_state']"}))
        return
    if not devices_raw:
        print(json.dumps({"isError": True, "error": "missing required: ['devices']"}))
        return

    try:
        current_state = _as_dict(current_state_raw, "current_state")
        devices = _as_dict(devices_raw, "devices")
    except ValueError as e:
        print(json.dumps({"isError": True, "error": str(e)}))
        return

    missing = REQUIRED_DEVICES - set(devices.keys())
    if missing:
        print(
            json.dumps(
                {
                    "isError": True,
                    "error": f"devices is missing required device(s): {sorted(missing)}",
                }
            )
        )
        return

    for name, entry in devices.items():
        if not isinstance(entry, dict) or "config_commands" not in entry or "reasoning" not in entry:
            print(
                json.dumps(
                    {
                        "isError": True,
                        "error": f"devices.{name} must be an object with 'config_commands' (list of strings) and 'reasoning' (string)",
                    }
                )
            )
            return

    print(
        json.dumps(
            {
                "isError": False,
                "summary": summary,
                "current_state": current_state,
                "devices": devices,
            }
        )
    )


if __name__ == "__main__":
    main()
