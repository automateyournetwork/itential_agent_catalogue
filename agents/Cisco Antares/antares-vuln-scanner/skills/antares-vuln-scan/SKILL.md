# Skill: Antares-style vulnerability localization

Generalized version of `../../itential/agent.spec.md`'s system prompt — usable by
any MCP-capable coding agent (Claude Code, Codex, etc.), no Itential involved.

## When to use this

You've been given a CWE description and a codebase (here, the bundled
`../../sample-repo/`), and asked to find which file(s), if any, contain that
vulnerability class.

## Procedure

1. **Orient first.** List files by pattern (`find_files` / equivalent) before
   reading anything — don't grep blind across a codebase you haven't looked at.
2. **Search for the vulnerability's real signature, not its topic.** For
   OS command injection (CWE-78), search for shell-execution calls
   (`os.system`, `os.popen`, `subprocess` with `shell=True`), not just files that
   mention the feature area (e.g. "network" or "ping"). A file can be topically
   relevant and still be safe.
3. **Confirm data flow before concluding.** A shell-execution call is only a
   vulnerability if untrusted input reaches it unsanitized. Read the actual
   function, don't just trust that a grep hit near a suspicious call name means
   the pattern applies.
4. **Rule out decoys explicitly, don't just ignore them.** A validation helper
   that exists in the repo but isn't actually called from the vulnerable path is
   a common real-world near-miss — worth a sentence in your reasoning
   ("`utils/validation.py` exists but is never called from `network.py`'s
   `ping_host`, so it provides no protection here"), not silent omission.
5. **Bounded effort.** Cisco's own model card scopes this to ~15 tool calls
   before requiring a submission. Don't re-read the same file or re-run a
   near-identical grep — that's wasted budget, not thoroughness.
6. **Terminate explicitly.** Every run ends with exactly one of: naming the
   specific vulnerable file(s) with reasoning grounded in the actual code you
   read, or stating plainly that the described vulnerability class isn't present
   after a real search — never silence, and never a vague "this might be an
   issue" without pointing at a specific file and line.

## Honesty / edge cases

- If your search tool returns an error (bad pattern, path escape, etc.), say so
  and adjust — don't silently treat an error as "no matches."
- If you genuinely can't determine confidently within budget, say that
  explicitly rather than guessing a file to "have an answer."
- Don't flag a file because it's topically adjacent (e.g. flagging
  `diagnostics/logger.py` because it's in the same package as the real
  vulnerability) — the reasoning must trace the actual unsafe data flow.
