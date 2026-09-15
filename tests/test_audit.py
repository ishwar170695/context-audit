import os
import pytest
from context_audit.parser import load_session, find_transcript_files
from context_audit.analyzer import analyze_session, get_token_count, run_benchmark

def test_token_counting():
    # Test token counting with simple string
    text = "Hello World"
    tokens = get_token_count(text)
    assert tokens > 0
    
    empty = get_token_count("")
    assert empty == 0

def test_parse_and_analyze_session():
    # Locate test data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_path = os.path.join(current_dir, "..", "sample_data", "sample_session.json")
    
    assert os.path.exists(sample_path)
    
    # Load
    session = load_session(sample_path)
    assert len(session.tools) == 3
    assert len(session.history) == 8
    assert "guidelines" in session.system_instructions.lower()
    
    # Analyze
    result = analyze_session(session)
    
    # Verify results
    assert result.total_tokens_across_session > 0
    assert result.peak_context_size > 0
    assert result.final_context_size > 0
    assert len(result.timeline) == 4 # 4 model messages
    assert len(result.repeated_blocks) > 0
    
    # Cost metrics verification
    assert result.standard_input_cost > 0.0
    assert result.cached_input_cost > 0.0
    assert result.potential_cache_savings >= 0.0
    assert 0.0 <= result.cache_savings_percentage <= 100.0
    
    # Verify categories in breakdown
    for cat in ["System Prompt", "Tool Schemas", "Chat History", "Retrieved Content"]:
        assert cat in result.category_breakdown
        assert result.category_breakdown[cat] >= 0

def test_parse_and_analyze_transcript():
    # Locate test data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_path = os.path.join(current_dir, "..", "sample_data", "sample_transcript.jsonl")
    
    assert os.path.exists(sample_path)
    
    # Load
    session = load_session(sample_path)
    assert len(session.history) > 0
    
    # Analyze
    result = analyze_session(session)
    assert result.total_tokens_across_session > 0
    assert result.peak_context_size > 0
    assert result.final_context_size > 0
    assert len(result.timeline) > 0
    assert result.standard_input_cost > 0.0
    assert result.cached_input_cost > 0.0

def test_directory_scanning_and_benchmarking():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.abspath(os.path.join(current_dir, "..", "sample_data"))
    
    # Verify file finder
    files = find_transcript_files(sample_dir)
    assert len(files) >= 2 # should find sample_session.json and sample_transcript.jsonl
    
    # Run benchmark
    summary = run_benchmark(sample_dir)
    assert summary.total_sessions >= 2
    
    # Verify aggregated arrays
    assert len(summary.cumulative_tokens) == summary.total_sessions
    assert len(summary.peak_context_sizes) == summary.total_sessions
    assert len(summary.final_context_sizes) == summary.total_sessions
    assert len(summary.reuse_ratios) == summary.total_sessions
    
    # Verify Cost aggregated lists
    assert len(summary.standard_costs) == summary.total_sessions
    assert len(summary.cached_costs) == summary.total_sessions
    assert len(summary.savings_list) == summary.total_sessions
    
    # Verify repeated blocks list
    assert len(summary.repeated_blocks) > 0
    first_block = summary.repeated_blocks[0]
    assert "total_repeated" in first_block
    assert "sessions_count" in first_block
    assert "total_repeated_cost_usd" in first_block
    
    # Verify buckets are populated
    found_populated_bucket = False
    for b_name, b_data in summary.buckets.items():
        if b_data["count"] > 0:
            found_populated_bucket = True
            assert len(b_data["reuse_ratios"]) == b_data["count"]
            assert len(b_data["peak_sizes"]) == b_data["count"]
            assert len(b_data["cumulative_tokens"]) == b_data["count"]
    assert found_populated_bucket

