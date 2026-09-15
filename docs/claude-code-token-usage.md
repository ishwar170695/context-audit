# How to Analyze Claude Code Token Usage & Session Transcripts

When using Anthropic's **Claude Code** CLI, token consumption does not grow linearly with each command you type. Instead, it compounds quadratically over long sessions because the entire conversational history, read file contents, and terminal outputs are re-transmitted on every single turn.

This guide explains:
1. Where Claude Code stores local session transcripts.
2. Why input tokens account for 85–99% of your total token spend.
3. How Anthropic prompt caching alters the cost economics.
4. How to inspect and analyze session transcripts using `context-audit`.

---

## 1. Where Does Claude Code Store Session Transcripts?

Claude Code operates locally and writes detailed JSON/JSONL logs of every interaction, tool execution, and file inspection to your home directory:

* **Linux & macOS**: `~/.claude/projects/`
* **Windows**: `%USERPROFILE%\.claude\projects\`

Inside these project directories, you will find session transcripts containing:
* System instructions and tool schemas (e.g., `Bash`, `FileEdit`, `GlobTool`).
* Raw terminal command outputs.
* Entire file contents read by the agent.
* Model thoughts, turn completions, and token counts.

---

## 2. Why Does Token Usage Compound? (The Context Multiplier)

A common point of confusion for developers is why a 20-turn session consumes millions of tokens when the user prompt was only a few sentences.

In an agent loop:
* **Turn 1**: System Prompt (1.5k) + User Prompt (100) = **1.6k input tokens**
* **Turn 2**: System Prompt + Turn 1 (1.6k) + Agent Read File `app.py` (3k) + User Prompt (50) = **4.6k input tokens**
* **Turn 15**: System Prompt + Previous 14 turns + 8 read files + 5 terminal command outputs = **60k+ input tokens**

By Turn 20, you may have accumulated **1.5M+ cumulative input tokens**, even though the active context window at Turn 20 is only 65k tokens.

---

## 3. The Impact of Prompt Caching

Anthropic implements **prompt caching** (automatic 5-minute prefix caching):
* **Base Input Tokens**: ~$3.00 / million tokens (Claude 3.5 Sonnet / 3.7 Sonnet).
* **Cached Input Tokens (90% discount)**: ~$0.30 / million tokens.
* **Cache Write (25% surcharge)**: ~$3.75 / million tokens.

If your multi-turn conversation maintains an intact prefix, consecutive turns receive up to a 90% discount on the reused prefix. However:
1. **Cache misses**: Breaking the prefix (e.g., dynamic tools or timestamp alterations) invalidates downstream cache.
2. **Residual waste**: Even with a 90% discount, paying 10% on 20 identical copies of a 10,000-token file across 20 turns still wastes meaningful spend and clogs the attention window.

---

## 4. How to Audit Claude Code Transcripts with `context-audit`

`context-audit` is an open-source local CLI designed specifically to parse these transcripts and give you a forensic breakdown in seconds.

### Installation

```bash
pip install context-audit
```

### Auto-Discovery: Audit Your Most Recent Claude Code Session

To automatically discover and audit your latest session transcript:

```bash
context-audit
```

Output:
```text
context-audit summary ─────────────────────────────────────────────────────────

  Target: ~/.claude/projects/my-app/session_2026-09-14.jsonl
  Cumulative Session Tokens: 2.8M tokens

  94%  repeated context (Context Reuse Ratio) -> Paid for 2x+ (identical file reads & tool history)
  12%  fixed overhead -> Tool schemas & system instructions before prompt
  89%  effective cache rate -> Eligible for 90% prefix cache discount

  Estimated wasted spend: ~$7.28

───────────────────────────────────────────────────────────────────────────────
```

### Audit a Specific Transcript File

If you want to inspect a specific historical transcript:

```bash
context-audit run ~/.claude/projects/my-app/session_xyz.jsonl
```

### Identify Duplicate File Reads & Largest Context Wasters

To see which files or tool outputs were repeatedly injected across turns:

```bash
context-audit --wasters
```

### Benchmark All Historical Claude Code Sessions

To aggregate and analyze all discovered sessions across your local machine:

```bash
context-audit benchmark
```

---

## 5. Summary: When to Use What

* **During active coding**: Check Claude Code's built-in `/cost` or use `ccusage` for real-time statusline rate-limit monitoring.
* **After a session or when investigating bills**: Run `context-audit` to inspect where the context went, measure prefix cache efficiency, and identify redundant file read loops.
