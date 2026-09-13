# context-audit

> **85–99% of your coding agent bill is invisible input tokens. Inspect your context economics in 5 seconds.**

```text
context-audit summary ─────────────────────────────────────────────────────────

  Target: session_2026-06-19.jsonl
  Cumulative Session Tokens: 2.8M tokens

  94%  repeated context (Context Reuse Ratio) -> Paid for 2x+ (identical file reads & tool history)
  12%  fixed overhead -> Tool schemas & system instructions before prompt
  89%  effective cache rate -> Eligible for 90% prefix cache discount

  Estimated wasted spend: ~$7.28

───────────────────────────────────────────────────────────────────────────────
Tip: Run with --wasters for duplicate files, --composition for visual map, or --show-math for audit formulas.
```

---

## 💡 What Problem Does This Solve?

When you use AI coding agents (Claude Code, Cursor, Antigravity, or custom agent loops), you aren't paying for what you type. You are paying for the compounding weight of **raw terminal command outputs, repeated file reads, and tool declarations re-sent on every single turn**.

In long sessions, 85% to 99% of the tokens billed by API providers are identical repetitions of earlier turns.

`context-audit` is a **zero-config, 100% local CLI** that parses your local agent transcripts, calculates context reuse, models dynamic prefix caching savings, and pinpoints preventable waste.

---

## ⚡ Quick Start

```bash
# Install CLI
pip install context-audit

# 1. Zero-config auto-discovery of local session logs:
context-audit

# 2. Check agent discovery diagnostics & candidate paths:
context-audit doctor

# 3. Explore with a sample session (if you don't have local logs yet):
context-audit demo
```

---

## 📖 Plain-English Glossary

* **Prefix Caching**: Modern LLM providers (Anthropic, OpenAI) discount tokens by up to 90% when consecutive turns share an identical message prefix. `context-audit` models this dynamic prefix breakpoint economics.
* **Context Reuse Ratio**: The percentage of cumulative session tokens that were identical re-transmissions of content already seen in earlier turns.
* **Fixed Overhead**: The baseline token cost of system instructions and tool definitions that occupy context before your first user prompt.
* **Context Pressure**: The percentage of the model's context window limit (e.g. 100k or 200k tokens) consumed by the session, identifying when older instructions risk attention degradation.
* **Skeptic's Audit (`--show-math`)**: A step-by-step arithmetic verification table breaking down exact formulas, counts, and price calculations.

---

## 🧭 Agent Support Matrix

| Agent | Detect | Locate | Parse | End-to-End Zero-Config | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Antigravity** | ✓ | ✓ | ✓ | **✓ Supported** | Discovers `~/.gemini/antigravity-ide/brain` transcripts |
| **Claude Code** | ✓ | ✓ | ✓ | **✓ Supported** | Discovers `~/.claude` transcripts and session logs |
| **Codex** | ✓ | ✓ | ✓ | **Experimental** | Scans `~/.codex` / `~/.openai` JSON/JSONL logs |
| **Cursor** | ✓ | ✗ | ? | **✗ Unsupported format** | Cursor stores chat history in SQLite (`state.vscdb`) |
| **Aider** | ✓ | ✗ | ✗ | **✗ Unsupported format** | Aider stores history as Markdown (`.aider.chat.history.md`) |
| **Local Workspace** | ✓ | ✓ | ✓ | **✓ Supported** | Scans current directory for `.jsonl` / `session.json` |

---

## 🚀 CLI Usage: 3 Core Workflows

`context-audit` has three distinct commands that fit your workflow:

```bash
# 1. "How did my last session go?" (Audits your most recent session automatically)
context-audit

# 2. "How am I doing overall?" (Aggregates all sessions discovered across your machine)
context-audit benchmark

# 3. "Audit this specific log file"
context-audit run path/to/transcript.jsonl
```

### Output Tiers & Scriptable Flags

Display and export flags work orthogonally across all commands:

```bash
# Conservative 10-second default (Summary Card alone):
context-audit

# Inspect top redundant files and largest context consumers:
context-audit --wasters

# Visual composition map (System vs Tools vs User vs Outputs vs Reasoning):
context-audit --composition

# Skeptic's Audit (transparent step-by-step arithmetic verification):
context-audit --show-math

# Full comprehensive report (timeline, anomaly alerts, belief drift):
context-audit --full

# Machine-readable JSON export (pipe-safe for CI/CD gates and scripts):
context-audit --json

# GitHub-flavored Markdown export (ready to pipe into PRs and issues):
context-audit --markdown
```

---

## 🔒 Verifiable Trust: 100% Local & Zero Telemetry

