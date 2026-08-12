# Find, Fix, Approve, Ship: local LLMs doing real security work on Itential

This is a walk-through of one real, live run of the **CWE Find-Fix-Approve-Ship**
pipeline — job `5c333de2cebf430d99718904`, which found a real vulnerability,
proposed a real fix, waited for a human, and opened and merged a real GitHub
pull request (automateyournetwork/netdiag-vuln-sample#5) — with two free,
locally-hosted models doing all the "thinking," and Itential doing all the
orchestration, state, and safety gating.

## The cast

**Two Ollama models, running on a Mac, never leaving the local network:**

- **Antares-1B** (`antares-1b:latest`) — Cisco's ~1.8B security-focused model.
  Trained on a narrow terminal loop (grep/find/read a codebase, then submit a
  verdict). Its job here: read code, decide if it's vulnerable, explain why.
- **Qwen3-Coder** (`qwen3-coder:latest`, 18GB) — a general coding model. Its
  job: given the vulnerable file and Antares' reasoning, write the corrected
  version and explain the change.

**Itential components, and what each one actually does:**

| Component | Role in this pipeline |
|---|---|
| **Model Registry / IAG provider** | Points at Ollama's HTTP API on the Mac; this is *only* used by the two standalone demo agents, not the production workflow (see below) |
| **IAG Gateway** (`john_capo_cluster`) | Hosts five Python scripts as registered services — this is where the actual Ollama calls happen for the real pipeline |
| **Operations Manager / Automation Studio** | The workflow engine — owns the job, the state machine, the variables, the transitions |
| **Work Center** | Where a human sees the proposed fix and clicks Approve/Reject — the one non-automatable step by design |
| **Job / task iteration records** | The real audit trail — every task's exact input and output, forever (well, for a retention window) |

## Why there's no agent session for the real pipeline

Itential gives you two ways to make an LLM do something in a workflow:

- **`runAgent`** — starts a real FlowAI agent session with tools and a
  multi-turn loop. Shows up in Work Center's session logs.
- **`runService`** — calls a plain script on the Gateway once, synchronously,
  gets back stdout. No session, no loop.

Early builds of this pipeline used `runAgent` with real tool-calling
(`grep_repo`, `find_files`, `read_file`, plus submit tools) — architecturally
the "correct" approach, mirroring how Antares-1B was actually trained. But
small local models turned out to be unreliable multi-turn tool-callers: runs
that reasoned about a next step and then never emitted the tool call, one run
that combined several grep patterns into one malformed regex that silently
matched nothing, one run with cross-contaminated tool arguments from an
unrelated agent (an Ollama tool-schema-grammar bug).

The fix wasn't a better prompt — it was removing the loop. `scan_repo_deep.py`
and `propose_fix.py` are deterministic Python scripts that call Ollama's HTTP
API directly, once, and parse the response with a strict regex. They're
registered as IAG services and invoked with `runService`, not `runAgent`. The
model still does 100% of the reasoning — same weights, same task — it just
never has to decide what to do next, because there's exactly one decision to
make per call, and Itential's workflow engine makes every *other* decision
(what to do with the result, whether to branch, when to pause for a human).

That's the actual thesis of this pipeline: **put the probabilistic part where
it's good (single-shot judgment) and the deterministic part where it's needed
(control flow, state, gating)**, and don't blur the line between them.

## Blow-by-blow: what happened in job `5c333de2cebf430d99718904`

```
POST /operations-manager/jobs/start
  {"workflow": "CWE Find-Fix-Approve-Ship",
   "options": {"variables": {
     "repo": "https://github.com/automateyournetwork/netdiag-vuln-sample",
     "cwe": "CWE-78: OS Command Injection"}}}
```

**1. `a1` (merge) → `a2` (runService: `scan_repo_deep`)**
Builds `{repo, cwe}` and calls the scan service. Inside that one script call:
clone the repo fresh into a scratch dir, chunk every file into small windows,
and for *each chunk*, one direct HTTP call to Ollama running Antares-1B:
"here's this chunk, here's the CWE description, answer `FOUND: <file>` or
`CLEAN`." No tool loop — the script does the looping over chunks, the model
just judges one chunk at a time. First hit wins; the script returns
`{"verdict": "vulnerable", "files": [...], "reasoning": "..."}`.

**2. `c1`→`a3`→`c7`→`a4`→`c5`→`a5`→`c6`→`a6` (query/parse/newVariable chain)**
Pure plumbing: pull `verdict`, `cweFlaggedPath`, and the model's reasoning
text out of the JSON stdout and store them as job variables. No model
involved — this is the deterministic half doing bookkeeping.

**3. `a7` (evaluation)**
`if verdict == "vulnerable"` → continue; otherwise → end the job and report
clean. This run: vulnerable, in `diagnostics/network.py`, reasoning: *"The
`ping_host` function constructs a shell command using user input... executes
it with `os.popen`... CWE-78."* Correct.

**4. `c4`→`a8` (runService: `read_file`)→`c2`→`a9`→`c8`→`aa`**
Fetch the *current* full content of the flagged file (fresh, not whatever the
scanner chunked) and store it as `fileContent`.

**5. `ab` (merge)→`ac` (runService: `propose_fix`)**
One more single Ollama call, this time to Qwen3-Coder: "here's the vulnerable
file, here's why it's vulnerable, write the fixed version and explain it."
Returns fixed code (plain *and* base64-encoded — more on why below) plus an
explanation (also both forms).

Its actual fix, verbatim from this run:

```python
# before
command = f"ping -c 1 {host}"
return os.popen(command).read()

# after
command = ["ping", "-c", "1", host]
return subprocess.run(command, capture_output=True, text=True).stdout
```

Correct: shell string → argv list, `os.popen` → `subprocess.run`, no shell
interpretation of the host argument anywhere.

**6. `ad`→`c3`/`c9`/`ca`/`cb`→`ae`/`af`/`cc` (extraction chain)**
More deterministic plumbing: pull `fixedCode`, `explanation`,
`fixedCodeBase64`, and (as of today) `explanationBase64` into job variables.

**7. `b1` (manual / ViewData) — the one non-automatable step**
The workflow *stops*. Not polling, not timing out — genuinely paused,
waiting on a human. Work Center renders the fix explanation and two buttons:
Approve / Reject. There is no API to complete this task programmatically;
only a real person clicking a real button advances the job. This is the
actual safety boundary of the whole system — everything upstream is "an
opinion," nothing downstream of this task is reversible.

**8. On Approve → `b2` (merge)→`b3` (runService: `create_branch_pr_merge`)**
Real git, for real: clone with push credentials, `git checkout -b
fix/cwe-78-os-command-injection-e0b59f`, write the fixed file, commit, push,
open a PR via the GitHub REST API (no `gh` CLI on the Gateway container —
direct HTTPS calls with a token), then merge it. Result this run: real PR
[#5](https://github.com/automateyournetwork/netdiag-vuln-sample/pull/5),
merged.

**9. `d1`→…→`d9`→`da` (runService: `compose_final_report`)**
New today. Extract `prUrl`/`branch`/`merged` from the git-ops result, then
call one more deterministic script — no LLM this time — that:
  - Assembles the technical write-up (vulnerability, reasoning, fix, PR link)
  - **Authenticates to the Itential Platform itself** (OAuth
    client-credentials) and looks up who actually clicked Approve and when,
    by querying the workflow's own approval-task history and cross-referencing
    the CWE project's member list to turn a user ID into a real username.

Real output from this run:

```
## Approval
- Approved by: john.capobianco@itential.com
- Approved at: 2026-08-12 22:00:53 UTC

## Shipped
- Branch: fix/cwe-78-os-command-injection-e0b59f
- Pull Request: https://github.com/automateyournetwork/netdiag-vuln-sample/pull/5
- Merged: Yes
```

That final report is a genuinely interesting hybrid: assembled by
deterministic code, but every fact in it — the vulnerability, the fix
rationale, the approver, the PR — traces back to either a model judgment or a
real platform/GitHub event. Nothing in it is fabricated or templated filler.

## The part that isn't glamorous but is the actual lesson

Two real platform bugs surfaced (and got fixed) specifically because of this
run:

- The Gateway's `runService` has a real CLI-parsing bug: multi-line,
  quote-containing string arguments can crash with `"EOF found when
  expecting closing quote"` — while the task still reports `status:
  complete`, silently swallowing the failure. First hit this with raw source
  code; today it hit again on the *fix explanation* text once it contained
  markdown backticks. Fix both times: base64-encode the string, decode inside
  the script. Plain alphanumeric text can never trigger a shell-quoting bug.
- Boolean decorator fields don't arrive as `--merged=true` — they arrive as a
  bare `--merged` flag (present = true, absent = false). A naive `--key=value`
  parser silently drops any argv item without an `=`, which is why the first
  end-to-end run of the new report correctly detected and merged PR #5, but
  still printed "Merged: No."

Neither of these would show up in a code review of the Python scripts in
isolation — they're both "the platform's calling convention doesn't match
what I assumed," discoverable only by actually running the thing and reading
the real task iteration record, not the job's own summary view (which shows
template placeholders, not resolved runtime values).

## The takeaway

Nothing here required a frontier model or a cloud API call. It required:
one small model that's good at narrow judgment calls, one mid-size model
that's good at writing code, deterministic Python gluing each of them to
exactly one well-scoped task, Itential's workflow engine owning every branch
and every piece of state, and a human in the loop at the one point where a
mistake would actually cost something.
