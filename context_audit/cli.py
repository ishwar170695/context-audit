import argparse
import sys
from context_audit import __version__
from context_audit.parser import load_session
from context_audit.analyzer import analyze_session, run_benchmark
from context_audit.reporter import print_audit_report, print_benchmark_report

def main():
    parser = argparse.ArgumentParser(
        description="context-audit: Identify where your LLM tokens are going, frame costs, and spot prompt caching potential."
    )
    parser.add_argument(
        "--version", action="version", version=f"context-audit v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

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

    if args.command == "run":
        try:
            # 1. Parse log
            session = load_session(args.log_path)
            
            # 2. Analyze
            result = analyze_session(
                session, 
                input_price=args.input_price,
                cache_price=args.cache_price
            )
            
            # 3. Report
            print_audit_report(
                result, 
                args.log_path, 
                text_limit=args.text_limit
            )
            
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            import traceback
            print(f"An error occurred while analyzing the file: {e}", file=sys.stderr)
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
            print(f"An error occurred during benchmarking: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()