`context-audit` is designed for privacy-conscious developers and sensitive codebases:

* **Zero Network Requests**: The CLI never initiates an outbound network connection. It has no telemetry, no tracking, and sends no data anywhere.
* **Minimal Dependencies**: Inspect `pyproject.toml`—the package depends solely on:
  * `rich` (for terminal formatting)
  * `tiktoken` (for local, offline BPE token counting)
* **Local Parsing**: Transcripts are read directly from your local filesystem and analyzed strictly in-memory.

---

## 📊 Cross-Session Benchmark (27 Real Developer Sessions)

We benchmarked **27 real-world developer session transcripts** scanned across IDE agent logs:

```text
+-------------------------- context-audit benchmark --------------------------+
|   CROSS-SESSION BENCHMARK SUMMARY                                           |
|   Directory: 27 Real Developer Sessions                                     |
|                                                                             |
|   Sessions Analyzed: 27                                                     |
|                                                                             |
|   Cumulative Session Tokens:                                                |
|     Avg: 3.3M | Median: 314.2k | Max: 43.3M                                 |
|   Peak Context Size:                                                        |
|     Avg: 33.2k | Median: 20.1k | Max: 188.9k                                |
|   Final Context Size:                                                       |
|     Avg: 33.2k | Median: 20.1k                                              |
|   Context Reuse Ratio:                                                      |
|     Avg: 92.6% | Median: 94.2%                                              |
|   Average Novel Context Ratio: 7.4%                                         |
|                                                                             |
|   Financial Cost Aggregations (USD):                                        |
|     Total Standard Spend: $269.80                                           |
|     Avg Session Cost (No Cache): $9.99 | Median: $0.94                      |
|     Avg Session Cost (With Cache): $1.09 | Median: $0.15                    |
|     Total Potential Cache Savings: $240.40 (Avg: $8.90 / session, 89.1%)    |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### Context Size Scaling Breakdown

| Session Size Class (Final Turn) | Session Count | Avg Context Reuse % | Avg Cache Savings ($) | Avg Peak Context Size | Avg Cumulative Tokens |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **< 5k tokens** | 1 | 94.2% | $0.09 | 2.0k | 34.3k |
| **5k - 20k tokens** | 12 | 87.4% | $0.24 | 10.0k | 97.5k |
| **20k - 50k tokens** | 8 | 95.6% | $1.49 | 23.6k | 575.4k |
| **> 50k tokens** | 6 | 99.0% | $37.59 | 97.3k | 14.0M |

*(For the complete cross-session benchmark report, see [benchmark_summary.md](examples/benchmark_summary.md).)*

---

## 💡 Key Architectural Insights

### 1. The Prompt Caching Paradox
* **Dynamic Prefix Caching (Anthropic/OpenAI style)**: Caching the multi-turn conversational prefix across turns reduces input costs by **~89.1%** ($240 of $270 spend across our 27 sessions). If you're running custom agent loops without cache breakpoints configured, you are overpaying by ~9x.
* **Static Header Caching**: Caching only the static header (system prompt + tools) saves only **~1.0%**. In long sessions, the dynamic message history (>50k tokens) completely dwarfs the static header (~500 tokens).

### 2. The Residual Waste (What Caching Doesn't Fix)
Even with prompt caching enabled, **~35% of payload volume** was redundant workspace state:
* Identical files re-read multiple times within the same session without edits.
* Redundant tool declarations that are never invoked.
* Multi-kilobyte compiler error logs lingering across 40 subsequent turns.

This dead payload pushes context windows toward the 100k/200k token limits, increases per-turn latency, and degrades model attention.

### 3. Coding Agents Have Two Memory Systems
* **Workspace Memory (Disk-Backed)**: Terminal command outputs, read file payloads, directory listings, and compiler logs.  
  * *Verdict*: **Safe for compaction**. Once code changes are written to the workspace, the filesystem is the source of truth.
* **Conversational Memory (Not Disk-Backed)**: User preferences, constraints, stylistic choices, and rejected options.  
  * *Verdict*: **Must persist**. Pruning them naively causes behavioral regressions (e.g. the agent re-suggesting previously rejected architectures). (See [regression_case.md](examples/regression_case.md) for a case study).

---

## 🔬 Research & Empirical Reproducibility

The standalone statistical tools and scripts used in our research (including the $p < 0.0001$ Mann-Whitney U test on tool output entropy) are maintained in the [`research/`](research/) directory. See [`research/README.md`](research/README.md) for reproduction commands.

---

## 📄 License

MIT License. See [LICENSE](LICENSE).
