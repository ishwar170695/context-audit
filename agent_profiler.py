import sys
import os
from context_audit.parsers import AntigravityParser, TraceLabClaudeParser
from context_audit.classifier import classify_raw_event
from context_audit.analyzer import BehaviorAnalyzer

def profile_session(transcript_path: str):
    # Very rudimentary heuristic to pick parser:
    if "trace.json" in transcript_path:
        parser = TraceLabClaudeParser(transcript_path)
    else:
        parser = AntigravityParser(transcript_path)
        
    raw_events = parser.parse()
    
    semantic_events = []
    unknown_count = 0
    mapped_count = 0
    skipped_count = 0
    total_confidence = 0.0
    
    for raw in raw_events:
        events = classify_raw_event(raw)
        if not events:
            skipped_count += 1
            continue
            
        semantic_events.extend(events)
        for e in events:
            if e.category == "UNKNOWN":
                unknown_count += 1
            else:
                mapped_count += 1
            total_confidence += e.confidence

    analyzer = BehaviorAnalyzer(semantic_events)
    metrics = analyzer.analyze()

    avg_confidence = (total_confidence / len(semantic_events)) if semantic_events else 0.0

    print("Agent Behavior Benchmark")
    print("========================")
    print(f"Parser Confidence: {avg_confidence*100:.1f}%")
    print(f"Mapped events:     {mapped_count}")
    print(f"Unknown commands:  {unknown_count}")
    print(f"Skipped events:    {skipped_count}")
    print("\nMetrics")
    print("-------")
    
    if not metrics:
        print("No valid metrics found.")
        return
        
    print(f"Unique files read: {metrics.get('unique_files_read', 0)}")
    print(f"Total reads:       {metrics.get('total_reads', 0)}")
    print(f"Rediscovery ratio: {metrics.get('rediscovery_ratio', 0):.2f}x")
    print(f"Session median gap:{metrics.get('session_median_gap', 0):.1f} actions")
    print(f"Recovery threshold:{metrics.get('recovery_threshold_used', 0):.1f} actions")
    print(f"Recovery reads:    {metrics.get('total_recovery_reads', 0)}")
    print(f"Navigation loops:  {metrics.get('navigation_loops', 0)}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python agent_profiler.py <path_to_transcript_or_trace>")
        sys.exit(1)
    profile_session(sys.argv[1])
