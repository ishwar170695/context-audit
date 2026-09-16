import argparse
import os
import sys
import platform
from pathlib import Path
from rich.table import Table
from rich.panel import Panel

from context_audit import __version__
from context_audit.parser import load_session, discover_session_logs, session_fs_path
from context_audit.analyzer import analyze_session, run_benchmark
from context_audit.reporter import (
    print_audit_report, 
    print_benchmark_report, 
    console, 
    safe_char,
    format_display_path,
    print_math_breakdown,
    export_json_report,
    export_markdown_report
)
from context_audit.detectors import run_discovery

CHECK_MARK = safe_char("✓", "+")
CROSS_MARK = safe_char("✗", "-")

EMBEDDED_DEMO_TRANSCRIPT = """{"step_index":0,"source":"USER_EXPLICIT","type":"USER_INPUT","status":"DONE","created_at":"2026-06-19T03:30:00Z","content":"Explain how main.py works and check the directory."}
{"step_index":1,"source":"SYSTEM","type":"CONVERSATION_HISTORY","status":"DONE","created_at":"2026-06-19T03:30:01Z"}
{"step_index":2,"source":"MODEL","type":"PLANNER_RESPONSE","status":"DONE","created_at":"2026-06-19T03:30:05Z","thinking":"I should list the workspace directory first.","tool_calls":[{"name":"list_dir","args":{"DirectoryPath":"d:\\\\workspace\\\\demo"}}]}
{"step_index":3,"source":"MODEL","type":"LIST_DIRECTORY","status":"DONE","created_at":"2026-06-19T03:30:06Z","content":"{\\"name\\":\\"main.py\\",\\"sizeBytes\\":87}\\n{\\"name\\":\\"pyproject.toml\\",\\"sizeBytes\\":320}"}
{"step_index":4,"source":"MODEL","type":"PLANNER_RESPONSE","status":"DONE","created_at":"2026-06-19T03:30:10Z","thinking":"Now I'll view main.py to understand it.","tool_calls":[{"name":"view_file","args":{"AbsolutePath":"d:\\\\workspace\\\\demo\\\\main.py"}}]}
{"step_index":5,"source":"MODEL","type":"VIEW_FILE","status":"DONE","created_at":"2026-06-19T03:30:11Z","content":"def main():\\n    print('Hello World')\\n\\nif __name__ == '__main__':\\n    main()"}
{"step_index":6,"source":"MODEL","type":"PLANNER_RESPONSE","status":"DONE","created_at":"2026-06-19T03:30:15Z","thinking":"Now I will explain it to the user.","tool_calls":[]}
"""

