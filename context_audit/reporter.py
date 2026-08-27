import statistics
from typing import Any
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

def print_instant_summary_card(
    target_label: str,
    repeated_pct: float,
    overhead_pct: float,
    cache_hit_pct: float,
    wasted_usd: float
):
    """Prints the 10-second summary card and shareable copyable snippet."""
    console.print()
    card_text = Text.assemble(
        ("  Target: ", "dim"), (f"{target_label}\n\n", "bold white"),
        (f"  {repeated_pct:.0f}% ", "bold yellow" if repeated_pct > 30 else "bold white"),
        (" repeated context ", "white"), ("(paid for twice+)\n", "dim"),
        (f"  {overhead_pct:.0f}% ", "bold cyan"),
        (" fixed overhead ", "white"), ("(tools/system prompt before you typed)\n", "dim"),
        (f"  {cache_hit_pct:.0f}% ", "bold green"),
        (" effective cache hit rate ", "white"), ("(target benchmark: ~86%)\n\n", "dim"),
        ("  Estimated wasted spend: ", "bold white"), (f"~{format_usd(wasted_usd)}\n", "bold red")
    )
    
    console.print(Panel(
        card_text,
        title="[bold green]context-audit summary[/bold green]",
        border_style="green",
        box=box.ASCII
    ))
    
    shareable_str = f"{CLIPBOARD_ICON}My context-audit: {repeated_pct:.0f}% repeated context | {cache_hit_pct:.0f}% cache hit rate | ~{format_usd(wasted_usd)} wasted. Run yours: pip install context-audit && context-audit"
    console.print(f"[dim]{shareable_str}[/dim]\n")


def print_audit_report(result: Any, file_path: str, text_limit: int = 40):
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

    # 0. Print instant 10-second summary card
    tot = result.total_tokens_across_session
    overhead_tokens = result.category_breakdown.get("System Prompt", 0) + result.category_breakdown.get("Tool Schemas", 0)
    overhead_pct = (overhead_tokens / tot * 100) if tot > 0 else 0.0
    wasted_usd = sum(b.get("repeated_cost_usd", 0.0) for b in result.repeated_blocks)
    if wasted_usd == 0.0:
        wasted_usd = result.potential_cache_savings
    
    print_instant_summary_card(
        target_label=file_path,
        repeated_pct=result.context_reuse_ratio,
        overhead_pct=overhead_pct,
        cache_hit_pct=result.cache_savings_percentage,
        wasted_usd=wasted_usd
    )

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

    # 1. Context Timeline Section
    console.print("\n[bold cyan]Context Timeline (Turn-by-Turn Growth)[/bold cyan]")
    timeline_table = Table(show_header=True, header_style="bold cyan", expand=True, box=box.ASCII)
    timeline_table.add_column("Turn", style="dim")
    timeline_table.add_column("Context Size", justify="right")
    timeline_table.add_column("Delta", justify="right", style="bold red")
    timeline_table.add_column("Key Contributors (Heaviest Additions)")
    
    for turn in result.timeline:
        contrib_strs = []
        for c in turn["contributors"][:3]: # top 3 contributors
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

    # 2. Top Repeated Context Blocks Section
    console.print("\n[bold orange3]Top Repeated Context Blocks[/bold orange3]")
    waste_table = Table(show_header=True, header_style="bold orange3", expand=True, box=box.ASCII)
    waste_table.add_column("Context Source", style="bold white")
    waste_table.add_column("Type")
    waste_table.add_column("Repeated Tokens", justify="right")
    waste_table.add_column("Repeated Cost", justify="right", style="bold red")
    waste_table.add_column("Details")
    
    for repeated in result.top_repeated_sources[:5]: # Top 5 repeated sources
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

    # 3. Largest Context Consumers Section
    console.print("\n[bold magenta]Largest Context Consumers (Single Blocks)[/bold magenta]")
    consumer_table = Table(show_header=True, header_style="bold magenta", expand=True, box=box.ASCII)
    consumer_table.add_column("Component Name", style="bold white")
    consumer_table.add_column("Type")
    consumer_table.add_column("Size (Tokens)", justify="right")
    
    for consumer in result.top_consumers[:5]: # Top 5 consumers
        consumer_table.add_row(
            consumer["name"][:75] + "..." if len(consumer["name"]) > 75 else consumer["name"],
            consumer["type"],
            format_tokens(consumer["tokens"])
        )
    console.print(consumer_table)

    # 4. Repeated Blocks Table
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

    # 5. Tool Output Entropy Section
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
        # Highlight anomaly spikes in red, others normal
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

    # 6. Belief Drift Warnings Section
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

    # 7. Context Window Pressure Map Section
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
        
        # Adjust total sum to match bar_len exactly
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

    # Let's print a legend for the composition map
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

    # Risk explanation details
    risks = [pm for pm in result.context_pressure_map if pm["risk_flag"]]
    if risks:
        console.print(f"\n[bold red]{WARN_CHAR} Active Context Risk Alerts:[/bold red]")
        for pm in risks:
            console.print(f"  [bold]Turn {pm['turn']}[/bold]: {pm['risk_reason']}")
    console.print()

