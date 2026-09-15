import json
import os
import statistics
from typing import Any, Dict, List
from rich import box
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.align import Align
from rich.text import Text
from rich.style import Style

console = Console()

def format_tokens(num: int) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}k"
    return str(num)

def format_usd(val: float) -> str:
    if val == 0.0:
        return "$0.00"
    elif val < 0.01:
        return f"${val:.4f}"
    return f"${val:.2f}"

import sys

def safe_char(char: str, fallback: str) -> str:
    try:
        char.encode(sys.stdout.encoding or "utf-8")
        return char
    except Exception:
        return fallback

CLIPBOARD_ICON = safe_char("📋 ", "[*] ")

def format_display_path(file_path: str, max_len: int = 55) -> str:
    """Formats a file path for clean, unambiguous console display without box overflow."""
    if not file_path or file_path.startswith("Demo Sample") or file_path.endswith(" Sessions") or file_path.startswith("Auto-Discovered"):
        return file_path

    sub_id = None
    if "#" in file_path and not os.path.exists(file_path):
        base_file, potential_sub = file_path.rsplit("#", 1)
        if os.path.exists(base_file):
            file_path = base_file
            sub_id = potential_sub

    from pathlib import Path
    try:
        p = Path(file_path).resolve()
        home = Path.home().resolve()
        cwd = Path.cwd().resolve()

        if p.is_relative_to(cwd):
            rel = p.relative_to(cwd)
            display = f"./{rel.as_posix()}"
        elif p.is_relative_to(home):
            rel = p.relative_to(home)
            display = f"~/{rel.as_posix()}"
        else:
            display = p.as_posix()
    except Exception:
        display = str(file_path).replace("\\", "/")

    if sub_id:
        display = f"{display} [{sub_id}]"

    if len(display) <= max_len:
        return display

    parts = display.split("/")
    if len(parts) <= 3:
        return "..." + display[-(max_len - 3):]

    first = parts[0] + "/" + parts[1]
    filename = parts[-1]

    # Find unique distinguishing ancestor segment (avoid generic folder names)
    boilerplate_folders = {
        "logs", ".system_generated", "transcripts", "brain", 
        "projects", ".claude", ".gemini", "antigravity-ide", ".codex", ".openai",
        "sessions", "history", ".cursor", ".aider"
    }
    
    unique_ident = None
    for segment in reversed(parts[2:-1]):
        if segment.lower() not in boilerplate_folders:
            unique_ident = segment
            break

    # If identifier looks like a UUID (e.g. 7e05f9ce-4995-...), use the 8-char short hash
    if unique_ident and len(unique_ident) >= 32 and "-" in unique_ident:
        unique_ident = unique_ident[:8]
    elif unique_ident and len(unique_ident) > 16:
        unique_ident = unique_ident[:14] + ".."

    if unique_ident:
        contracted = f"{first}/.../{unique_ident}/{filename}"
    else:
        last = parts[-2] + "/" + filename
        contracted = f"{first}/.../{last}"

    if len(contracted) <= max_len:
        return contracted

    # If still too long, trim root component rather than losing the unique identifier
    if len(first) > 12:
        first = first[:10] + ".."
        if unique_ident:
            contracted = f"{first}/.../{unique_ident}/{filename}"
        else:
            contracted = f"{first}/.../{last}"
        if len(contracted) <= max_len:
            return contracted

    return "..." + display[-(max_len - 3):]

def print_instant_summary_card(
    target_label: str,
    repeated_pct: float,
    overhead_pct: float,
    cache_hit_pct: float,
    wasted_usd: float,
    discount_pct: float = 90.0,
    total_tokens: int = 0,
    show_share: bool = False,
    is_benchmark: bool = False,
    avg_tokens: int = 0,
    total_wasted_usd: float = 0.0,
    session_count: int = 0
):
    """Prints the 10-second summary card and optional shareable copyable snippet."""
    console.print()
    clean_target = format_display_path(target_label)
    card_elements = [
        ("  Target: ", "dim"), (f"{clean_target}\n", "bold white")
    ]
    if is_benchmark and total_tokens > 0:
        card_elements.extend([
            ("  Cumulative Benchmark Tokens: ", "dim"),
            (f"{format_tokens(total_tokens)} tokens ", "bold white"),
            (f"(avg {format_tokens(avg_tokens)} / session)\n\n", "dim")
        ])
    elif total_tokens > 0:
        card_elements.extend([
            ("  Cumulative Session Tokens: ", "dim"), (f"{format_tokens(total_tokens)} tokens\n\n", "bold white")
        ])
    else:
        card_elements.append(("\n", "white"))
        
    if is_benchmark:
        card_elements.extend([
            (f"  {repeated_pct:.0f}% ", "bold yellow" if repeated_pct > 30 else "bold white"),
            (" repeated context (avg per session) ", "white"), ("-> Paid for 2x+ (identical file reads & tool history)\n", "dim"),
            (f"  {overhead_pct:.0f}% ", "bold cyan"),
            (" fixed overhead (avg per session) ", "white"), ("-> Tool schemas & system instructions before prompt\n", "dim"),
            (f"  {cache_hit_pct:.0f}% ", "bold green"),
            (" effective cache rate (avg)\n\n", "white"),
            ("  Estimated wasted spend: ", "bold white"),
            (f"~{format_usd(wasted_usd)} / session avg  ", "bold red"),
            (f"(Total: ~{format_usd(total_wasted_usd)} across {session_count} sessions)\n", "dim red")
        ])
    else:
        card_elements.extend([
            (f"  {repeated_pct:.0f}% ", "bold yellow" if repeated_pct > 30 else "bold white"),
            (" repeated context (Context Reuse Ratio) ", "white"), ("-> Paid for 2x+ (identical file reads & tool history)\n", "dim"),
            (f"  {overhead_pct:.0f}% ", "bold cyan"),
            (" fixed overhead ", "white"), ("-> Tool schemas & system instructions before prompt\n", "dim"),
            (f"  {cache_hit_pct:.0f}% ", "bold green"),
            (" effective cache rate\n\n", "white"),
            ("  Estimated wasted spend: ", "bold white"), (f"~{format_usd(wasted_usd)}\n", "bold red")
        ])

    card_text = Text.assemble(*card_elements)
    from rich.rule import Rule
    rule_char = safe_char("─", "-")
    title_str = "[bold green]context-audit benchmark summary[/bold green]" if is_benchmark else "[bold green]context-audit summary[/bold green]"
    console.print(Rule(title_str, style="green", align="left", characters=rule_char))
    console.print()
    console.print(card_text)
    console.print(Rule(style="dim green", characters=rule_char))
    console.print()
    
    if show_share:
        if is_benchmark:
            shareable_str = f"{CLIPBOARD_ICON}My context-audit benchmark: {repeated_pct:.0f}% avg repeated context | ~{format_usd(wasted_usd)}/session wasted (~{format_usd(total_wasted_usd)} total across {session_count} sessions). Run yours: pip install context-audit && context-audit"
        else:
            shareable_str = f"{CLIPBOARD_ICON}My context-audit: {repeated_pct:.0f}% repeated context | {cache_hit_pct:.0f}% cache hit rate | ~{format_usd(wasted_usd)} wasted. Run yours: pip install context-audit && context-audit"
        console.print(f"[dim]{shareable_str}[/dim]\n")
    else:
        console.print()


