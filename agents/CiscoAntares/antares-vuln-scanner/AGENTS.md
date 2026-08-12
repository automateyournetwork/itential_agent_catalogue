# Antares-1B Vulnerability Scanner Agent

A FlowAI agent built specifically for Cisco's Antares-1B — a small (1B-class) model
from Cisco Foundation AI, built on IBM Granite 4.0, specialized for **CWE
vulnerability localization in source code**. This is not another Catalyst Center
API-orchestration agent; it's shaped around what this specific model was actually
trained to do: explore a codebase via `grep`/`find`/`cat`-style primitives and
report which files contain a described vulnerability class.

## Two variants exist here — read this before picking one

**`itential/agent.spec.md`** documents the tool-calling variant: `find_files`,
`grep_repo`, `read_file`, plus two submit tools, matching Antares-1B's real
training loop. This is the architecturally correct approach for arbitrarily
large real-world repos, but real testing surfaced a genuine reliability problem
(see "What actually happened" below) — treat it as not demo-safe without further
work.

**The no-tools, full-codebase variant** (see `tests/missions/happy-path.json` for
the real captured run) embeds the entire target codebase directly in the prompt
as plain text and asks the model to answer in a single shot, no tool loop at all.
This only works because the target codebase is small enough to fit in context
(the bundled sample is ~83 lines). It correctly found the planted vulnerability
in under 3 seconds with a clean explanation — the best working demonstration in
this folder right now.

## What actually happened, honestly

Across multiple real attempts, the tool-calling variant repeatedly failed to
complete the task correctly:
- Two full runs never reached a `submit_*` call at all — the model announced a
  next step in its reasoning and then simply stopped generating tool calls,
  despite an explicit instruction to always submit before finishing.
- One run reached `submit_no_vulnerability_found` — the wrong verdict. Root
  cause: instead of testing one candidate pattern at a time as instructed, it
  combined several into one hand-written regex (`os\.system|subprocess|Popen\(
  |popen\("|shell=True|...`); the `popen\("` branch requires a literal quote
  right after `popen(`, which the real vulnerable line (`os.popen(command)`)
  doesn't have, so it silently matched nothing.
- One earlier run showed a deeper infrastructure bug (now fixed): tool-call
  arguments got cross-contaminated with an `inventory` field from a completely
  unrelated agent (Linux Diagnostics), including a real `gateway_manager`-domain
  404 identical in shape to that agent's own error — almost certainly Ollama's
  automatic tool-schema-grammar generation misbehaving for this hand-rolled
  Modelfile (which only defines a plain chat `TEMPLATE`, never an explicit
  `{{ .Tools }}` block).

One concrete fix already landed: `grep_repo` now also accepts a `patterns` list
of plain literal strings (escaped and OR'd internally) instead of forcing the
model to hand-write a combined regex — this directly targets the most common
real failure. It has not yet been re-verified end-to-end after that change.

**The no-tools single-shot test exists specifically to answer "is this a model
capability problem or a tool-calling problem?"** — and the answer is tool-calling.
Given the exact same codebase and question with no tools involved, the model
correctly found and explained the vulnerability in one shot. Don't conclude from
the tool-calling failures that the model can't do this job; it can, when it
doesn't have to also drive a multi-turn tool loop reliably.

## What this agent does (tool-calling variant)

Given a `repo` (a real git URL — see `itential/agent.spec.md` for why this isn't
a hardcoded path) and a CWE description, the agent explores that repo with
`find_files`/`grep_repo`/`read_file` and reports either the specific vulnerable
file(s) with reasoning, or that nothing was found.

The default target, `automateyournetwork/netdiag-vuln-sample`, is a tiny,
realistic network-diagnostics CLI with one planted CWE-78 injection
(`diagnostics/network.py`, unsanitized host interpolated into a shell command)
plus several safe decoy files, so the search isn't trivial. It's a standalone
repo (not nested in this monorepo) specifically so `repo` is a genuine
arbitrary-URL input, not a subdirectory hack.

## Why this agent looks different from the Catalyst Center agents

Those agents call structured, read-only Catalyst Center API tools. Antares-1B's
own training used a narrow, bounded terminal loop: emit a `<tool_call>`, get a
`<tool_response>`, repeat up to ~15 rounds, then terminate via
`submit_vulnerable_files` or `submit_no_vulnerability_found`. This agent's
tools mirror that shape directly instead of forcing it into an unrelated
tool-calling pattern — see `../../Cisco Catalyst Center/` for contrast.

## Safety design

Cisco's own model card recommends running the model's shell commands inside an
ephemeral, network-disabled container. This implementation takes a different
but equally effective approach for this scope: the tools never shell out for
search/read operations at all. `grep_repo`/`find_files`/`read_file` are
pure-Python re-implementations, and `tools/_repo_utils.py`'s `safe_path()`
confines every path to the resolved repo root — any path that would escape it
raises an error before touching disk. The one real subprocess call
(`resolve_repo_root`'s `git clone`) uses an argument list, never `shell=True`,
so nothing in the `repo` URL is ever interpreted by a shell.

## Source of truth for behavior

The system prompt is at `itential/agent.spec.md` (section "Instructions") —
treat that as canonical.

## Testing without Itential

Every tool is a standalone script under `tools/`, runnable directly:

```bash
cd tools
python3 find_files.py --repo='https://github.com/automateyournetwork/netdiag-vuln-sample' --pattern='*.py'
python3 grep_repo.py --repo='https://github.com/automateyournetwork/netdiag-vuln-sample' --patterns='["os.system","os.popen","subprocess"]'
python3 read_file.py --repo='https://github.com/automateyournetwork/netdiag-vuln-sample' --path='diagnostics/network.py'
python3 submit_vulnerable_files.py --files='["diagnostics/network.py"]' --reasoning='...'
```

## Testing with Itential

See `itential/agent.spec.md` for the FlowAI-specific registration: each tool is
registered as its own `iagctl create service python-script` + matching
`iagctl create decorator` pointing at this same GitHub repo. Two gotchas found
the hard way, worth checking before assuming something else is broken:
- A service/decorator you just created may show up on `/tools` as
  `active: false` until you `POST /tools/discover` again — a freshly-created
  agent referencing an inactive tool comes back `authorized: false`, and
  `run-agent` against it fails with a generic "could not find Agent" error that
  has nothing to do with the agent actually existing.
- A folder name with a space in it (e.g. an earlier `Cisco Antares/`) breaks
  `iagctl create service python-script --filename` — it word-splits the path.
  Keep repo-relative filenames space-free.
