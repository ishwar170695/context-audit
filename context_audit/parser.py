import json
import os
from typing import Dict, List, Any, Optional

class Session:
    def __init__(self, system_instructions: str = "", tools: List[Dict[str, Any]] = None, history: List[Dict[str, Any]] = None):
        self.system_instructions = system_instructions or ""
        self.tools = tools or []
        self.history = history or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_instructions": self.system_instructions,
            "tools": self.tools,
            "history": self.history
        }

def parse_session_json(file_path: str) -> Session:
    """Parses a consolidated session.json file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return Session(
        system_instructions=data.get("system_instructions", ""),
        tools=data.get("tools", []),
        history=data.get("history", [])
    )

def parse_transcript_jsonl(file_path: str) -> Session:
    """Parses a line-delimited transcript.jsonl file from the IDE."""
    history = []
    
    system_instructions = (
        "You are Antigravity, a powerful agentic AI coding assistant designed by the Google DeepMind team...\n"
        "[System Prompt placeholders including Guidelines, Planning Mode, and Tool Declarations]"
    )
    
    observed_tools = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                step = json.loads(line)
                source = step.get("source")
                step_type = step.get("type")
                content = step.get("content", "")
                
                # Check for tool calls
                tool_calls = step.get("tool_calls", [])
                for tc in tool_calls:
                    name = tc.get("name")
                    if name:
                        observed_tools.add(name)
                
                # Map steps to history turns
                if step_type == "USER_INPUT":
                    history.append({
                        "role": "user",
                        "content": content,
                        "step_index": step.get("step_index")
                    })
                elif step_type == "PLANNER_RESPONSE":
                    msg = {
                        "role": "model",
                        "content": step.get("thinking", ""),
                        "step_index": step.get("step_index")
                    }
                    if tool_calls:
                        msg["tool_calls"] = tool_calls
                    history.append(msg)
                elif step_type in ["LIST_DIRECTORY", "VIEW_FILE", "GENERIC", "RUN_COMMAND", "REPLACE_FILE_CONTENT", "WRITE_TO_FILE"] or (source == "SYSTEM" and content):
                    # Tool response
                    history.append({
                        "role": "tool",
                        "name": (step_type or "system").lower(), # Approximate tool name
                        "content": content,
                        "step_index": step.get("step_index")
                    })
            except Exception as e:
                # Silently skip bad lines
                continue
                
    # Reconstruct some typical tool definitions based on what we observed
    tools = []
    for tool_name in observed_tools:
        # Mocking schemas for observed tools to make token estimation realistic
        tools.append({
            "name": tool_name,
            "description": f"Mock schema for tool: {tool_name} to simulate schema tokens in context audit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {"type": "string", "description": "Arguments details."}
                }
            }
        })
        
    return Session(
        system_instructions=system_instructions,
        tools=tools,
        history=history
    )

def load_session(file_path: str) -> Session:
    """Loads a session from a file, automatically detecting the format."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    _, ext = os.path.splitext(file_path)
    if ext.lower() == '.jsonl':
        return parse_transcript_jsonl(file_path)
    elif ext.lower() == '.json':
        # Let's peek inside to see if it's jsonl with .json extension or true json
        with open(file_path, 'r', encoding='utf-8') as f:
            first_char = f.read(1)
        if first_char != '{':
            # Might be jsonl
            return parse_transcript_jsonl(file_path)
        return parse_session_json(file_path)
    else:
        # Try JSON first, fallback to JSONL
        try:
            return parse_session_json(file_path)
        except Exception:
            return parse_transcript_jsonl(file_path)

def find_transcript_files(directory_path: str) -> List[str]:
    """Finds all transcript.jsonl and similar session files recursively under directory_path."""
    files = []
    if not os.path.isdir(directory_path):
        return files
        
    for root, _, filenames in os.walk(directory_path):
        for filename in filenames:
            # Match transcript.jsonl or files ending in .jsonl containing 'transcript'
            if filename == 'transcript.jsonl' or (filename.endswith('.jsonl') and 'transcript' in filename.lower()):
                files.append(os.path.join(root, filename))
            # Match session.json or files ending in .json containing 'session'
            elif filename == 'session.json' or (filename.endswith('.json') and 'session' in filename.lower()):
                files.append(os.path.join(root, filename))
    return files
