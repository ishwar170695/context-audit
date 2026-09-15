# Comparing Claude Code Token Tools: ccusage vs context-audit

As developers spend more time working in **Claude Code**, understanding token consumption, rate limits, and spend has become essential.

Two open-source local CLI tools have emerged in this space: **`ccusage`** and **`context-audit`**.

While both tools analyze Claude Code session data without sending code to third-party servers, they address completely different developer questions and operate at different layers of the workflow.

---

## At a Glance: Key Differences

| Feature / Dimension | `ccusage` | `context-audit` |
| :--- | :--- | :--- |
| **Primary Question** | *"How many tokens did I use and am I close to rate limits?"* | *"What happened to my context and why did it cost so much?"* |
| **Target Data** | API token counts & rate limit metrics | Full conversation transcripts (`~/.claude/projects/...`) |
| **Primary Workflow** | Terminal statusline & background daemon | Post-session forensics & multi-session benchmarks |
| **Key Output** | Daily, weekly, monthly spend & 5-hour window tracker | Context reuse ratio, prompt cache efficiency, redundant files |
| **Installation** | `npx ccusage` or `uv tool install ccusage` | `pip install context-audit` |
| **Execution Model** | Statusline hook / polling daemon | On-demand single command or multi-session aggregation |

---

## Deep Dive: `ccusage`

**What it is:** A real-time rate limit and token monitor developed by `@ryoppippi`.

### Strengths
1. **Statusline Integration**: Seamlessly integrates into your Claude Code status bar (`~/.claude/settings.json`) to show current token burn and rate limits as you work.
2. **5-Hour Rate Limit Tracking**: Crucial for Claude Pro and Max subscribers who need to pace their work and avoid hitting Anthropic's rolling usage ceilings.
3. **Temporal Aggregation**: Breaks down usage by hour, day, week, and month.

### Best Used For
* Monitoring live token consumption while typing prompts.
* Preventing unexpected rate limit lockouts during intense coding sessions.
* Tracking daily and weekly Anthropic API / subscription budget burn.

---

## Deep Dive: `context-audit`

**What it is:** An open-source forensic transcript analyzer that inspects the internal mechanics of agent context.

### Strengths
1. **Context Reuse Ratio**: Quantifies what percentage of cumulative session tokens were identical repetitions of earlier turns (typically 85–95%).
2. **Prompt Cache Modeling**: Calculates how much you saved (or could have saved) through dynamic prefix caching discounts (up to 90%).
3. **Redundant Workspace State Detection (`--wasters`)**: Pinpoints identical files that were re-read multiple times across turns without changes, and long compiler error outputs lingering across 40 turns.
4. **Cross-Session Benchmarks (`context-audit benchmark`)**: Aggregates dozens of historical sessions to show macroscopic trends in context pressure and cumulative tokens.

### Best Used For
* Investigating why a specific Claude Code session was unexpectedly expensive.
* Measuring prompt caching effectiveness across multi-turn agent runs.
* Auditing whether agent tool loops are re-reading duplicate files unnecessarily.

---

## How to Use Both Tools Together

Because `ccusage` and `context-audit` do not overlap in functionality, many developers use them as a companion pair:

1. **In Real-Time**: Use `ccusage` in your Claude Code statusline to keep an eye on rate limits and current session token burn.
2. **After the Session**: Run `context-audit` in your terminal to see the context breakdown, cache efficiency, and identify any wasteful context loops.

```bash
# 1. Live statusline monitor (ccusage)
npx ccusage statusline

# 2. Post-session context forensic audit (context-audit)
context-audit
```