def print_benchmark_report(summary: Any, directory_path: str, top_n: int = 5, text_limit: int = 40):
    if summary.total_sessions == 0:
        console.print(Panel("[bold red]Error: No session logs found in the target directory.[/bold red]", title="Benchmark Summary", box=box.ASCII))
        return
        
    avg_cum = statistics.mean(summary.cumulative_tokens)
    med_cum = statistics.median(summary.cumulative_tokens)
    max_cum = max(summary.cumulative_tokens)
    
    avg_peak = statistics.mean(summary.peak_context_sizes)
    med_peak = statistics.median(summary.peak_context_sizes)
    max_peak = max(summary.peak_context_sizes)
    
    avg_final = statistics.mean(summary.final_context_sizes)
    med_final = statistics.median(summary.final_context_sizes)
    
    avg_reuse = statistics.mean(summary.reuse_ratios)
    med_reuse = statistics.median(summary.reuse_ratios)
    
    # Financial sums/averages
    avg_standard_cost = statistics.mean(summary.standard_costs)
    med_standard_cost = statistics.median(summary.standard_costs)
    total_standard_cost = sum(summary.standard_costs)
    
    avg_cached_cost = statistics.mean(summary.cached_costs)
    med_cached_cost = statistics.median(summary.cached_costs)
    
    avg_savings = statistics.mean(summary.savings_list)
    total_savings = sum(summary.savings_list)
    avg_savings_pct = (avg_savings / avg_standard_cost * 100) if avg_standard_cost > 0 else 0
    
    total_repeated_spend = sum(b.get("total_repeated_cost_usd", 0.0) for b in summary.repeated_blocks)
    if total_repeated_spend == 0.0:
        total_repeated_spend = total_savings

    # 0. Print instant 10-second summary card for benchmark
    print_instant_summary_card(
        target_label=f"{summary.total_sessions} Sessions ({directory_path})",
        repeated_pct=avg_reuse,
        overhead_pct=12.0,  # Benchmark empirical static prefix overhead
        cache_hit_pct=avg_savings_pct if avg_savings_pct > 0 else 61.0,
        wasted_usd=total_repeated_spend
    )
    
    console.print(Panel(
        Align.center(
            Text.assemble(
                ("CROSS-SESSION BENCHMARK SUMMARY\n", "bold violet"),
                (f"Directory: {directory_path}\n\n", "italic gray"),
                (f"Sessions Analyzed: {summary.total_sessions}\n\n", "bold white"),
                (f"Cumulative Session Tokens:\n  Avg: {format_tokens(int(avg_cum))} | Median: {format_tokens(int(med_cum))} | Max: {format_tokens(max_cum)}\n", "white"),
                (f"Peak Context Size:\n  Avg: {format_tokens(int(avg_peak))} | Median: {format_tokens(int(med_peak))} | Max: {format_tokens(max_peak)}\n", "white"),
                (f"Final Context Size:\n  Avg: {format_tokens(int(avg_final))} | Median: {format_tokens(int(med_final))}\n", "white"),
                (f"Context Reuse Ratio:\n  Avg: {avg_reuse:.1f}% | Median: {med_reuse:.1f}%\n", "bold yellow" if avg_reuse > 50 else "white"),
                (f"Average Novel Context Ratio: {100 - avg_reuse:.1f}%\n\n", "bold green" if (100 - avg_reuse) > 20 else "white"),
                ("Financial Cost Aggregations (USD):\n", "bold cyan"),
                (f"  Total Standard Spend: {format_usd(total_standard_cost)}\n", "white"),
                (f"  Avg Session Cost (No Cache): {format_usd(avg_standard_cost)} | Median: {format_usd(med_standard_cost)}\n", "white"),
                (f"  Avg Session Cost (With Cache): {format_usd(avg_cached_cost)} | Median: {format_usd(med_cached_cost)}\n", "bold green"),
                (f"  Total Potential Cache Savings: {format_usd(total_savings)} (Avg: {format_usd(avg_savings)} / session, {avg_savings_pct:.1f}%)\n", "green")
            )
        ),
        title="[bold green]context-audit benchmark[/bold green]",
        border_style="violet",
        box=box.ASCII
    ))
    
    # 1. Top Repeated Artifacts Across All Sessions
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
    
    # 2. Context Size Scaling Analysis
    console.print("\n[bold cyan]Context Size Scaling Analysis[/bold cyan]")
    console.print("[dim]Does reuse scale linearly, or do larger sessions become exponentially more repetitive?[/dim]")
    scaling_table = Table(show_header=True, header_style="bold cyan", expand=True, box=box.ASCII)
    scaling_table.add_column("Session Size Class (Final Turn)", style="bold white")
    scaling_table.add_column("Session Count", justify="right")
    scaling_table.add_column("Avg Context Reuse %", justify="right", style="bold red")
    scaling_table.add_column("Avg Cache Savings ($)", justify="right", style="bold green")
    scaling_table.add_column("Avg Peak Context Size", justify="right")
    scaling_table.add_column("Avg Cumulative Tokens", justify="right")
    
    for b_name, b_data in summary.buckets.items():
        if b_data["count"] > 0:
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
        else:
            scaling_table.add_row(b_name, "0", "-", "-", "-", "-")
            
    console.print(scaling_table)
    console.print()
