# Antares-1B Vulnerability Scanner Agent

A FlowAI agent built specifically for Cisco's Antares-1B — a small (1B-class) model
from Cisco Foundation AI, built on IBM Granite 4.0, specialized for **CWE
vulnerability localization in source code**. This is not another Catalyst Center
API-orchestration agent; it's shaped around what this specific model was actually
trained to do: explore a codebase via `grep`/`find`/`cat`-style primitives and
report which files contain a described vulnerability class.

## What this agent does

Given a CWE description (e.g. "CWE-78: OS Command Injection"), the agent searches
a small bundled sample repository (`sample-repo/`) for matching code and reports
either the specific vulnerable file(s) with reasoning, or that nothing was found.

`sample-repo/` is a tiny, realistic network-diagnostics CLI with one planted
CWE-78 injection (`diagnostics/network.py`, unsanitized host interpolated into a
shell command) plus several safe decoy files, so the search isn't trivial.

## Why this agent looks different from the Catalyst Center agents

Those agents call structured, read-only Catalyst Center API tools. Antares-1B's
own training used a narrow, bounded terminal loop: emit a `<tool_call>`, get a
`<tool_response>`, repeat up to ~15 rounds, then terminate via
`submit_vulnerable_files` or `submit_no_vulnerability_found`. This agent's
tools mirror that shape directly (`grep_repo`, `find_files`, `read_file`, plus
the two submit tools) instead of forcing it into an unrelated tool-calling
pattern — see `../../Cisco Catalyst Center/` for contrast.

## Safety design

Cisco's own model card recommends running the model's shell commands inside an
ephemeral, network-disabled container. This implementation takes a different
but equally effective approach for this scope: the tools never shell out at
all. `grep_repo`/`find_files`/`read_file` are pure-Python re-implementations
confined to `sample-repo/` via `tools/_repo_utils.py`'s `safe_path()` — any
path that would escape the sample repo root raises an error before touching
disk. There is no command-execution surface for the model to exploit, so
there's nothing to sandbox against.

## Source of truth for behavior

The system prompt is at `itential/agent.spec.md` (section "Instructions") —
treat that as canonical.

## Testing without Itential

Every tool is a standalone script under `tools/`, runnable directly:

```bash
cd tools
python3 find_files.py --pattern='*.py'
python3 grep_repo.py --pattern='os\.(system|popen)'
python3 read_file.py --path='diagnostics/network.py'
python3 submit_vulnerable_files.py --files='["diagnostics/network.py"]' --reasoning='...'
```

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration: each tool is
registered as its own `iagctl create service python-script` pointing at this
same GitHub repo, no separate wrapper repo needed since the tools and the
target sample codebase live side by side here.
