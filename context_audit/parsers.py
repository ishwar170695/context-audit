import json
import re
from typing import List
from context_audit.events import RawEvent

class AntigravityParser:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse(self) -> List[RawEvent]:
        events = []
        action_index = 0
        with open(self.filepath, 'r', encoding='utf-8') as f:
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
                        
                        target = ""
                        if name in ["view_file", "read_file"]:
                            target = args.get("AbsolutePath", args.get("FilePath", ""))
                        elif name in ["replace_file_content", "multi_replace_file_content", "write_to_file"]:
                            target = args.get("TargetFile", args.get("AbsolutePath", args.get("FilePath", "")))
                        elif name == "grep_search":
                            target = args.get("Query", "")
                        elif name == "list_dir":
                            target = args.get("DirectoryPath", "")
                        elif name == "run_command":
                            target = args.get("CommandLine", "")
                        
                        events.append(RawEvent(action_index, name, target))
        return events

class TraceLabClaudeParser:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse(self) -> List[RawEvent]:
        events = []
        action_index = 0
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Split by the record separators
        parts = re.split(r'===== record \d+ =====', content)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                data = json.loads(part)
            except json.JSONDecodeError:
                continue
                
            # Look for assistant tool uses
            if data.get("type") == "assistant" and "message" in data:
                msg = data["message"]
                if msg.get("role") == "assistant" and "content" in msg:
                    for block in msg["content"]:
                        if block.get("type") == "tool_use":
                            name = block.get("name")
                            target = ""
                            if name == "Bash" and "input" in block:
                                target = block["input"].get("command", "")
                            elif name in ["str_replace_editor", "GlobTool", "FileReadTool"]: # Examples of other tools some Claude agents use
                                target = str(block.get("input", ""))
                                
                            action_index += 1
                            events.append(RawEvent(action_index, name, target))
        return events