def test_math_breakdown_and_exports():
    import json
    from context_audit.reporter import export_json_report, export_markdown_report, print_audit_report
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_path = os.path.join(current_dir, "..", "sample_data", "sample_session.json")
    session = load_session(sample_path)
    result = analyze_session(session, input_price=4.00, cache_price=1.00)
    
    # Check math breakdown
    mb = result.math_breakdown
    assert mb["total_cumulative_tokens"] > 0
    assert mb["input_price_per_m"] == 4.00
    assert mb["cache_price_per_m"] == 1.00
    assert mb["effective_discount_rate_pct"] == 75.0 # (1 - 1/4) * 100
    assert mb["reused_tokens"] >= 0
    
    # Check JSON export
    json_str = export_json_report(result, "sample_session.json")
    parsed = json.loads(json_str)
    assert parsed["target"] == "sample_session.json"
    assert parsed["summary"]["cumulative_tokens"] == result.total_tokens_across_session
    assert parsed["summary"]["effective_discount_rate_pct"] == 75.0
    assert "math_breakdown" in parsed
    
    # Check Markdown export
    md_str = export_markdown_report(result, "sample_session.json", show_math=True, show_wasters=True)
    assert "# Context Audit Report" in md_str
    assert "75% prefix cache discount" in md_str
    assert "## Mathematical Verification" in md_str
    assert "## Top Repeated Context Blocks" in md_str
    
    # Check conservative default terminal report runs cleanly
    print_audit_report(result, "sample_session.json")

def test_format_display_path_disambiguation():
    from context_audit.reporter import format_display_path

    # 1. Antigravity path with UUID
    p1 = "C:/Users/test/.gemini/antigravity-ide/brain/7e05f9ce-4995-4152-9db9-44edbe2e42e9/.system_generated/logs/transcript.jsonl"
    p2 = "C:/Users/test/.gemini/antigravity-ide/brain/1c8491ef-d3bb-4f43-bdc4-8f5cc724d104/.system_generated/logs/transcript.jsonl"
    d1 = format_display_path(p1)
    d2 = format_display_path(p2)
    assert d1 != d2, f"Expected distinct paths, but got {d1} and {d2}"
    assert "7e05f9ce" in d1
    assert "1c8491ef" in d2
    assert len(d1) <= 55

    # 2. Claude Code project path
    claude_p = "C:/Users/test/.claude/projects/my-awesome-app/transcripts/session_1234.jsonl"
    d_claude = format_display_path(claude_p)
    assert "my-awesome-app" in d_claude
    assert "session_1234.jsonl" in d_claude
    assert len(d_claude) <= 55

    # 3. Codex session path
    codex_p = "C:/Users/test/.codex/sessions/run_2026_09_13/transcript.jsonl"
    d_codex = format_display_path(codex_p)
    assert "run_2026_09_13" in d_codex
    assert len(d_codex) <= 55

    # 4. Short path untouched
    short_p = "./logs/session.jsonl"
    assert format_display_path(short_p) == "./logs/session.jsonl"


