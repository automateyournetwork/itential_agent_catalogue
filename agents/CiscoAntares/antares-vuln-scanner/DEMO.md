# Demo script: CWE Find-Fix-Approve-Ship

A live, recordable walkthrough of Antares-1B + Qwen3-Coder + Work Center
finding, fixing, and shipping a real CWE-78 fix on a real GitHub repo.

## Before you hit record

1. **Reset the target repo** so there's a real vulnerability to find:
   ```bash
   cd /path/to/netdiag-vuln-sample   # or clone fresh: git clone https://github.com/automateyournetwork/netdiag-vuln-sample
   python3 reset_demo.py
   ```
   Confirms `diagnostics/network.py` is vulnerable again on `main`.

2. **Confirm no stray pending approvals** in Work Center from a prior run —
   reject/clear any leftover jobs so the one you trigger live is the only
   one waiting.

3. **Confirm Ollama models are loaded and warm** (optional, avoids a cold-start
   pause on camera):
   ```bash
   ollama run antares-1b:latest "test"
   ollama run qwen3-coder:latest "test"
   ```

## The recording — 4 beats

### Beat 1 — Show the vulnerability exists (30s)
Open `diagnostics/network.py` on GitHub (or in an editor) and point at the
line: `os.popen(f"ping -c 1 {host}")` — untrusted `host` interpolated
straight into a shell string. This is what the pipeline is about to find on
its own.

### Beat 2 — Trigger the pipeline (30s)
In Itential, start the **"CWE Find-Fix-Approve-Ship"** workflow with:
```json
{"repo": "https://github.com/automateyournetwork/netdiag-vuln-sample", "cwe": "CWE-78: OS Command Injection"}
```
Narrate what's about to happen: Antares-1B (a 1.8B local model) will scan the
repo, Qwen3-Coder (local, 18GB) will propose a fix, then it pauses for human
approval — nothing touches the real repo without a person clicking Approve.

### Beat 3 — Work Center approval (the key moment)
Once the job reaches the manual task, open Work Center and show:
- The verdict Antares-1B reached and why (its reasoning, not just a label)
- The exact diff Qwen3-Coder proposed (`os.popen` → `subprocess.run` with an
  argv list) and its explanation of why that closes the vulnerability

Click **Approve**. This is the moment worth pausing on — everything before
was analysis, this click is what actually authorizes a change.

### Beat 4 — Show the real result (30s)
Refresh the GitHub repo's PR list — a brand new PR exists, already merged,
with the exact fix just reviewed. Open `diagnostics/network.py` on `main`
again to show it's genuinely changed.

## After the demo

Reset again if you'll run this more than once:
```bash
python3 reset_demo.py
```

## If you want to show the Reject path too

Trigger a second run, and when it reaches Work Center, click **Reject**
instead. Show that the job ends cleanly and `main` is untouched — the gate
holds in both directions, not just the happy path.

## Recreating this from scratch (if you need to rebuild it on a different platform/account)

1. Pull `qwen3-coder:latest` and a **BF16-converted** (not the raw community
   GGUF) `antares-1b` into Ollama — see this folder's `README.md` for why the
   conversion step matters (F16/quantized builds collapse into repeated-token
   garbage on this architecture).
2. Create Ollama provider profiles for both in FlowAI, `Fetch Models`, and add
   your builder group to each profile's access control (UI-only step, no API
   path exists for this).
3. The 5 IAG tools already live in this repo under `tools/` — register each
   with `iagctl create decorator` + `iagctl create service python-script`,
   then `POST /tools/discover` (do this after *every* decorator/service
   change, or the tool comes back `active: false` and any agent using it
   silently fails to authorize).
4. Recreate the two agents (`CWE Finder`, `CWE Fixer`) and the workflow — the
   full JSON and the API call sequence are captured in this session's history;
   ask me to walk through it again if rebuilding elsewhere.
