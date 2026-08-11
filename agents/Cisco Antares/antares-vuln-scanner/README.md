# Antares-1B Vulnerability Scanner

Runs Cisco's Antares-1B model against a small bundled sample codebase to find a
described CWE-class vulnerability, using the terminal-style tool loop the model
was actually trained on (`grep`/`find`/`cat`-equivalents, ending in a `submit_*`
call) instead of generic API tool-calling.

## Setup

### 1. Get Antares-1B running correctly locally first

**Do not skip this.** The community GGUF conversions of this model (F16
intermediate) collapse into repeating a single token forever
(`@@@@@@@@@@...`) because Granite 4.0's hybrid Mamba/attention architecture
saturates in F16. You need your own BF16 conversion. Full steps: convert
`fdtn-ai/antares-1b` from Hugging Face at `--outtype bf16` with `llama.cpp`,
verify with `llama-cli --jinja` before touching Ollama, then `ollama create`
with an explicit Modelfile (Ollama does not pick up this GGUF's chat template
automatically). Confirmed working settings: **unquantized BF16** (`q8_0`
quantization alone was enough to reproduce the same repeating-token collapse
on this architecture — stay at full precision), temperature 0.3, top-p 1.0,
`num_ctx` 32768.

Verify before moving on:
```bash
ollama run antares-1b "Say OK"
# expect a short coherent reply, not repeated garbage characters
```

### 2. Test the 5 tools directly (no Itential needed)

```bash
cd tools
python3 find_files.py --pattern='*.py'
python3 grep_repo.py --pattern='os\.(system|popen)'
python3 read_file.py --path='diagnostics/network.py'
```

### 3. Register on FlowAI

See `itential/agent.spec.md` Section 0 for the exact deployment recipe —
`iagctl create repository` pointed at this GitHub repo, then one
`iagctl create service python-script` per tool (5 total), then create the
agent via `agent-project-service`.

## What's in here

- `tools/` — the 5 IAG service scripts (`grep_repo`, `find_files`,
  `read_file`, `submit_vulnerable_files`, `submit_no_vulnerability_found`),
  plus `_repo_utils.py` (shared path-confinement + arg-parsing helper)
- `sample-repo/` — a tiny network-diagnostics CLI with one planted CWE-78
  (OS command injection) and several safe decoy files
- `itential/agent.spec.md` — the FlowAI agent definition and deployment recipe
- `skills/antares-vuln-scan/SKILL.md` — the same procedure, generalized for
  any MCP-capable coding agent (Claude Code, Codex, etc.), no Itential needed
- `tests/missions/` — example verification runs