def main():
    # If called with no arguments, run zero-config auto-discovery
    if len(sys.argv) == 1:
        run_auto_discover()
        return

    # If first argument is a file or dir that exists and not a recognized command, default to 'run <file>' or 'benchmark <dir>'
    recognized_commands = ["run", "benchmark", "doctor", "demo", "receipt", "-h", "--help", "-v", "--version"]
    if len(sys.argv) == 2 and sys.argv[1] not in recognized_commands:
        if os.path.isfile(sys.argv[1]) or os.path.isfile(session_fs_path(sys.argv[1])):
            sys.argv.insert(1, "run")
        elif os.path.isdir(sys.argv[1]):
            sys.argv.insert(1, "benchmark")

    parser = argparse.ArgumentParser(
        description="context-audit: 85-99% of your coding agent bill is invisible input tokens. See what's actually in your context window in 10 seconds."
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"context-audit v{__version__}"
    )
    
    # Root arguments (applied when run with no subcommand, auditing the latest session)
    parser.add_argument("--text-limit", type=int, default=40, help="Character limit for repeated text snippets.")
    parser.add_argument("--input-price", type=float, default=3.00, help="LLM input token price per million (USD). Default: 3.00.")
    parser.add_argument("--cache-price", type=float, default=0.30, help="LLM cache read token price per million (USD). Default: 0.30.")
    parser.add_argument("--context-limit", type=int, default=100000, help="LLM maximum context window size (default: 100000).")
    parser.add_argument("--entropy-threshold", type=float, default=2.0, help="Z-score threshold for tool output entropy anomaly detection (default: 2.0).")
    parser.add_argument("--wasters", action="store_true", help="Display top repeated context blocks and largest context consumers.")
    parser.add_argument("--composition", action="store_true", help="Display context window pressure and composition visual map.")
    parser.add_argument("--show-math", action="store_true", help="Display step-by-step arithmetic verification of metrics and pricing.")
    parser.add_argument("--full", action="store_true", help="Display comprehensive report including all tables, timeline, and anomaly alerts.")
    parser.add_argument("--json", action="store_true", help="Output audit results as machine-readable JSON.")
    parser.add_argument("--markdown", action="store_true", help="Output audit results as GitHub-flavored Markdown.")
    parser.add_argument("--share", action="store_true", help="Print a shareable one-line summary quote.")
    parser.add_argument("--session", type=str, default=None, help="Cursor session/composer ID or index when auditing SQLite state.vscdb.")

    subparsers = parser.add_subparsers(dest="command", required=False)

    # run command
    run_parser = subparsers.add_parser("run", help="Audit token usage and cost for a single log file.")
    run_parser.add_argument("log_path", type=str, help="Path to the session.json or transcript.jsonl log file.")
    run_parser.add_argument("--text-limit", type=int, default=40, help="Character limit for repeated text snippets.")
    run_parser.add_argument("--input-price", type=float, default=3.00, help="LLM input price per million. Default: 3.00.")
    run_parser.add_argument("--cache-price", type=float, default=0.30, help="LLM cache price per million. Default: 0.30.")
    run_parser.add_argument("--context-limit", type=int, default=100000, help="Context limit (default: 100000).")
    run_parser.add_argument("--entropy-threshold", type=float, default=2.0, help="Entropy threshold (default: 2.0).")
    run_parser.add_argument("--wasters", action="store_true", help="Display top repeated context blocks.")
    run_parser.add_argument("--composition", action="store_true", help="Display composition visual map.")
    run_parser.add_argument("--show-math", action="store_true", help="Display arithmetic verification.")
    run_parser.add_argument("--full", action="store_true", help="Display comprehensive report.")
    run_parser.add_argument("--json", action="store_true", help="Output audit results as JSON.")
    run_parser.add_argument("--markdown", action="store_true", help="Output audit results as Markdown.")
    run_parser.add_argument("--share", action="store_true", help="Print shareable one-line quote.")
    run_parser.add_argument("--session", type=str, default=None, help="Cursor session/composer ID or index when auditing SQLite state.vscdb.")

    # benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Benchmark and aggregate token usage/costs across multiple sessions recursively.")
    bench_parser.add_argument(
        "directory_path", type=str, nargs="?", default=None, help="Directory containing session logs (default: auto-discover all local sessions)."
    )
    bench_parser.add_argument("--top-n", type=int, default=5, help="Number of top repeated artifacts to show.")
    bench_parser.add_argument("--text-limit", type=int, default=40, help="Character limit for repeated text snippets.")
    bench_parser.add_argument("--input-price", type=float, default=3.00, help="LLM input price per million. Default: 3.00.")
    bench_parser.add_argument("--cache-price", type=float, default=0.30, help="LLM cache price per million. Default: 0.30.")
    bench_parser.add_argument("--wasters", action="store_true", help="Display top repeated artifacts table.")
    bench_parser.add_argument("--scaling", action="store_true", help="Display context size scaling table.")
    bench_parser.add_argument("--full", action="store_true", help="Display full benchmark breakdown.")
    bench_parser.add_argument("--share", action="store_true", help="Print shareable one-line quote.")

    # doctor command
    subparsers.add_parser("doctor", help="Diagnose local environment, agent detection, and session log discoverability.")

    # demo command
    demo_parser = subparsers.add_parser("demo", help="Run an educational audit on a sample session transcript (product education).")
    demo_parser.add_argument("--text-limit", type=int, default=40, help="Character limit for repeated text snippets.")
    demo_parser.add_argument("--input-price", type=float, default=3.00, help="LLM input price per million. Default: 3.00.")
    demo_parser.add_argument("--cache-price", type=float, default=0.30, help="LLM cache price per million. Default: 0.30.")
    demo_parser.add_argument("--context-limit", type=int, default=100000, help="Context limit (default: 100000).")
    demo_parser.add_argument("--entropy-threshold", type=float, default=2.0, help="Entropy threshold (default: 2.0).")
    demo_parser.add_argument("--wasters", action="store_true", help="Display top repeated context blocks.")
    demo_parser.add_argument("--composition", action="store_true", help="Display composition visual map.")
    demo_parser.add_argument("--show-math", action="store_true", help="Display arithmetic verification.")
    demo_parser.add_argument("--full", action="store_true", help="Display comprehensive report.")
    demo_parser.add_argument("--json", action="store_true", help="Output audit results as JSON.")
    demo_parser.add_argument("--markdown", action="store_true", help="Output audit results as Markdown.")
    demo_parser.add_argument("--share", action="store_true", help="Print shareable one-line quote.")

    # receipt command
    receipt_parser = subparsers.add_parser(
        "receipt", help="Detect local agents, select a session, and generate an instant browser receipt."
    )
    receipt_parser.add_argument(
        "--agent", type=str, default=None, help="Filter by agent name (claude, cursor, antigravity, etc.)."
    )
    receipt_parser.add_argument(
        "--latest", action="store_true", help="Audit the newest session immediately without prompting."
    )
    receipt_parser.add_argument(
        "--no-open", action="store_true", help="Do not open the receipt in a browser."
    )
    receipt_parser.add_argument(
        "--input-price", type=float, default=3.00, help="LLM input price per million. Default: 3.00."
    )
    receipt_parser.add_argument(
        "--cache-price", type=float, default=0.30, help="LLM cache price per million. Default: 0.30."
    )

    args = parser.parse_args()

    if args.command is None:
        run_auto_discover(args)
        return

    if args.command == "doctor":
        run_doctor()
    elif args.command == "demo":
        run_demo(args)
    elif args.command == "receipt":
        run_receipt_flow(args)
    elif args.command == "run":
        try:
            # 1. Parse log
            session = load_session(args.log_path, session_id=getattr(args, "session", None))
            
            # 2. Analyze
            result = analyze_session(
                session, 
                input_price=args.input_price,
                cache_price=args.cache_price,
                context_limit=args.context_limit,
                entropy_threshold=args.entropy_threshold
            )
            
            # 3. Report or Export
            if getattr(args, "json", False):
                print(export_json_report(result, args.log_path))
                return
            if getattr(args, "markdown", False):
                print(export_markdown_report(
                    result, 
                    args.log_path,
                    show_wasters=getattr(args, "wasters", False),
                    show_composition=getattr(args, "composition", False),
                    show_full=getattr(args, "full", False),
                    show_math=getattr(args, "show_math", False)
                ))
                return
            
            print_audit_report(
                result, 
                args.log_path, 
                text_limit=args.text_limit,
                show_wasters=getattr(args, "wasters", False),
                show_composition=getattr(args, "composition", False),
                show_full=getattr(args, "full", False),
                show_math=getattr(args, "show_math", False),
                show_share=getattr(args, "share", False)
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
            target_path = args.directory_path
            if not target_path:
                report = run_discovery()
                target_path = report.all_sessions
                if not target_path:
                    console.print("[bold yellow]No local agent sessions discovered to benchmark.[/bold yellow]")
                    return
                dir_label = f"Auto-Discovered ({len(target_path)} sessions)"
            else:
                dir_label = target_path

            # 1. Run benchmark analysis
            summary = run_benchmark(
                target_path,
                input_price=args.input_price,
                cache_price=args.cache_price
            )
            
            # 2. Report benchmark results
            print_benchmark_report(
                summary,
                directory_path=dir_label,
                top_n=args.top_n,
                text_limit=args.text_limit,
                show_wasters=getattr(args, "wasters", False),
                show_scaling=getattr(args, "scaling", False),
                show_full=getattr(args, "full", False),
                show_share=getattr(args, "share", False)
            )
        except Exception as e:
            import traceback
            console.print(f"[bold red]An error occurred during benchmarking:[/bold red] {e}")
            traceback.print_exc()
            sys.exit(1)

def run_doctor():
    """Diagnoses local environment, agent detection, and session log discoverability."""
    report = run_discovery(limit=None)
    
    console.print("\n[bold cyan]context-audit doctor[/bold cyan]\n")
    
    # Environment Table
    env_table = Table(title="Environment", show_header=True, header_style="bold cyan")
    env_table.add_column("Property", style="dim", width=20)
    env_table.add_column("Value")
    
    env_table.add_row("OS", f"{platform.system()} ({platform.release()})")
    env_table.add_row("Python", sys.version.split()[0])
    env_table.add_row("Working Directory", os.getcwd())
    console.print(env_table)
    console.print()

    # Agent Discovery Table
    agent_table = Table(title="Agent Detection & Session Discovery", show_header=True, header_style="bold cyan")
    agent_table.add_column("Agent", style="bold")
    agent_table.add_column("Installed / Detected")
    agent_table.add_column("Discovery Status")
    agent_table.add_column("Log Format")

    for item in report.agent_reports:
        if item["installed"]:
            installed_str = f"[bold green]{CHECK_MARK} Detected[/bold green]"
        else:
            installed_str = f"[dim]{CROSS_MARK} Not detected[/dim]"
            
        sessions_count = len(item.get("sessions", []))
        if not item["installed"]:
            status_str = "[dim]not applicable[/dim]"
        elif not item["format_supported"]:
            status_str = f"[yellow]{item['support_note']}[/yellow]"
        elif sessions_count > 0:
            status_str = f"[bold green]{sessions_count} candidate(s)[/bold green]"
        else:
            status_str = "[yellow]0 candidates[/yellow]"
            
        agent_table.add_row(
            item["name"],
            installed_str,
            status_str,
            item["format_name"]
        )

    console.print(agent_table)
    console.print()

    # Diagnosis / Next Steps
    if report.has_sessions:
        console.print(Panel(
            f"[bold green]Ready:[/bold green] Found [bold]{len(report.all_sessions)}[/bold] auditable session(s).\n\n"
            f"Run zero-config audit:\n  [bold cyan]context-audit[/bold cyan]\n\n"
            f"Or audit a sample session for product education:\n  [bold cyan]context-audit demo[/bold cyan]",
            title="Result",
            border_style="green"
        ))
    else:
        detected_names = [r['name'] for r in report.detected_agents if r['name'] != 'Local Workspace']
        detected_summary = ", ".join(detected_names) if detected_names else "None"
        console.print(Panel(
            f"[bold yellow]No auditable sessions found.[/bold yellow]\n\n"
            f"Detected agents: [cyan]{detected_summary}[/cyan]\n\n"
            f"Options:\n"
            f"  1. [bold cyan]context-audit demo[/bold cyan]        - Explore context-audit on a sample session transcript\n"
            f"  2. [bold cyan]context-audit run <path>[/bold cyan]  - Audit a specific JSONL transcript or session.json file directly",
            title="Result",
            border_style="yellow"
        ))
    console.print()

def run_demo(args=None):
    """Runs an educational demo audit against a sample transcript."""
    base_dir = Path(__file__).resolve().parent.parent
    sample_file = base_dir / "sample_data" / "sample_transcript.jsonl"
    
    if not sample_file.exists():
        pkg_sample = Path(__file__).resolve().parent / "sample_transcript.jsonl"
        if pkg_sample.exists():
            sample_file = pkg_sample
    
    if not sample_file.exists():
        import tempfile
        sample_file = Path(tempfile.gettempdir()) / "context_audit_demo.jsonl"
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write(EMBEDDED_DEMO_TRANSCRIPT)

    is_export = getattr(args, "json", False) or getattr(args, "markdown", False)
    if not is_export:
        console.print()
        console.print(Panel(
            "[bold yellow]Demo audit — sample session[/bold yellow]\n"
            "[dim](Product education mode: analyzing sample developer session, not your local agent data)[/dim]",
            border_style="yellow"
        ))
        console.print()
    
    session = load_session(str(sample_file))
    
    input_price = getattr(args, "input_price", 3.00) if args else 3.00
    cache_price = getattr(args, "cache_price", 0.30) if args else 0.30
    context_limit = getattr(args, "context_limit", 100000) if args else 100000
    text_limit = getattr(args, "text_limit", 40) if args else 40
    entropy_threshold = getattr(args, "entropy_threshold", 2.0) if args else 2.0
    
    result = analyze_session(
        session,
        input_price=input_price,
        cache_price=cache_price,
        context_limit=context_limit,
        entropy_threshold=entropy_threshold
    )
    
    sample_label = "Demo Sample (sample_transcript.jsonl)"
    if getattr(args, "json", False):
        print(export_json_report(result, sample_label))
        return
    if getattr(args, "markdown", False):
        print(export_markdown_report(
            result, 
            sample_label,
            show_wasters=getattr(args, "wasters", False),
            show_composition=getattr(args, "composition", False),
            show_full=getattr(args, "full", False),
            show_math=getattr(args, "show_math", False)
        ))
        return

    print_audit_report(
        result, 
        sample_label, 
        text_limit=text_limit,
        show_wasters=getattr(args, "wasters", False),
        show_composition=getattr(args, "composition", False),
        show_full=getattr(args, "full", False),
        show_math=getattr(args, "show_math", False),
        show_share=getattr(args, "share", False)
    )

def format_time_ago(mtime: float) -> str:
    import time
    diff = max(0, int(time.time() - mtime))
    if diff < 60:
        return f"{diff}s ago"
    elif diff < 3600:
        return f"{diff // 60}m ago"
    elif diff < 86400:
        return f"{diff // 3600}h ago"
    else:
        return f"{diff // 86400}d ago"

def run_auto_discover(args=None):
    """Zero-config auto discovery: audits the most recent local session with single-session tiering."""
    is_export = getattr(args, "json", False) or getattr(args, "markdown", False)
    if not is_export:
        console.print("\n[bold cyan]Scanning for local Claude Code / Cursor / IDE agent session logs...[/bold cyan]")
    
    report = run_discovery()
    discovered_files = report.all_sessions
    
    if not discovered_files:
        console.print("\n[bold yellow]No compatible session found. (0 local logs discovered)[/bold yellow]\n")
        console.print("[bold]Searched locations:[/bold]")
        console.print("  • ~/.gemini/antigravity-ide/brain  (Antigravity IDE)")
        console.print("  • ~/.claude                      (Claude Code)")
        console.print("  • ~/.codex                       (Codex / OpenAI)")
        console.print("  • ./                             (Local workspace .jsonl / session.json)\n")
        console.print("[bold]Detected agents:[/bold]")
        for item in report.agent_reports:
            if item["name"] == "Local Workspace":
                continue
            if item["installed"]:
                mark = f"[bold green]{CHECK_MARK}[/bold green]"
                note = f"({item['status_summary']})"
            else:
                mark = f"[dim]{CROSS_MARK}[/dim]"
                note = "(not detected)"
            console.print(f"  {mark} {item['name']:<15} [dim]{note}[/dim]")
        
        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print("  1. Run [bold green]context-audit demo[/bold green] to explore an educational audit on realistic developer data.")
        console.print("  2. Run [bold green]context-audit doctor[/bold green] to inspect path diagnostics and format compatibility.")
        console.print("  3. Or audit a specific file directly: [bold green]context-audit run <path/to/transcript.jsonl>[/bold green]\n")
        return

    if not is_export:
        console.print(f"[green]Discovered {len(discovered_files)} agent session log(s). Analyzing...[/green]")

    from context_audit.parser import (
        session_ref_exists,
        session_ref_size,
        session_ref_mtime,
        format_display_ref
    )

    # Filter out empty files/sessions and sort by true session mtime descending (newest first)
    valid_sessions = [
        f for f in discovered_files
        if session_ref_exists(f) and session_ref_size(f) > 0
    ]
    if not valid_sessions:
        valid_sessions = discovered_files
    valid_sessions.sort(key=session_ref_mtime, reverse=True)

    target_path = None
    session = None
    for candidate in valid_sessions:
        try:
            cand_session = load_session(candidate)
            if cand_session and (cand_session.history or cand_session.system_instructions):
                target_path = candidate
                session = cand_session
                break
        except Exception:
            continue

    if not session or not target_path:
        target_path = valid_sessions[0]
        session = load_session(target_path)

    input_price = getattr(args, "input_price", 3.00) if args else 3.00
    cache_price = getattr(args, "cache_price", 0.30) if args else 0.30
    context_limit = getattr(args, "context_limit", 100000) if args else 100000
    text_limit = getattr(args, "text_limit", 40) if args else 40
    entropy_threshold = getattr(args, "entropy_threshold", 2.0) if args else 2.0

    result = analyze_session(
        session,
        input_price=input_price,
        cache_price=cache_price,
        context_limit=context_limit,
        entropy_threshold=entropy_threshold
    )

    if getattr(args, "json", False):
        print(export_json_report(result, target_path))
        return
    if getattr(args, "markdown", False):
        print(export_markdown_report(
            result,
            target_path,
            show_wasters=getattr(args, "wasters", False),
            show_composition=getattr(args, "composition", False),
            show_full=getattr(args, "full", False),
            show_math=getattr(args, "show_math", False)
        ))
        return

    print_audit_report(
        result,
        target_path,
        text_limit=text_limit,
        show_wasters=getattr(args, "wasters", False),
        show_composition=getattr(args, "composition", False),
        show_full=getattr(args, "full", False),
        show_math=getattr(args, "show_math", False),
        show_share=getattr(args, "share", False)
    )

    time_ago = format_time_ago(session_ref_mtime(target_path))
    display_name = format_display_ref(target_path)

    console.print(f"[dim]Audited most recent session: {display_name} (modified {time_ago}).[/dim]")
    if len(discovered_files) > 1:
        console.print(f"[dim]Found {len(discovered_files) - 1} other local sessions. To aggregate all sessions, run: [bold cyan]context-audit benchmark[/bold cyan][/dim]")
    console.print()

def run_receipt_flow(args=None):
    """Interactive zero-friction agent session detection and instant browser receipt generation."""
    import json
    import urllib.parse
    import webbrowser
    from context_audit.detectors import run_discovery
    from context_audit.parser import (
        load_session,
        session_ref_mtime,
        session_ref_size,
        session_ref_exists,
        format_display_ref
    )
    from context_audit.analyzer import analyze_session
    from context_audit.reporter import format_tokens

    console.print("\n[bold cyan]Scanning for installed coding agents & local session storage...[/bold cyan]")
    report = run_discovery(limit=250)

    # Collect sessions grouped by agent
    agent_sessions = {}
    for item in report.agent_reports:
        name = item["name"]
        sessions = [
            s for s in item.get("sessions", [])
            if session_ref_exists(s) and session_ref_size(s) > 0
        ]
        if sessions:
            agent_sessions[name] = sessions

    if not agent_sessions:
        console.print("\n[bold yellow]No auditable agent sessions discovered locally.[/bold yellow]\n")
        console.print("[bold]Searched locations:[/bold]")
        console.print("  • ~/.claude / projects           (Claude Code)")
        console.print("  • Cursor global/workspace SQLite (Cursor state.vscdb)")
        console.print("  • ~/.gemini/antigravity-ide      (Antigravity IDE)")
        console.print("  • ./                             (Local Workspace)\n")
        console.print("Run [bold green]context-audit demo[/bold green] to test on realistic sample data, or open [bold green]receipt.html[/bold green] in your browser.\n")
        return

    # 1. Agent Selection
    filter_agent = getattr(args, "agent", None) if args else None
    if filter_agent:
        matched = [k for k in agent_sessions if filter_agent.lower() in k.lower()]
        if matched:
            selected_agent = matched[0]
        else:
            console.print(f"[bold red]Unknown agent '{filter_agent}'. Detected agents: {', '.join(agent_sessions.keys())}[/bold red]")
            return
    elif getattr(args, "latest", False) or len(agent_sessions) == 1:
        selected_agent = list(agent_sessions.keys())[0]
        console.print(f"Found [bold green]{selected_agent}[/bold green] ({len(agent_sessions[selected_agent])} session(s)).")
    else:
        console.print("\n[bold]Found agents with sessions:[/bold]\n")
        agent_names = list(agent_sessions.keys())
        for idx, name in enumerate(agent_names, 1):
            sess_count = len(agent_sessions[name])
            console.print(f"  [{idx}] [bold]{name:<16}[/bold] ({sess_count} session{'s' if sess_count != 1 else ''})")
        
        console.print()
        try:
            choice = input(f"Select agent [1-{len(agent_names)}] (default 1): ").strip()
            if not choice:
                selected_agent = agent_names[0]
            else:
                idx = int(choice) - 1
                selected_agent = agent_names[idx] if 0 <= idx < len(agent_names) else agent_names[0]
        except (ValueError, IndexError):
            selected_agent = agent_names[0]

    sessions = agent_sessions[selected_agent]
    sessions.sort(key=session_ref_mtime, reverse=True)

    # 2. Session Selection
    if getattr(args, "latest", False) or len(sessions) == 1:
        target_session = sessions[0]
    else:
        console.print(f"\n[bold]Recent sessions for {selected_agent}:[/bold]\n")
        display_limit = min(8, len(sessions))
        for idx in range(display_limit):
            s_ref = sessions[idx]
            time_str = format_time_ago(session_ref_mtime(s_ref))
            disp_title = format_display_ref(s_ref, max_len=50)
            console.print(f"  [{idx + 1}] {time_str:<8}  {disp_title}")
        
        console.print()
        try:
            choice = input(f"Select session [1-{display_limit}] (default 1): ").strip()
            if not choice:
                target_session = sessions[0]
            else:
                idx = int(choice) - 1
                target_session = sessions[idx] if 0 <= idx < display_limit else sessions[0]
        except (ValueError, IndexError):
            target_session = sessions[0]

    console.print(f"\n[cyan]Auditing session...[/cyan]")
    try:
        session_obj = load_session(target_session)
    except Exception as e:
        console.print(f"[bold red]Failed to load session:[/bold red] {e}")
        return

    input_price = getattr(args, "input_price", 3.00) if args else 3.00
    cache_price = getattr(args, "cache_price", 0.30) if args else 0.30

    result = analyze_session(session_obj, input_price=input_price, cache_price=cache_price)

    tot_tok = result.total_tokens_across_session
    reuse_ratio = (result.context_reuse_ratio or 0.0) / 100.0
    rep_tok = int(tot_tok * reuse_ratio)
    novel_tok = max(0, tot_tok - rep_tok)

    tot_bill = result.standard_input_cost
    waste_cost = (rep_tok / 1_000_000.0) * input_price
    novel_cost = max(0.0, tot_bill - waste_cost)

    top_items = []
    if result.repeated_blocks:
        for b in result.repeated_blocks[:4]:
            top_items.append({
                "name": b["name"] if b.get("name") else (b["text"][:30] if b.get("text") else "context block"),
                "reads": f"{b['occurrences']}x",
                "cost": f"${b['repeated_cost_usd']:.2f}"
            })
    if not top_items and result.top_repeated_sources:
        for s in result.top_repeated_sources[:4]:
            top_items.append({
                "name": s["name"],
                "reads": f"{s.get('details', 'repeated')}",
                "cost": f"${s['cost_usd']:.2f}"
            })
    if not top_items:
        top_items.append({
            "name": "conversational context history",
            "reads": f"{len(session_obj.history)}x",
            "cost": f"${waste_cost:.2f}"
        })

    session_display = format_display_ref(target_session, max_len=40)
    shop_title = f"{selected_agent.upper()} RECEIPT"

    receipt_data = {
        "shopTitle": shop_title,
        "heroWaste": f"${waste_cost:.2f}",
        "heroSubtext": f"{reuse_ratio*100:.1f}% of your input was re-read context.",
        "totalBill": f"${tot_bill:.2f}",
        "novelCost": f"${novel_cost:.2f}",
        "reuseRatio": f"{reuse_ratio*100:.1f}%",
        "totalTokens": format_tokens(tot_tok),
        "repeatedTokens": format_tokens(rep_tok),
        "postStory": f"The model reread context throughout {len(session_obj.history)} turns.",
        "topItems": top_items,
        "sessionTitle": session_display
    }

    # Print Terminal Receipt
    border = "=" * 44
    console.print(f"\n[bold]{border}[/bold]")
    console.print(f"[bold]{shop_title.center(44)}[/bold]")
    console.print(f"[dim]{session_display.center(44)}[/dim]")
    console.print(f"[bold]{border}[/bold]")
    console.print(f"[bold red]YOU PAID:          ${waste_cost:.2f}[/bold red]")
    console.print(f"[bold red]FOR:               REPEATED CONTEXT[/bold red]")
    console.print(f"[dim]{reuse_ratio*100:.1f}% of your input was re-read context.[/dim]")
    console.print("-" * 44)
    console.print(f"Total Session Bill:  ${tot_bill:.2f}")
    console.print(f"Cost of Unique Code: ${novel_cost:.2f}")
    console.print(f"Total Input Tokens:  {format_tokens(tot_tok)}")
    console.print(f"Re-read Tokens:      {format_tokens(rep_tok)} ({reuse_ratio*100:.1f}%)")
    console.print("-" * 44)
    console.print("[bold]TOP RE-READS:[/bold]")
    for idx, item in enumerate(top_items, 1):
        console.print(f"  {idx}. {item['name'][:24]:<24} {item['reads']} ({item['cost']})")
    console.print(f"[bold]{border}[/bold]\n")

    # Launch in Browser
    if not getattr(args, "no_open", False):
        candidates = [
            Path(__file__).resolve().parent / "receipt_template.html",
            Path(__file__).resolve().parent.parent / "receipt.html",
            Path("receipt.html"),
        ]
        template_text = None
        for c in candidates:
            if c.exists():
                try:
                    template_text = c.read_text(encoding="utf-8")
                    break
                except Exception:
                    continue

        if template_text:
            audit_json_str = json.dumps(receipt_data, indent=2)
            if "window.AUDIT_DATA = null;" in template_text:
                injected_html = template_text.replace(
                    "window.AUDIT_DATA = null;",
                    f"window.AUDIT_DATA = {audit_json_str};"
                )
            else:
                injected_html = template_text.replace(
                    "<script>",
                    f"<script>\nwindow.AUDIT_DATA = {audit_json_str};\n",
                    1
                )

            out_file = Path.cwd() / "context_audit_receipt.html"
            try:
                out_file.write_text(injected_html, encoding="utf-8")
            except Exception:
                import tempfile
                out_file = Path(tempfile.gettempdir()) / "context_audit_receipt.html"
                out_file.write_text(injected_html, encoding="utf-8")

            file_url = out_file.resolve().as_uri()
            console.print(f"[bold green]Opening interactive receipt in browser ({out_file.name})...[/bold green]")
            try:
                webbrowser.open(file_url)
            except Exception:
                console.print(f"[dim]Open URL: {file_url}[/dim]")
        else:
            console.print("[dim]receipt.html not found. Terminal report printed above.[/dim]")

if __name__ == "__main__":
    main()
