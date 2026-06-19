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

def print_audit_report(result: Any, file_path: str, text_limit: int = 40):
    console.print()
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

def print_benchmark_report(summary: Any, directory_path: str, top_n: int = 5, text_limit: int = 40):
    console.print()
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
