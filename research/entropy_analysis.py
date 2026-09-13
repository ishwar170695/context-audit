#!/usr/bin/env python3
"""
entropy_analysis.py

Runs across all session files in a directory, extracts tool-output turns
vs user/model turns, computes Shannon entropy per turn, then runs a
Mann-Whitney U test to answer:

  Are tool-output turns statistically distinguishable from other turns by entropy?

Outputs:
  entropy_results.jsonl  — one record per turn
  entropy_summary.json   — the number (U stat, p-value, effect size, verdict)

Usage:
  python entropy_analysis.py --sessions-dir /path/to/sessions
  python entropy_analysis.py --sessions-dir . --out-dir ./results
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator

try:
    from scipy.stats import mannwhitneyu
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Tokenizer (whitespace, same as context-audit's token estimator)
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Whitespace split — consistent with context-audit's token counting."""
    return text.split()


def shannon_entropy(tokens: list[str]) -> float:
    """Shannon entropy in bits over token distribution."""
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = len(tokens)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


# ---------------------------------------------------------------------------
# Session loaders — handles both formats directly, no context-audit import
# dependency so this runs standalone even if the package isn't installed
# ---------------------------------------------------------------------------

def _turns_from_jsonl(path: Path) -> Iterator[dict]:
    """
    Parse transcript.jsonl format.
    Returns normalised dicts: {role, content, tool_name, session, path}
    """
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue

            src = step.get("source", "")
            stype = step.get("type", "")
            content = step.get("content", "") or ""

            # Tool output: source=MODEL, type != PLANNER_RESPONSE, has content
            if src == "MODEL" and stype not in ("PLANNER_RESPONSE", "CONVERSATION_HISTORY") and content:
                yield {
                    "role": "tool",
                    "tool_name": stype.lower(),
                    "content": content,
                    "step_index": step.get("step_index"),
                    "session": path.stem,
                    "path": str(path),
                }
            elif src == "USER_EXPLICIT":
                yield {
                    "role": "user",
                    "tool_name": None,
                    "content": content,
                    "step_index": step.get("step_index"),
                    "session": path.stem,
                    "path": str(path),
                }
            elif src == "MODEL" and stype == "PLANNER_RESPONSE":
                thinking = step.get("thinking", "") or ""
                if thinking:
                    yield {
                        "role": "model",
                        "tool_name": None,
                        "content": thinking,
                        "step_index": step.get("step_index"),
                        "session": path.stem,
                        "path": str(path),
                    }


def _turns_from_session_json(path: Path) -> Iterator[dict]:
    """
    Parse session.json format.
    Returns normalised dicts.
    """
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return

    history = data.get("history", [])
    for i, turn in enumerate(history):
        role = turn.get("role", "")
        content = turn.get("content", "") or ""
        tool_name = turn.get("name") if role == "tool" else None

        if not content:
            continue

        yield {
            "role": role,
            "tool_name": tool_name,
            "content": content,
            "step_index": i,
            "session": path.stem,
            "path": str(path),
        }


def iter_sessions(sessions_dir: Path) -> Iterator[dict]:
    """Walk directory, yield normalised turns from all session files."""
    for root, _, files in os.walk(sessions_dir):
        for fname in files:
            fpath = Path(root) / fname
            if fname.endswith(".jsonl"):
                yield from _turns_from_jsonl(fpath)
            elif fname.endswith(".json") and "session" in fname.lower():
                yield from _turns_from_session_json(fpath)


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def compute_records(sessions_dir: Path) -> list[dict]:
    records = []
    for turn in iter_sessions(sessions_dir):
        tokens = tokenize(turn["content"])
        if not tokens:
            continue
        ent = shannon_entropy(tokens)
        records.append({
            "session": turn["session"],
            "path": turn["path"],
            "step_index": turn["step_index"],
            "role": turn["role"],
            "tool_name": turn["tool_name"],
            "token_count": len(tokens),
            "entropy": round(ent, 4),
        })
    return records


def effect_size_r(U: float, n1: int, n2: int) -> float:
    """Rank-biserial correlation r = 1 - 2U/(n1*n2). Range [-1, 1]."""
    return round(1 - (2 * U) / (n1 * n2), 4)


def run_test(records: list[dict]) -> dict:
    tool_entropy   = [r["entropy"] for r in records if r["role"] == "tool"]
    other_entropy  = [r["entropy"] for r in records if r["role"] != "tool"]

    n_tool  = len(tool_entropy)
    n_other = len(other_entropy)

    summary = {
        "n_tool_turns":  n_tool,
        "n_other_turns": n_other,
        "mean_tool_entropy":  round(sum(tool_entropy)  / n_tool  if n_tool  else 0, 4),
        "mean_other_entropy": round(sum(other_entropy) / n_other if n_other else 0, 4),
    }

    if not SCIPY_AVAILABLE:
        summary["error"] = "scipy not installed — pip install scipy"
        summary["verdict"] = "UNKNOWN"
        return summary

    if n_tool < 3 or n_other < 3:
        summary["error"] = f"Insufficient data: tool={n_tool}, other={n_other}"
        summary["verdict"] = "UNKNOWN"
        return summary

    stat, p = mannwhitneyu(tool_entropy, other_entropy, alternative="two-sided")
    r = effect_size_r(stat, n_tool, n_other)

    summary["mann_whitney_U"] = round(stat, 2)
    summary["p_value"]        = round(p, 6)
    summary["effect_size_r"]  = r

    # Verdict
    if p < 0.05 and abs(r) >= 0.1:
        summary["verdict"] = "YES — tool turns are statistically distinguishable"
    elif p < 0.05:
        summary["verdict"] = "WEAK — significant but negligible effect size"
    else:
        summary["verdict"] = "NO — distributions are not distinguishable"

    return summary


def write_results(records: list[dict], summary: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / "entropy_results.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    summary_path = out_dir / "entropy_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return jsonl_path, summary_path


def print_summary(summary: dict):
    print("\n" + "="*60)
    print("ENTROPY ANALYSIS SUMMARY")
    print("="*60)
    print(f"  Tool turns    : {summary.get('n_tool_turns', 0)}")
    print(f"  Other turns   : {summary.get('n_other_turns', 0)}")
    print(f"  Mean entropy (tool)  : {summary.get('mean_tool_entropy', 'N/A')}")
    print(f"  Mean entropy (other) : {summary.get('mean_other_entropy', 'N/A')}")
    if "mann_whitney_U" in summary:
        print(f"  Mann-Whitney U: {summary['mann_whitney_U']}")
        print(f"  p-value       : {summary['p_value']}")
        print(f"  Effect size r : {summary['effect_size_r']}")
    if "error" in summary:
        print(f"  Error         : {summary['error']}")
    print(f"\n  VERDICT: {summary.get('verdict', 'UNKNOWN')}")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Entropy analysis: tool vs non-tool turns")
    parser.add_argument("--sessions-dir", required=True, help="Directory containing session files")
    parser.add_argument("--out-dir", default="./entropy_output", help="Output directory for results")
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir)
    if not sessions_dir.exists():
        print(f"ERROR: sessions-dir does not exist: {sessions_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {sessions_dir}")
    records = compute_records(sessions_dir)

    if not records:
        print("ERROR: No turns found. Check that the directory contains .jsonl or session*.json files.")
        sys.exit(1)

    print(f"Found {len(records)} turns across sessions.")
    summary = run_test(records)

    out_dir = Path(args.out_dir)
    jsonl_path, summary_path = write_results(records, summary, out_dir)

    print_summary(summary)
    print(f"Results written to:")
    print(f"  {jsonl_path}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()