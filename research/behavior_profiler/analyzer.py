import statistics
from collections import defaultdict
from typing import Dict, List, Any
from research.behavior_profiler.events import SemanticEvent

class BehaviorAnalyzer:
    def __init__(self, events: List[SemanticEvent]):
        self.events = events
        
    def analyze(self) -> Dict[str, Any]:
        if not self.events:
            return {}

        file_reads = defaultdict(list)
        
        for event in self.events:
            if event.method == "READ" and event.category == "RESOURCE_ACCESSED":
                file_reads[event.resource].append(event.index)
                
        unique_files_read = len(file_reads)
        total_reads = sum(len(reads) for reads in file_reads.values())
        rediscovery_ratio = total_reads / max(1, unique_files_read)

        all_gaps = []
        for reads in file_reads.values():
            if len(reads) > 1:
                for i in range(1, len(reads)):
                    all_gaps.append(reads[i] - reads[i-1])

        session_median_gap = statistics.median(all_gaps) if all_gaps else 0
        recovery_threshold = max(5, session_median_gap * 2)

        total_recovery_reads = 0
        for reads in file_reads.values():
            if len(reads) > 1:
                for i in range(1, len(reads)):
                    if (reads[i] - reads[i-1]) > recovery_threshold:
                        total_recovery_reads += 1

        navigation_loops = 0
        for i, event in enumerate(self.events):
            if event.method == "READ" and i >= 3:
                prev1 = self.events[i-1]
                prev2 = self.events[i-2]
                prev3 = self.events[i-3]
                if prev1.method == "SEARCH" and prev2.method == "READ" and prev3.method == "SEARCH":
                    navigation_loops += 1
            if event.method == "LIST" and i >= 1:
                if self.events[i-1].method == "LIST":
                    navigation_loops += 1

        return {
            "unique_files_read": unique_files_read,
            "total_reads": total_reads,
            "rediscovery_ratio": rediscovery_ratio,
            "session_median_gap": session_median_gap,
            "recovery_threshold_used": recovery_threshold,
            "total_recovery_reads": total_recovery_reads,
            "navigation_loops": navigation_loops,
            "total_events": len(self.events)
        }
