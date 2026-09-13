import json
import os
from collections import defaultdict
import glob

def process_transcript(transcript_path):
    timeline = []
    action_index = 0
    
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if data.get("type") == "PLANNER_RESPONSE":
                    tool_calls = data.get("tool_calls", [])
                    if tool_calls is None:
                        continue
                    for tool in tool_calls:
                        name = tool.get("name")
                        args = tool.get("args", {})
                        action_index += 1
                        
                        if name in ["view_file", "read_file"]:
                            path = args.get("AbsolutePath") or args.get("FilePath")
                            if path:
                                timeline.append({"index": action_index, "type": "read", "target": path})
                        elif name in ["replace_file_content", "multi_replace_file_content", "write_to_file"]:
                            path = args.get("TargetFile") or args.get("AbsolutePath") or args.get("FilePath")
                            if path:
                                timeline.append({"index": action_index, "type": "edit", "target": path})
                        elif name == "grep_search":
                            query = args.get("Query", "")
                            timeline.append({"index": action_index, "type": "grep", "target": query})
                        elif name == "list_dir":
                            path = args.get("DirectoryPath", "")
                            timeline.append({"index": action_index, "type": "ls", "target": path})
                        elif name == "run_command":
                            cmd = args.get("CommandLine", "")
                            timeline.append({"index": action_index, "type": "cmd", "target": cmd})
                        else:
                            timeline.append({"index": action_index, "type": "other", "target": name})
    except Exception as e:
        return None

    if not timeline:
        return None

    # Analyze File Explorations
    file_reads = defaultdict(list)
    file_edits = defaultdict(list)
    
    for event in timeline:
        if event["type"] == "read":
            file_reads[event["target"]].append(event["index"])
        elif event["type"] == "edit":
            file_edits[event["target"]].append(event["index"])

    unique_files_read = len(file_reads)
    total_reads = sum(len(reads) for reads in file_reads.values())
    rediscovery_ratio = total_reads / max(1, unique_files_read)
    
    total_recovery_reads = 0
    for path, reads in file_reads.items():
        if len(reads) <= 1:
            continue
        for i in range(1, len(reads)):
            prev_read = reads[i-1]
            curr_read = reads[i]
            gap = curr_read - prev_read
            
            edits = file_edits.get(path, [])
            has_edit = any(prev_read < e < curr_read for e in edits)
            
            if not has_edit and gap > 20:
                total_recovery_reads += 1

    # Analyze Loops
    grep_read_loops = 0
    ls_loops = 0
    
    for i, event in enumerate(timeline):
        if event["type"] == "read" and i >= 3:
            prev1 = timeline[i-1]
            prev2 = timeline[i-2]
            prev3 = timeline[i-3]
            if prev1["type"] == "grep" and prev2["type"] == "read" and prev3["type"] == "grep":
                grep_read_loops += 1
                
        if event["type"] == "ls" and i >= 1:
            if timeline[i-1]["type"] == "ls":
                ls_loops += 1

    return {
        "unique_files_read": unique_files_read,
        "total_reads": total_reads,
        "rediscovery_ratio": rediscovery_ratio,
        "recovery_reads": total_recovery_reads,
        "grep_read_loops": grep_read_loops,
        "ls_loops": ls_loops,
        "total_actions": action_index
    }

def main():
    base_dir = r"C:\Users\ishu\.gemini\antigravity-ide\brain"
    pattern = os.path.join(base_dir, "*", ".system_generated", "logs", "transcript.jsonl")
    transcripts = glob.glob(pattern)
    
    print(f"Found {len(transcripts)} transcripts.")
    
    valid_sessions = 0
    high_rediscovery_count = 0
    total_recovery_reads = 0
    sessions_with_recovery = 0
    total_grep_loops = 0
    total_ls_loops = 0
    
    for t in transcripts:
        stats = process_transcript(t)
        if not stats or stats["total_actions"] < 5:
            continue
            
        valid_sessions += 1
        
        if stats["rediscovery_ratio"] > 2.0:
            high_rediscovery_count += 1
            
        total_recovery_reads += stats["recovery_reads"]
        if stats["recovery_reads"] > 0:
            sessions_with_recovery += 1
            
        total_grep_loops += stats["grep_read_loops"]
        total_ls_loops += stats["ls_loops"]

    print("\n--- AGGREGATE STATS ---")
    print(f"Analyzed {valid_sessions} valid sessions (>=5 actions).")
    if valid_sessions > 0:
        print(f"% with Rediscovery Ratio > 2.0: {high_rediscovery_count / valid_sessions * 100:.1f}% ({high_rediscovery_count})")
        print(f"Total Recovery Reads: {total_recovery_reads}")
        print(f"% with at least 1 Recovery Read: {sessions_with_recovery / valid_sessions * 100:.1f}% ({sessions_with_recovery})")
        print(f"Total Grep->Read Loops: {total_grep_loops}")
        print(f"Total ls->ls Loops: {total_ls_loops}")

if __name__ == "__main__":
    main()
