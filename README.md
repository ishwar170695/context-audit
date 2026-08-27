# context-audit

> **85–99% of your coding agent bill is invisible input tokens. Inspect your context economics in 5 seconds.**

---

## 📈 The Problem

Almost every engineer building or using agentic coding tools (like Claude Code, Cursor, Aider, or custom IDE agents) complains about runaway context growth and mounting API bills. 

When sessions get long, you aren't paying for your prompts—you’re paying for the compounding weight of raw terminal logs, repeated file reads, and tool history re-sent on every single turn.

We built `context-audit` as a **zero-config, 100% local CLI** that parses your local session transcripts, measures context reuse, models dynamic prefix caching, and identifies true redundant waste.

---

## ⚡ Quick Start (Zero Config)

```bash
# Auto-detects local Claude Code, Cursor, and IDE agent session logs
pip install context-audit && context-audit
```

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

## 📊 Terminal Run Output

Running `context-audit` instantly outputs a clean summary card and timeline report:

```text
+--------------------------- context-audit summary ---------------------------+
|   Target: 27 Sessions (Auto-Discovered)                                     |
|                                                                             |
|   93%  repeated context (paid for twice+)                                   |
|   12%  fixed overhead (tools/system prompt before you typed)                |
|   89%  effective cache hit rate (target benchmark: ~86%)                    |
|                                                                             |
|   Estimated wasted spend: ~$267.12                                          |
|                                                                             |
+-----------------------------------------------------------------------------+
[*] My context-audit: 93% repeated context | 89% cache hit rate | ~$267.12 wasted. Run yours: pip install context-audit && context-audit
```

---

## 🚀 CLI Usage

```bash
# 1. Zero-config auto-discovery across ~/.claude, ~/.cursor, and local workspace:
context-audit

# 2. Audit a specific session transcript:
context-audit run path/to/transcript.jsonl

# 3. Benchmark a directory recursively:
context-audit benchmark path/to/logs_directory
```

---

## 🔒 Privacy & Offline Guarantee

* **100% Local**: No network requests, no telemetry, no tracking, no data leaves your machine.
* **Open Source**: MIT Licensed.
