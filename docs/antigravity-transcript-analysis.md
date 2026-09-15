# How to Analyze Antigravity IDE Session Transcripts & Token Economics

**Google Antigravity IDE** is an advanced agentic coding environment that orchestrates complex coding tasks through planning, multi-file inspection, terminal execution, and subagent coordination.

As tasks run, Antigravity records rich JSONL transcripts of conversation history, planner reasoning, and tool execution.

`context-audit` has first-class, zero-config support for discovering and analyzing **Antigravity IDE** session transcripts.

---

## 1. Where Does Antigravity Store Transcripts?

Antigravity logs session transcripts, artifacts, and execution trajectories locally inside your user profile:

* **Linux & macOS**: `~/.gemini/antigravity-ide/brain/<conversation-id>/`
* **Windows**: `%USERPROFILE%\.gemini\antigravity-ide\brain\<conversation-id>\`

Key files inside each session directory include:
* `.system_generated/logs/transcript.jsonl`: The token-efficient conversation transcript.
* `.system_generated/logs/transcript_full.jsonl`: The complete, untruncated transcript.
* `implementation_plan.md` & `walkthrough.md`: Planning and review artifacts.

---

## 2. Antigravity Schema & Context Breakdown

In Antigravity IDE, agent interactions are logged with rich step types:
* `USER_INPUT` / `USER_EXPLICIT`: User requirements and feedback.
* `PLANNER_RESPONSE`: Model thinking, reasoning chains, and emitted tool calls.
* Tool execution steps: `LIST_DIRECTORY`, `VIEW_FILE`, `RUN_COMMAND`, `REPLACE_FILE_CONTENT`, `WRITE_TO_FILE`.

Because agentic workflows frequently read large files, execute build commands, and iterate on multi-step plans, **context reuse typically exceeds 90%** over long sessions.

`context-audit` automatically parses these step types, models dynamic prefix caching discounts, and separates fixed overhead (system skills and tool declarations) from iterative conversational memory.

---

## 3. How to Audit Antigravity Sessions with `context-audit`

### Installation

```bash
pip install context-audit
```

### Auto-Discovery

`context-audit` automatically detects your Antigravity installation and selects the latest session:

```bash
context-audit
```

To run diagnostics and verify that your Antigravity logs are detected:

```bash
context-audit doctor
```

Example Doctor Output:
```text
Agent Discovery Diagnostics:
  • Antigravity: Detected at ~/.gemini/antigravity-ide/brain (Supported)
  • Claude Code: Detected at ~/.claude/projects (Supported)
```

### Audit a Specific Antigravity Conversation

You can point `context-audit` directly at any Antigravity conversation transcript:

```bash
# Linux / macOS
context-audit run ~/.gemini/antigravity-ide/brain/<conversation-id>/.system_generated/logs/transcript.jsonl

# Windows PowerShell
context-audit run $HOME\.gemini\antigravity-ide\brain\<conversation-id>\.system_generated\logs\transcript.jsonl
```

### Identify Repeated File Reads & Largest Payloads

Agentic loops sometimes re-read the same source files across multiple planning steps. To inspect top context consumers and redundant reads:

```bash
context-audit --wasters
```

### Cross-Session Benchmark Across All Antigravity Sessions

To aggregate all Antigravity and Claude Code sessions discovered on your machine into a single macroscopic benchmark:

```bash
context-audit benchmark
```

---

## 4. Summary: Antigravity + context-audit

* **Privacy**: 100% local analysis. Transcripts are never uploaded or transmitted over the network.
* **Economics**: Accurately measures dynamic prefix caching savings versus un-cached standard API rates.
* **Diagnostics**: Identifies when large terminal outputs or file views cause context pressure and attention degradation.
