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
            assert len(b_data["savings"]) == b_data["count"]
            
    assert found_populated_bucket