def test_benchmark_weighted_vs_average_reuse():
    """Regression test: average of session reuse ratios != total reused / total cumulative.

    Session A: small session, high reuse (90%+)
      - System prompt + tools repeated across 5 turns with identical user messages
    Session B: large session, low reuse
      - Many unique large messages → minimal repetition but far more tokens

    If the benchmark incorrectly reports mean(reuse_ratios) as the only reuse metric,
    it will show ~50% for two sessions at 90% and 10%.
    But weighted = (reused_A + reused_B) / (cumulative_A + cumulative_B) which differs.
    """
    import json
    import tempfile
    import statistics as stats
    from context_audit.parser import Session

    # --- Session A: small, high reuse ---
    session_a = Session()
    session_a.system_instructions = "You are a helpful assistant. Follow all guidelines carefully."
    session_a.tools = [{"name": "read_file", "description": "Reads a file from disk"}]
    for i in range(5):
        session_a.history.append({"role": "user", "content": "What is the status of the project?"})
        session_a.history.append({"role": "model", "content": f"The project is on track. Turn {i+1}."})

    # --- Session B: large tokens, low reuse ---
    # Only 2 model turns but with very large unique content.
    # With just 2 turns, the only "reuse" is the system prompt repeated in turn 2.
    # This keeps reuse low while making total tokens much larger than Session A.
    session_b = Session()
    session_b.system_instructions = "Short."
    session_b.tools = []
    # Turn 1: huge unique user message + model response
    session_b.history.append({"role": "user", "content": "Query: " + ("a" * 8000)})
    session_b.history.append({"role": "model", "content": "Response: " + ("b" * 8000)})
    # Turn 2: different huge user message + model response
    session_b.history.append({"role": "user", "content": "Follow-up: " + ("c" * 8000)})
    session_b.history.append({"role": "model", "content": "Answer: " + ("d" * 8000)})

    result_a = analyze_session(session_a)
    result_b = analyze_session(session_b)

    # Verify per-session reuse ratios are very different
    assert result_a.context_reuse_ratio > 50.0, \
        f"Session A should have high reuse, got {result_a.context_reuse_ratio:.1f}%"
    assert result_b.context_reuse_ratio < result_a.context_reuse_ratio, \
        f"Session B reuse ({result_b.context_reuse_ratio:.1f}%) should be lower than A ({result_a.context_reuse_ratio:.1f}%)"

    # Verify at the math level
    reuse_ratios = [result_a.context_reuse_ratio, result_b.context_reuse_ratio]
    reused_tokens = [result_a.math_breakdown['reused_tokens'], result_b.math_breakdown['reused_tokens']]
    cumulative_tokens = [result_a.total_tokens_across_session, result_b.total_tokens_across_session]

    average_reuse = stats.mean(reuse_ratios)
    weighted_reuse = (sum(reused_tokens) / sum(cumulative_tokens) * 100) if sum(cumulative_tokens) > 0 else 0.0

    # THE KEY ASSERTION: average and weighted should differ
    assert abs(average_reuse - weighted_reuse) > 1.0, \
        f"Average ({average_reuse:.1f}%) and weighted ({weighted_reuse:.1f}%) reuse should differ meaningfully"

    # Weighted should be pulled toward the larger session's ratio
    assert weighted_reuse < average_reuse, \
        f"Weighted ({weighted_reuse:.1f}%) should be < average ({average_reuse:.1f}%) because larger session has lower reuse"

    # --- Test via actual run_benchmark ---
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = os.path.join(tmpdir, "session_a.json")
        path_b = os.path.join(tmpdir, "session_b.json")
        with open(path_a, 'w') as f:
            json.dump({"system_instructions": session_a.system_instructions,
                       "tools": session_a.tools, "history": session_a.history}, f)
        with open(path_b, 'w') as f:
            json.dump({"system_instructions": session_b.system_instructions,
                       "tools": session_b.tools, "history": session_b.history}, f)

        summary = run_benchmark(tmpdir)

        assert summary.total_sessions == 2

        # reused_tokens_list populated
        assert len(summary.reused_tokens_list) == 2
        assert all(isinstance(x, int) for x in summary.reused_tokens_list)

        # waste_per_session populated
        assert len(summary.waste_per_session) == 2

        # worst_session identified by waste USD (not by tokens)
        assert summary.worst_session is not None
        max_waste = max(summary.waste_per_session)
        assert abs(summary.worst_session['waste_usd'] - max_waste) < 0.001, \
            f"Worst session waste ({summary.worst_session['waste_usd']}) should match max ({max_waste})"

        # Histogram buckets sum to total sessions
        low = sum(1 for w in summary.waste_per_session if w < 0.10)
        med = sum(1 for w in summary.waste_per_session if 0.10 <= w < 1.00)
        high = sum(1 for w in summary.waste_per_session if w >= 1.00)
        assert low + med + high == summary.total_sessions

        # Weighted reuse from benchmark data matches direct calculation
        total_reused_bm = sum(summary.reused_tokens_list)
        total_cum_bm = sum(summary.cumulative_tokens)
        weighted_bm = (total_reused_bm / total_cum_bm * 100) if total_cum_bm > 0 else 0.0
        avg_bm = stats.mean(summary.reuse_ratios)
        assert abs(avg_bm - weighted_bm) > 1.0, \
            f"Benchmark avg ({avg_bm:.1f}%) and weighted ({weighted_bm:.1f}%) should differ"