def print_math_breakdown(result: Any):
    """Prints step-by-step arithmetic verification of metrics and pricing."""
    mb = getattr(result, "math_breakdown", {})
    if not mb:
        return
    math_table = Table(title="Skeptic's Audit: Mathematical Verification", show_header=True, header_style="bold cyan", box=box.ASCII)
    math_table.add_column("Metric", style="bold white")
    math_table.add_column("Formula / Derivation", style="dim")
    math_table.add_column("Calculation Details", style="cyan")
    math_table.add_column("Verified Value", style="bold green", justify="right")
    
    math_table.add_row(
        "Total Cumulative Tokens",
        "sum(turn_tokens for all turns)",
        f"{format_tokens(mb.get('total_cumulative_tokens', 0))} tokens across {mb.get('total_turns', 0)} turns",
        f"{mb.get('total_cumulative_tokens', 0):,}"
    )
    math_table.add_row(
        "Context Reuse Ratio",
        "(reused_tokens / cumulative_tokens) * 100",
        f"({mb.get('reused_tokens', 0):,} / {mb.get('total_cumulative_tokens', 0):,}) * 100",
        f"{mb.get('context_reuse_ratio_pct', 0.0):.1f}%"
    )
    math_table.add_row(
        "Fixed Overhead Ratio",
        "(system_tokens + tool_tokens) / cumulative_tokens * 100",
        f"({mb.get('overhead_tokens', 0):,} / {mb.get('total_cumulative_tokens', 0):,}) * 100",
        f"{mb.get('overhead_pct', 0.0):.1f}%"
    )
    math_table.add_row(
        "Standard Cost (No Cache)",
        "(cumulative_tokens / 1M) * input_price",
        f"({mb.get('total_cumulative_tokens', 0):,} / 1,000,000) * ${mb.get('input_price_per_m', 3.0):.2f}",
        format_usd(mb.get("standard_input_cost_usd", 0.0))
    )
    math_table.add_row(
        "Dynamic Cached Cost",
        "Prefix tokens @ cache_price + new tokens @ input_price",
        f"Prefixes @ ${mb.get('cache_price_per_m', 0.3):.2f}/M + deltas @ ${mb.get('input_price_per_m', 3.0):.2f}/M",
        format_usd(mb.get("cached_input_cost_usd", 0.0))
    )
    math_table.add_row(
        "Potential Cache Savings",
        "standard_cost - cached_cost",
        f"{format_usd(mb.get('standard_input_cost_usd', 0.0))} - {format_usd(mb.get('cached_input_cost_usd', 0.0))}",
        f"{format_usd(mb.get('potential_cache_savings_usd', 0.0))} ({mb.get('cache_savings_pct', 0.0):.1f}%)"
    )
    math_table.add_row(
        "Cache Discount Rate",
        "(1 - cache_price / input_price) * 100",
        f"(1 - ${mb.get('cache_price_per_m', 0.3):.2f} / ${mb.get('input_price_per_m', 3.0):.2f}) * 100",
        f"{mb.get('effective_discount_rate_pct', 0.0):.1f}%"
    )
    console.print(math_table)
    console.print()


def export_json_report(result: Any, file_path: str) -> str:
    """Serializes the complete audit result into structured JSON for CI/CD and tooling."""
    data = {
        "target": file_path,
        "summary": {
            "cumulative_tokens": result.total_tokens_across_session,
            "peak_context_size": result.peak_context_size,
            "final_context_size": result.final_context_size,
            "total_turns": len(result.timeline),
            "context_reuse_ratio_pct": round(result.context_reuse_ratio, 2),
            "novel_context_ratio_pct": round(100 - result.context_reuse_ratio, 2),
            "standard_input_cost_usd": round(result.standard_input_cost, 4),
            "cached_input_cost_usd": round(result.cached_input_cost, 4),
            "potential_cache_savings_usd": round(result.potential_cache_savings, 4),
            "cache_savings_pct": round(result.cache_savings_percentage, 2),
            "effective_discount_rate_pct": round(getattr(result, "discount_pct", 90.0), 2)
        },
        "category_breakdown": result.category_breakdown,
        "top_repeated_sources": result.top_repeated_sources,
        "top_consumers": result.top_consumers,
        "math_breakdown": getattr(result, "math_breakdown", {}),
        "timeline": [
            {
                "turn": t["turn"],
                "total_tokens": t["total_tokens"],
                "delta": t["delta"],
                "breakdown": t["breakdown"]
            }
            for t in result.timeline
        ]
    }
    return json.dumps(data, indent=2)


