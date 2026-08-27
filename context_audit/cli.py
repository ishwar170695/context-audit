import argparse
import os
import sys
from context_audit import __version__
from context_audit.parser import load_session, discover_session_logs
from context_audit.analyzer import analyze_session, run_benchmark
from context_audit.reporter import print_audit_report, print_benchmark_report, console

def main():
    # If called with no arguments, run zero-config auto-discovery
    if len(sys.argv) == 1:
        run_auto_discover()
        return

    # If first argument is a file that exists and not a command, default to 'run <file>'
    if len(sys.argv) == 2 and sys.argv[1] not in ["run", "benchmark", "-h", "--help", "-v", "--version"]:
        if os.path.isfile(sys.argv[1]):
            sys.argv.insert(1, "run")
        elif os.path.isdir(sys.argv[1]):
            sys.argv.insert(1, "benchmark")

    parser = argparse.ArgumentParser(
        description="context-audit: 85-99% of your coding agent bill is invisible input tokens. See what's actually in your context window in 10 seconds."
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"context-audit v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    # run command
    run_parser = subparsers.add_parser("run", help="Audit token usage and cost for a single log file.")
    run_parser.add_argument(
        "log_path", type=str, help="Path to the session.json or transcript.jsonl log file."
    )
    run_parser.add_argument(
        "--text-limit", type=int, default=40, help="Character limit for repeated text snippets in the console report."
    )
    run_parser.add_argument(
        "--input-price", type=float, default=3.00, help="LLM standard input token price per million tokens (USD). Default: 3.00 (e.g. Claude 3.5 Sonnet)."
    )
    run_parser.add_argument(
        "--cache-price", type=float, default=0.30, help="LLM cache read token price per million tokens (USD). Default: 0.30 (e.g. 90% caching discount)."
    )
    run_parser.add_argument(
        "--context-limit", type=int, default=100000, help="LLM maximum context window size (default: 100000)."
    )
    run_parser.add_argument(
        "--llm-extract", action="store_true", help="Enable LLM-based entity claim extraction (requires API keys in env)."
    )
    run_parser.add_argument(
        "--entropy-threshold", type=float, default=2.0, help="Z-score threshold for tool output entropy anomaly detection (default: 2.0)."
    )

    # benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Benchmark and aggregate token usage/costs across multiple sessions recursively.")
    bench_parser.add_argument(
        "directory_path", type=str, help="Directory containing transcript.jsonl and/or session.json files."
    )
    bench_parser.add_argument(
        "--top-n", type=int, default=5, help="Number of top repeated artifacts to show."
    )
    bench_parser.add_argument(
        "--text-limit", type=int, default=40, help="Character limit for repeated text snippets in the console report."
    )
    bench_parser.add_argument(
        "--input-price", type=float, default=3.00, help="LLM standard input token price per million tokens (USD). Default: 3.00."
    )
    bench_parser.add_argument(
        "--cache-price", type=float, default=0.30, help="LLM cache read token price per million tokens (USD). Default: 0.30."
    )

    args = parser.parse_args()

    if args.command is None:
        run_auto_discover()
        return

    if args.command == "run":
        try:
            # 1. Parse log
            session = load_session(args.log_path)
            
            # 2. Analyze
            result = analyze_session(
                session, 
                input_price=args.input_price,
                cache_price=args.cache_price,
                context_limit=args.context_limit,
                use_llm=args.llm_extract,
                entropy_threshold=args.entropy_threshold
            )
            
            # 3. Report
            print_audit_report(
                result, 
                args.log_path, 
                text_limit=args.text_limit
            )
            
        except FileNotFoundError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)
        except Exception as e:
            import traceback
            console.print(f"[bold red]An error occurred while analyzing the file:[/bold red] {e}")
            traceback.print_exc()
            sys.exit(1)
            
    elif args.command == "benchmark":
        try:
            # 1. Run benchmark analysis
            summary = run_benchmark(
                args.directory_path,
                input_price=args.input_price,
                cache_price=args.cache_price
            )
            
            # 2. Report benchmark results
            print_benchmark_report(
                summary,
                args.directory_path,
                top_n=args.top_n,
                text_limit=args.text_limit
            )
        except Exception as e:
            import traceback
            console.print(f"[bold red]An error occurred during benchmarking:[/bold red] {e}")
            traceback.print_exc()
            sys.exit(1)

def run_auto_discover():
    """Zero-config auto discovery of local agent sessions."""
    console.print("\n[bold cyan]Scanning for local Claude Code / Cursor / IDE agent session logs...[/bold cyan]")
    discovered_files = discover_session_logs()
    
    if not discovered_files:
        console.print("[yellow]No local session logs found automatically in default paths (~/.claude, ~/.cursor, ~/.gemini, ./)![/yellow]")
        console.print("Pass a session log directly with:\n  [bold green]context-audit run <path/to/transcript.jsonl>[/bold green]\n")
        return
        
    console.print(f"[green]Discovered {len(discovered_files)} agent session log(s). Analyzing...[/green]")
    try:
        summary = run_benchmark(discovered_files)
        print_benchmark_report(
            summary,
            directory_path=f"Auto-Discovered ({len(discovered_files)} logs)",
            top_n=5,
            text_limit=40
        )
    except Exception as e:
        import traceback
        console.print(f"[bold red]An error occurred during auto-analysis:[/bold red] {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