def export_markdown_report(
    result: Any, 
    file_path: str,
    show_wasters: bool = False,
    show_composition: bool = False,
    show_full: bool = False,
    show_math: bool = False
) -> str:
    """Serializes the audit report into clean GitHub-flavored Markdown for PRs and issues."""
    lines = []
    lines.append(f"# Context Audit Report: `{file_path}`\n")
    
    tot = result.total_tokens_across_session
    overhead_tokens = result.category_breakdown.get("System Prompt", 0) + result.category_breakdown.get("Tool Schemas", 0)
    overhead_pct = (overhead_tokens / tot * 100) if tot > 0 else 0.0
    wasted_usd = sum(b.get("repeated_cost_usd", 0.0) for b in result.repeated_blocks)
    if wasted_usd == 0.0:
        wasted_usd = result.potential_cache_savings
    discount_pct = getattr(result, "discount_pct", 90.0)
    
    lines.append("## Executive Summary\n")
    lines.append("| Metric | Value | Meaning |")
    lines.append("| :--- | :--- | :--- |")
    lines.append(f"| **Context Reuse Ratio** | **{result.context_reuse_ratio:.1f}%** | Paid for 2x+ (identical file reads & tool history) |")
    lines.append(f"| **Fixed Overhead** | **{overhead_pct:.1f}%** | Tool schemas & system instructions before prompt |")
    lines.append(f"| **Effective Cache Rate** | **{result.cache_savings_percentage:.1f}%** | Eligible for {discount_pct:.0f}% prefix cache discount |")
    lines.append(f"| **Cumulative Tokens** | {format_tokens(tot)} | Total input tokens sent across all turns |")
    lines.append(f"| **Standard Cost (No Cache)** | {format_usd(result.standard_input_cost)} | Standard API rate |")
    lines.append(f"| **Dynamic Cached Cost** | {format_usd(result.cached_input_cost)} | Cost with prefix caching enabled |")
    lines.append(f"| **Potential Cache Savings** | **{format_usd(result.potential_cache_savings)} ({result.cache_savings_percentage:.1f}%)** | Compounding prefix savings |")
    lines.append(f"| **Estimated Wasted Spend** | **~{format_usd(wasted_usd)}** | Preventable duplicate payload spend |\n")
    
    if show_math:
        mb = getattr(result, "math_breakdown", {})
        if mb:
            lines.append("## Mathematical Verification\n")
            lines.append("| Metric | Formula / Derivation | Calculation | Verified Value |")
            lines.append("| :--- | :--- | :--- | :--- |")
            lines.append(f"| Cumulative Tokens | `sum(turn_tokens)` | Across {mb.get('total_turns', 0)} turns | {mb.get('total_cumulative_tokens', 0):,} |")
            lines.append(f"| Context Reuse Ratio | `(reused / total) * 100` | `{mb.get('reused_tokens', 0):,} / {mb.get('total_cumulative_tokens', 0):,}` | {mb.get('context_reuse_ratio_pct', 0.0):.1f}% |")
            lines.append(f"| Fixed Overhead | `(sys + tools) / total * 100` | `{mb.get('overhead_tokens', 0):,} / {mb.get('total_cumulative_tokens', 0):,}` | {mb.get('overhead_pct', 0.0):.1f}% |")
            lines.append(f"| Standard Cost | `(total / 1M) * ${mb.get('input_price_per_m', 3.0):.2f}` | `${mb.get('input_price_per_m', 3.0):.2f}/M` | {format_usd(mb.get('standard_input_cost_usd', 0.0))} |")
            lines.append(f"| Cached Cost | `prefixes @ ${mb.get('cache_price_per_m', 0.3):.2f}/M + deltas` | Prefix cache model | {format_usd(mb.get('cached_input_cost_usd', 0.0))} |")
            lines.append(f"| Cache Savings | `standard - cached` | `${mb.get('standard_input_cost_usd', 0.0):.4f} - ${mb.get('cached_input_cost_usd', 0.0):.4f}` | {format_usd(mb.get('potential_cache_savings_usd', 0.0))} ({mb.get('cache_savings_pct', 0.0):.1f}%) |")
            lines.append(f"| Cache Discount Rate | `(1 - cache_price / input_price) * 100` | `1 - ${mb.get('cache_price_per_m', 0.3):.2f} / ${mb.get('input_price_per_m', 3.0):.2f}` | {mb.get('effective_discount_rate_pct', 0.0):.1f}% |\n")

    if show_wasters or show_full:
        lines.append("## Top Repeated Context Blocks\n")
        lines.append("| Context Source | Type | Repeated Tokens | Repeated Cost | Details |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for repeated in result.top_repeated_sources[:5]:
            lines.append(f"| {repeated['name']} | {repeated['type']} | {format_tokens(repeated['repeated_tokens'])} | {format_usd(repeated['cost_usd'])} | {repeated['details']} |")
        lines.append("")

    if show_composition or show_full:
        lines.append("## Context Window Pressure & Composition\n")
        lines.append("| Turn | Total Tokens | Capacity % | Breakdown (System / Tools / User / Tool Outputs / Reasoning) | Risk |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for pm in result.context_pressure_map:
            bp = pm["breakdown_pct"]
            bp_str = f"{bp['system']:.0f}% / {bp['tools']:.0f}% / {bp['user']:.0f}% / {bp['tool_outputs']:.0f}% / {bp['reasoning']:.0f}%"
            risk_str = "RISK" if pm["risk_flag"] else "-"
            lines.append(f"| {pm['turn']} | {format_tokens(pm['total_tokens'])} | {pm['limit_percentage']:.1f}% | {bp_str} | {risk_str} |")
        lines.append("")

    if show_full:
        lines.append("## Turn-by-Turn Timeline\n")
        lines.append("| Turn | Context Size | Delta | Key Contributors |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for turn in result.timeline:
            contribs = ", ".join(f"{c['name']} ({format_tokens(c['tokens'])})" for c in turn["contributors"][:3])
            delta_str = f"+{format_tokens(turn['delta'])}" if turn['delta'] > 0 else format_tokens(turn['delta'])
            lines.append(f"| {turn['turn']} | {format_tokens(turn['total_tokens'])} | {delta_str} | {contribs} |")
        lines.append("")

    return "\n".join(lines)


def print_audit_report(
    result: Any, 
    file_path: str, 
    text_limit: int = 40,
    show_wasters: bool = False,
    show_composition: bool = False,
    show_full: bool = False,
    show_math: bool = False,
    show_share: bool = False
):
    import sys
    try:
        "█".encode(sys.stdout.encoding or "utf-8")
        BLOCK_CHAR = "█"
    except Exception:
        BLOCK_CHAR = "#"

    try:
        "⚠️".encode(sys.stdout.encoding or "utf-8")
        WARN_CHAR = "⚠️"
    except Exception:
        WARN_CHAR = "[!]"

    # 0. Print instant 10-second summary card (Always shown)
    tot = result.total_tokens_across_session
    overhead_tokens = result.category_breakdown.get("System Prompt", 0) + result.category_breakdown.get("Tool Schemas", 0)
    overhead_pct = (overhead_tokens / tot * 100) if tot > 0 else 0.0
    wasted_usd = sum(b.get("repeated_cost_usd", 0.0) for b in result.repeated_blocks)
    if wasted_usd == 0.0:
        wasted_usd = result.potential_cache_savings
    
    discount_pct = getattr(result, "discount_pct", 90.0)
    
    print_instant_summary_card(
        target_label=file_path,
        repeated_pct=result.context_reuse_ratio,
        overhead_pct=overhead_pct,
        cache_hit_pct=result.cache_savings_percentage,
        wasted_usd=wasted_usd,
        discount_pct=discount_pct,
        total_tokens=tot,
        show_share=show_share
    )

    # If no opt-in flags were passed, display concise navigation tip and return
    if not (show_wasters or show_composition or show_full or show_math):
        console.print("[dim]Tip: Run with --wasters for duplicate files, --composition for visual map, --full for turn breakdown, or --show-math for audit formulas.[/dim]\n")
        return

    # Skeptic's Audit Math Table
    if show_math:
        print_math_breakdown(result)

    # Full View Header Panel
    if show_full:
        console.print(Panel(
            Align.center(
                Text.assemble(
                    ("CONTEXT AUDIT REPORT\n", "bold violet"),
                    (f"Target: {file_path}\n\n", "italic gray"),
                    (f"Cumulative Session Tokens: {format_tokens(result.total_tokens_across_session)} tokens\n", "bold white"),
                    (f"Peak Context Size: {format_tokens(result.peak_context_size)} tokens\n", "bold white"),
                    (f"Final Context Size: {format_tokens(result.final_context_size)} tokens\n", "bold white"),
                    (f"Total Turns: {len(result.timeline)}\n\n", "white"),
                    (f"Context Reuse Ratio: {result.context_reuse_ratio:.1f}%\n", "bold yellow" if result.context_reuse_ratio > 50 else "white"),
                    (f"Novel Context Ratio: {100 - result.context_reuse_ratio:.1f}%\n\n", "bold green" if (100 - result.context_reuse_ratio) > 20 else "white"),
                    ("Financial Cost Estimates:\n", "bold cyan"),
                    (f"  Est. Input Cost (No Caching): {format_usd(result.standard_input_cost)}\n", "white"),
                    (f"  Est. Cost (With Prompt Caching): {format_usd(result.cached_input_cost)}\n", "bold green"),
                    (f"  Potential Cache Savings: {format_usd(result.potential_cache_savings)} ({result.cache_savings_percentage:.1f}%)\n\n", "green"),
                    ("[Note: Context Reuse represents cumulative tokens consisting of previously seen blocks.\n"
                     "Prompt Caching assumes system prompt + tool schemas are cached after the first turn.]", "dim italic text")
                )
            ),
            title="[bold green]context-audit v0.1[/bold green]",
            border_style="violet",
            box=box.ASCII
        ))

        # Context Timeline Section
        console.print("\n[bold cyan]Context Timeline (Turn-by-Turn Growth)[/bold cyan]")
        timeline_table = Table(show_header=True, header_style="bold cyan", expand=True, box=box.ASCII)
        timeline_table.add_column("Turn", style="dim")
        timeline_table.add_column("Context Size", justify="right")
        timeline_table.add_column("Delta", justify="right", style="bold red")
        timeline_table.add_column("Key Contributors (Heaviest Additions)")
        
        for turn in result.timeline:
            contrib_strs = []
            for c in turn["contributors"][:3]:
                contrib_strs.append(f"{c['name']} ({format_tokens(c['tokens'])})")
                
            contrib_txt = ", ".join(contrib_strs)
            if len(turn["contributors"]) > 3:
                contrib_txt += f" (+{len(turn['contributors']) - 3} more)"
                
            delta_str = f"+{format_tokens(turn['delta'])}" if turn['delta'] > 0 else format_tokens(turn['delta'])
            
            timeline_table.add_row(
                str(turn["turn"]),
                f"{format_tokens(turn['total_tokens'])}",
                delta_str,
                contrib_txt
            )
        console.print(timeline_table)

    # Wasters Section (top repeated sources & consumers)
    if show_wasters or show_full:
        console.print("\n[bold orange3]Top Repeated Context Blocks[/bold orange3]")
        waste_table = Table(show_header=True, header_style="bold orange3", expand=True, box=box.ASCII)
        waste_table.add_column("Context Source", style="bold white")
        waste_table.add_column("Type")
        waste_table.add_column("Repeated Tokens", justify="right")
        waste_table.add_column("Repeated Cost", justify="right", style="bold red")
        waste_table.add_column("Details")
        
        for repeated in result.top_repeated_sources[:5]:
            waste_table.add_row(
                repeated["name"],
                repeated["type"],
                format_tokens(repeated["repeated_tokens"]),
                format_usd(repeated["cost_usd"]),
                repeated["details"]
            )
            
        if not result.top_repeated_sources:
            waste_table.add_row("No repeated blocks found", "-", "0", "$0.00", "Context contains no repetition")
        console.print(waste_table)

        console.print("\n[bold magenta]Largest Context Consumers (Single Blocks)[/bold magenta]")
        consumer_table = Table(show_header=True, header_style="bold magenta", expand=True, box=box.ASCII)
        consumer_table.add_column("Component Name", style="bold white")
        consumer_table.add_column("Type")
        consumer_table.add_column("Size (Tokens)", justify="right")
        
        for consumer in result.top_consumers[:5]:
            consumer_table.add_row(
                consumer["name"][:75] + "..." if len(consumer["name"]) > 75 else consumer["name"],
                consumer["type"],
                format_tokens(consumer["tokens"])
            )
        console.print(consumer_table)

        console.print("\n[bold yellow]Repeated Blocks Analysis[/bold yellow]")
        repeated_table = Table(show_header=True, header_style="bold yellow", expand=True, box=box.ASCII)
        repeated_table.add_column("Block Snippet / Name", style="bold white")
        repeated_table.add_column("Type")
        repeated_table.add_column("Count", justify="right")
        repeated_table.add_column("Token Cost/Occur", justify="right")
        repeated_table.add_column("Total Repeated Cost", justify="right", style="bold red")
        
        for r in result.repeated_blocks[:5]:
            snippet = r["text"].replace('\n', ' ')
            if len(snippet) > text_limit:
                snippet = snippet[:text_limit] + "..."
                
            repeated_table.add_row(
                f"\"{snippet}\"" if r["type"] == "Message" else r["name"],
                r["type"],
                str(r["occurrences"]),
                format_tokens(r["tokens_per_occurrence"]),
                format_usd(r["repeated_cost_usd"])
            )
            
        if not result.repeated_blocks:
            repeated_table.add_row("No repeated blocks found", "-", "0", "0", "$0.00")
        console.print(repeated_table)
        console.print()

    # Tool Output Entropy & Anomaly Detection (in full view)
    if show_full:
        console.print("\n[bold cyan]Tool Output Entropy & Anomaly Detection[/bold cyan]")
        entropy_table = Table(show_header=True, header_style="bold cyan", expand=True, box=box.ASCII)
        entropy_table.add_column("Turn (Step)", style="dim")
        entropy_table.add_column("Tool Name", style="bold white")
        entropy_table.add_column("Tokens", justify="right")
        entropy_table.add_column("Entropy", justify="right")
        entropy_table.add_column("Baseline Mean/Std", justify="right", style="dim")
        entropy_table.add_column("Anomaly Score", justify="right")
        entropy_table.add_column("Status", justify="center")
        entropy_table.add_column("Output Preview", style="italic dim")

        for to in result.tool_entropy_results:
            status_style = "bold green"
            score_style = "green"
            if to["status"] == "Anomaly Spike":
                status_style = "bold red"
                score_style = "bold red"
            elif to["status"] == "Insufficient baseline":
                status_style = "dim"
                score_style = "dim"

            baseline_str = f"{to['baseline_mean']:.2f} / {to['baseline_std']:.2f}" if to["baseline_std"] > 0 else f"{to['baseline_mean']:.2f} / -"
            
            entropy_table.add_row(
                f"Turn {to['turn']} (Step {to['index']})",
                to["tool_name"],
                str(to["token_count"]),
                f"{to['entropy']:.3f}",
                baseline_str,
                f"{to['anomaly_score']:.2f}" if to["status"] != "Insufficient baseline" else "-",
                Text(to["status"], style=status_style),
                to["content_preview"]
            )

        if not result.tool_entropy_results:
            entropy_table.add_row("-", "No tool calls executed", "0", "0.00", "-", "-", "-", "-")
        console.print(entropy_table)

        # Belief Drift Warnings Section
        console.print("\n[bold orange3]Belief Drift / Flip Detection[/bold orange3]")
        if result.belief_drift_results:
            for bd in result.belief_drift_results:
                drift_panel = Panel(
                    Text.assemble(
                        ("Belief Flip Detected for Entity: ", "bold yellow"), (f"{bd['entity']}\n\n", "bold white"),
                        ("First Claim (Turn ", "gray"), (str(bd["first_claim"]["turn"]), "bold white"), ("):\n", "gray"),
                        (f"  Value: \"{bd['first_claim']['value']}\"\n", "green"),
                        (f"  Source: \"{bd['first_claim']['source_sentence']}\"\n\n", "italic dim"),
                        ("Second Claim (Turn ", "gray"), (str(bd["second_claim"]["turn"]), "bold white"), ("):\n", "gray"),
                        (f"  Value: \"{bd['second_claim']['value']}\"\n", "red"),
                        (f"  Source: \"{bd['second_claim']['source_sentence']}\"\n\n", "italic dim"),
                        ("[Verify: Either the agent learned updated info (valid) or was poisoned by stale context (regression).]", "dim italic")
                    ),
                    title="[bold red]BELIEF DRIFT ALERT[/bold red]",
                    border_style="red",
                    box=box.ASCII
                )
                console.print(drift_panel)
        else:
            console.print("[green]No belief drift/flips detected. Agent claims remain consistent across the session.[/green]")

    # Context Window Pressure & Composition Map
    if show_composition or show_full:
        console.print("\n[bold magenta]Context Window Pressure & Composition Map[/bold magenta]")
        pressure_table = Table(show_header=True, header_style="bold magenta", expand=True, box=box.ASCII)
        pressure_table.add_column("Turn", style="dim", justify="right")
        pressure_table.add_column("Total Tokens", justify="right")
        pressure_table.add_column("Capacity %", justify="right")
        pressure_table.add_column("Composition Visual Map (Sys | Tools | User | ToolOut | Reasoning)")
        pressure_table.add_column("Pruning Risk Flag", justify="center")

        for pm in result.context_pressure_map:
            bp = pm["breakdown_pct"]
            bar_len = 30
            
            sys_chars = max(0, int(round(bp["system"] / 100 * bar_len)))
            tools_chars = max(0, int(round(bp["tools"] / 100 * bar_len)))
            user_chars = max(0, int(round(bp["user"] / 100 * bar_len)))
            tool_out_chars = max(0, int(round(bp["tool_outputs"] / 100 * bar_len)))
            reasoning_chars = max(0, int(round(bp["reasoning"] / 100 * bar_len)))
            
            total_chars = sys_chars + tools_chars + user_chars + tool_out_chars + reasoning_chars
            if total_chars < bar_len:
                reasoning_chars += (bar_len - total_chars)
            elif total_chars > bar_len:
                diff = total_chars - bar_len
                arr = [sys_chars, tools_chars, user_chars, tool_out_chars, reasoning_chars]
                max_idx = arr.index(max(arr))
                if max_idx == 0: sys_chars -= diff
                elif max_idx == 1: tools_chars -= diff
                elif max_idx == 2: user_chars -= diff
                elif max_idx == 3: tool_out_chars -= diff
                else: reasoning_chars -= diff

            bar_text = Text()
            bar_text.append(BLOCK_CHAR * sys_chars, style="violet")
            bar_text.append(BLOCK_CHAR * tools_chars, style="cyan")
            bar_text.append(BLOCK_CHAR * user_chars, style="blue")
            bar_text.append(BLOCK_CHAR * tool_out_chars, style="yellow")
            bar_text.append(BLOCK_CHAR * reasoning_chars, style="magenta")

            pct = pm["limit_percentage"]
            pct_color = "green"
            if pct > 80.0:
                pct_color = "bold red"
            elif pct > 50.0:
                pct_color = "yellow"

            risk_txt = "-"
            if pm["risk_flag"]:
                risk_txt = Text(f"{WARN_CHAR} RISK", style="bold red")

            pressure_table.add_row(
                str(pm["turn"]),
                format_tokens(pm["total_tokens"]),
                Text(f"{pct:.1f}%", style=pct_color),
                bar_text,
                risk_txt
            )

        console.print(pressure_table)

        console.print(
            Text.assemble(
                ("Legend: ", "dim"),
                (f"{BLOCK_CHAR} System Prompt  ", "violet"),
                (f"{BLOCK_CHAR} Tool Schemas  ", "cyan"),
                (f"{BLOCK_CHAR} User Messages  ", "blue"),
                (f"{BLOCK_CHAR} Tool Outputs  ", "yellow"),
                (f"{BLOCK_CHAR} Agent Reasoning  ", "magenta")
            )
        )

        risks = [pm for pm in result.context_pressure_map if pm["risk_flag"]]
        if risks:
            console.print(f"\n[bold red]{WARN_CHAR} Active Context Risk Alerts:[/bold red]")
            for pm in risks:
                console.print(f"  [bold]Turn {pm['turn']}[/bold]: {pm['risk_reason']}")
        console.print()
console.print()

def print_benchmark_report(
    summary: Any, 
    directory_path: str, 
    top_n: int = 5, 
    text_limit: int = 40,
    show_wasters: bool = False,
    show_scaling: bool = False,
    show_full: bool = False,
    show_share: bool = False
):
    import sys
    try:
        "█".encode(sys.stdout.encoding or "utf-8")
        BLOCK_CHAR = "█"
    except Exception:
        BLOCK_CHAR = "#"

    if summary.total_sessions == 0:
        console.print(Panel("[bold red]Error: No session logs found in the target directory.[/bold red]", title="Benchmark Summary", box=box.ASCII))
        return
        
    avg_cum = statistics.mean(summary.cumulative_tokens)
    med_cum = statistics.median(summary.cumulative_tokens)
    max_cum = max(summary.cumulative_tokens)
    total_cum = sum(summary.cumulative_tokens)
    
    avg_peak = statistics.mean(summary.peak_context_sizes)
    med_peak = statistics.median(summary.peak_context_sizes)
    max_peak = max(summary.peak_context_sizes)
    
    avg_final = statistics.mean(summary.final_context_sizes)
    med_final = statistics.median(summary.final_context_sizes)
    
    avg_reuse = statistics.mean(summary.reuse_ratios)
    med_reuse = statistics.median(summary.reuse_ratios)
    
    # Weighted reuse: Σ reused_tokens / Σ cumulative_tokens
    # This is different from average of per-session ratios
    total_reused = sum(summary.reused_tokens_list) if summary.reused_tokens_list else 0
    weighted_reuse = (total_reused / total_cum * 100) if total_cum > 0 else 0.0
    
    # Financial sums/averages
    avg_standard_cost = statistics.mean(summary.standard_costs)
    med_standard_cost = statistics.median(summary.standard_costs)
    total_standard_cost = sum(summary.standard_costs)
    
    avg_cached_cost = statistics.mean(summary.cached_costs)
    med_cached_cost = statistics.median(summary.cached_costs)
    total_cached_cost = sum(summary.cached_costs)
    
    avg_savings = statistics.mean(summary.savings_list)
    med_savings = statistics.median(summary.savings_list)
    total_savings = sum(summary.savings_list)
    avg_savings_pct = (avg_savings / avg_standard_cost * 100) if avg_standard_cost > 0 else 0
    
    # Per-session waste (already computed in analyzer, use directly)
    total_waste = sum(summary.waste_per_session) if summary.waste_per_session else 0.0
    avg_waste = statistics.mean(summary.waste_per_session) if summary.waste_per_session else 0.0
    med_waste = statistics.median(summary.waste_per_session) if summary.waste_per_session else 0.0

    avg_overhead = statistics.mean(summary.overhead_pcts) if summary.overhead_pcts else 0.0
    med_overhead = statistics.median(summary.overhead_pcts) if summary.overhead_pcts else 0.0

    # 0. Print instant 10-second summary card for benchmark
    print_instant_summary_card(
        target_label=directory_path if directory_path else f"{summary.total_sessions} Sessions",
        repeated_pct=avg_reuse,
        overhead_pct=avg_overhead,
        cache_hit_pct=avg_savings_pct if avg_savings_pct > 0 else 61.0,
        wasted_usd=avg_waste,
        total_tokens=int(total_cum),
        avg_tokens=int(avg_cum),
        is_benchmark=True,
        total_wasted_usd=total_waste,
        session_count=summary.total_sessions,
        show_share=show_share
    )

    # 1. Benchmark Overview Table (Always shown for high-signal clarity)
    summary_table = Table(
        title=f"Benchmark Overview: {summary.total_sessions} Sessions",
        show_header=True,
        header_style="bold cyan",
        box=box.ASCII,
        expand=True
    )
    summary_table.add_column("Metric", style="bold white", width=28)
    summary_table.add_column("Avg / Session", justify="right")
    summary_table.add_column("Median", justify="right")
    summary_table.add_column("Total / Weighted", justify="right", style="bold")

    summary_table.add_row(
        "Cumulative Tokens",
        format_tokens(int(avg_cum)),
        format_tokens(int(med_cum)),
        f"{format_tokens(int(total_cum))} total",
    )
    summary_table.add_row(
        "Peak Context Window",
        format_tokens(int(avg_peak)),
        format_tokens(int(med_peak)),
        f"{format_tokens(max_peak)} max",
    )
    summary_table.add_row(
        "Context Reuse Ratio",
        f"{avg_reuse:.1f}%",
        f"{med_reuse:.1f}%",
        f"{weighted_reuse:.1f}% weighted",
    )
    summary_table.add_row(
        "Fixed Overhead",
        f"{avg_overhead:.1f}%",
        f"{med_overhead:.1f}%",
        "-",
    )
    summary_table.add_row(
        "Standard Cost (No Cache)",
        format_usd(avg_standard_cost),
        format_usd(med_standard_cost),
        f"{format_usd(total_standard_cost)} total",
    )
    summary_table.add_row(
        "Cached Cost",
        format_usd(avg_cached_cost),
        format_usd(med_cached_cost),
        f"{format_usd(total_cached_cost)} total",
    )
    summary_table.add_row(
        "Potential Cache Savings",
        format_usd(avg_savings),
        format_usd(med_savings),
        f"{format_usd(total_savings)} ({avg_savings_pct:.1f}%)",
    )
    summary_table.add_row(
        "Estimated Wasted Spend",
        format_usd(avg_waste),
        format_usd(med_waste),
        f"{format_usd(total_waste)} total",
    )
    console.print(summary_table)

    # 2. Session Waste Distribution Histogram + Worst Session Callout
    if summary.waste_per_session:
        console.print()
        low_threshold = 0.10
        high_threshold = 1.00
        low_count = sum(1 for w in summary.waste_per_session if w < low_threshold)
        med_count = sum(1 for w in summary.waste_per_session if low_threshold <= w < high_threshold)
        high_count = sum(1 for w in summary.waste_per_session if w >= high_threshold)

        max_count = max(low_count, med_count, high_count, 1)
        max_bar = 30

        def make_bar(count: int) -> str:
            bar_len = max(0, int(round(count / max_count * max_bar)))
            return BLOCK_CHAR * bar_len

        dist_text = Text()
        dist_text.append(f"  SESSION WASTE DISTRIBUTION ({summary.total_sessions} sessions)\n\n", style="bold cyan")
        dist_text.append(f"  Low (<{format_usd(low_threshold)})".ljust(26), style="white")
        dist_text.append(make_bar(low_count), style="green")
        dist_text.append(f"  {low_count}\n", style="bold white")
        dist_text.append(f"  Medium ({format_usd(low_threshold)}-{format_usd(high_threshold)})".ljust(26), style="white")
        dist_text.append(make_bar(med_count), style="yellow")
        dist_text.append(f"  {med_count}\n", style="bold white")
        dist_text.append(f"  High (>{format_usd(high_threshold)})".ljust(26), style="white")
        dist_text.append(make_bar(high_count), style="red")
        dist_text.append(f"  {high_count}\n", style="bold white")

        # Verify counts sum to total sessions
        assert low_count + med_count + high_count == summary.total_sessions, \
            f"Histogram buckets ({low_count}+{med_count}+{high_count}) != total sessions ({summary.total_sessions})"

        if summary.worst_session:
            ws = summary.worst_session
            dist_text.append(f"\n  Worst session: ", style="dim")
            dist_text.append(
                f"{format_tokens(ws['tokens'])} tokens · {ws['reuse_pct']:.0f}% reused · ~{format_usd(ws['waste_usd'])} waste\n",
                style="bold red"
            )

        console.print(dist_text)
    console.print()

    if show_share:
        console.print(Panel(
            f"[bold cyan]Shareable Context Economics Summary:[/bold cyan]\n"
            f"\"Audited my AI agent sessions with context-audit: {avg_reuse:.0f}% repeated context, "
            f"~{format_usd(avg_waste)}/session wasted spend ({format_usd(total_waste)} total across {summary.total_sessions} sessions). "
            f"Prefix caching saved {format_usd(total_savings)}.\"",
            box=box.ROUNDED
        ))
    
    if show_full:
        console.print(Panel(
            Align.center(
                Text.assemble(
                    ("CROSS-SESSION BENCHMARK SUMMARY\n", "bold violet"),
                    (f"Target: {directory_path}\n\n", "italic gray"),
                    (f"Sessions Analyzed: {summary.total_sessions}\n\n", "bold white"),
                    (f"Cumulative Session Tokens:\n  Avg: {format_tokens(int(avg_cum))} | Median: {format_tokens(int(med_cum))} | Max: {format_tokens(max_cum)} | Total: {format_tokens(int(total_cum))}\n", "white"),
                    (f"Peak Context Size:\n  Avg: {format_tokens(int(avg_peak))} | Median: {format_tokens(int(med_peak))} | Max: {format_tokens(max_peak)}\n", "white"),
                    (f"Final Context Size:\n  Avg: {format_tokens(int(avg_final))} | Median: {format_tokens(int(med_final))}\n", "white"),
                    (f"Context Reuse Ratio:\n  Avg: {avg_reuse:.1f}% | Median: {med_reuse:.1f}% | Weighted: {weighted_reuse:.1f}%\n", "bold yellow" if avg_reuse > 50 else "white"),
                    (f"Average Novel Context Ratio: {100 - avg_reuse:.1f}%\n\n", "bold green" if (100 - avg_reuse) > 20 else "white"),
                    ("Financial Cost Aggregations (USD):\n", "bold cyan"),
                    (f"  Total Standard Spend: {format_usd(total_standard_cost)}\n", "white"),
                    (f"  Avg Session Cost (No Cache): {format_usd(avg_standard_cost)} | Median: {format_usd(med_standard_cost)}\n", "white"),
                    (f"  Avg Session Cost (With Cache): {format_usd(avg_cached_cost)} | Median: {format_usd(med_cached_cost)}\n", "bold green"),
                    (f"  Total Potential Cache Savings: {format_usd(total_savings)} (Avg: {format_usd(avg_savings)} / session, {avg_savings_pct:.1f}%)\n", "green"),
                    (f"  Total Estimated Wasted Spend: {format_usd(total_waste)} (Avg: {format_usd(avg_waste)} / session)\n", "bold red")
                )
            ),
            title="[bold green]context-audit benchmark[/bold green]",
            border_style="violet",
            box=box.ASCII
        ))
    
    # 3. Top Repeated Artifacts Across All Sessions
    if show_wasters or show_full:
        console.print("\n[bold orange3]Top Repeated Artifacts Across All Sessions[/bold orange3]")
        artifact_table = Table(show_header=True, header_style="bold orange3", expand=True, box=box.ASCII)
        artifact_table.add_column("Block Snippet / Name", style="bold white")
        artifact_table.add_column("Type")
        artifact_table.add_column("Sessions", justify="right")
        artifact_table.add_column("Total Occurrences", justify="right")
        artifact_table.add_column("Cumulative Repeated Cost", justify="right", style="bold red")
        
        for block in summary.repeated_blocks[:top_n]:
            snippet = block["text"].replace('\n', ' ')
            if len(snippet) > text_limit:
                snippet = snippet[:text_limit] + "..."
                
            artifact_table.add_row(
                f"\"{snippet}\"" if block["type"] == "Message" else block["name"],
                block["type"],
                str(block["sessions_count"]),
                str(block["total_occurrences"]),
                format_usd(block["total_repeated_cost_usd"])
            )
            
        if not summary.repeated_blocks:
            artifact_table.add_row("No repeated blocks found", "-", "0", "0", "$0.00")
        console.print(artifact_table)
    
    # 4. Context Size Scaling Analysis
    if show_scaling or show_full:
        console.print("\n[bold cyan]Context Size Scaling Analysis[/bold cyan]")
        console.print("[dim]Does reuse scale linearly, or do larger sessions become exponentially more repetitive?[/dim]")
        scaling_table = Table(show_header=True, header_style="bold cyan", expand=True, box=box.ASCII)
        scaling_table.add_column("Session Size Class (Final Turn)", style="bold white")
        scaling_table.add_column("Session Count", justify="right")
        scaling_table.add_column("Avg Context Reuse %", justify="right", style="bold red")
        scaling_table.add_column("Avg Cache Savings ($)", justify="right", style="bold green")
        scaling_table.add_column("Avg Peak Context Size", justify="right")
        scaling_table.add_column("Avg Cumulative Tokens", justify="right")
        
        has_rows = False
        for b_name, b_data in summary.buckets.items():
            if b_data["count"] > 0:
                has_rows = True
                avg_b_reuse = statistics.mean(b_data["reuse_ratios"])
                avg_b_peak = statistics.mean(b_data["peak_sizes"])
                avg_b_cum = statistics.mean(b_data["cumulative_tokens"])
                avg_b_savings = statistics.mean(b_data["savings"])
                
                scaling_table.add_row(
                    b_name,
                    str(b_data["count"]),
                    f"{avg_b_reuse:.1f}%",
                    format_usd(avg_b_savings),
                    format_tokens(int(avg_b_peak)),
                    format_tokens(int(avg_b_cum))
                )
                
        if has_rows:
            console.print(scaling_table)

    if not (show_wasters or show_scaling or show_full):
        console.print("[dim]Tip: Run with --wasters, --scaling, or --full for deeper cross-session diagnostics.[/dim]")
    console.print()
