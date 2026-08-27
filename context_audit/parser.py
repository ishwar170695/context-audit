import json
import os
from pathlib import Path
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
    """Parses a consolidated session.json file or JSON message array."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        # Raw array of messages
        return Session(
            system_instructions="You are an AI coding assistant.",
            tools=[],
            history=data
        )
    
    return Session(
        system_instructions=data.get("system_instructions", ""),
        tools=data.get("tools", []),
        history=data.get("history", [])
    )

def parse_transcript_jsonl(file_path: str) -> Session:
    """Parses a line-delimited transcript.jsonl / Claude / Cursor log file."""
    history = []
    
    system_instructions = (
        "You are an agentic AI coding assistant.\n"
        "[System Prompt placeholders including Guidelines, Planning Mode, and Tool Declarations]"
    )
    
    observed_tools = set()
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except Exception:
                continue
            
            if not isinstance(step, dict):
                continue

            # 1. Antigravity IDE schema
            step_type = step.get("type", "")
            source = step.get("source", "")
            content = step.get("content", "")
            tool_calls = step.get("tool_calls", []) or []
            
            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else str(tc)
                if name:
                    observed_tools.add(name)

            if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
                history.append({
                    "role": "user",
                    "content": str(content) if content is not None else "",
                    "step_index": step.get("step_index", line_num)
                })
            elif step_type == "PLANNER_RESPONSE" or (source == "MODEL" and "thinking" in step):
                msg = {
                    "role": "model",
                    "content": str(step.get("thinking", content or "")),
                    "step_index": step.get("step_index", line_num)
                }
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                history.append(msg)
            elif step_type in ["LIST_DIRECTORY", "VIEW_FILE", "GENERIC", "RUN_COMMAND", "REPLACE_FILE_CONTENT", "WRITE_TO_FILE"] or (source == "SYSTEM" and content):
                history.append({
                    "role": "tool",
                    "name": (step_type or "system").lower(),
                    "content": str(content),
                    "step_index": step.get("step_index", line_num)
                })
            # 2. Claude Code Schema
            elif step_type in ["user", "assistant", "tool_result"] or "message" in step:
                msg_obj = step.get("message", step)
                role = msg_obj.get("role", step_type)
                msg_content = msg_obj.get("content", "")
                
                if isinstance(msg_content, list):
                    text_parts = []
                    extracted_tools = []
                    for block in msg_content:
                        if isinstance(block, dict):
                            b_type = block.get("type")
                            if b_type == "text":
                                text_parts.append(block.get("text", ""))
                            elif b_type == "tool_use":
                                t_name = block.get("name", "tool")
                                observed_tools.add(t_name)
                                extracted_tools.append({"name": t_name, "args": block.get("input", {})})
                            elif b_type == "tool_result":
                                text_parts.append(str(block.get("content", "")))
                        else:
                            text_parts.append(str(block))
                    
                    final_role = "model" if role == "assistant" else ("user" if role == "user" else "tool")
                    item = {
                        "role": final_role,
                        "content": "\n".join(text_parts),
                        "step_index": line_num
                    }
                    if extracted_tools:
                        item["tool_calls"] = extracted_tools
                    history.append(item)
                else:
                    final_role = "model" if role == "assistant" else ("user" if role == "user" else "tool")
                    history.append({
                        "role": final_role,
                        "content": str(msg_content),
                        "step_index": line_num
                    })
            # 3. Generic Role-Based Schema
            elif "role" in step and ("content" in step or "text" in step):
                r = step.get("role", "user")
                final_role = "model" if r in ["assistant", "model"] else ("tool" if r == "tool" else "user")
                history.append({
                    "role": final_role,
                    "content": str(step.get("content", step.get("text", ""))),
                    "step_index": line_num
                })

    # Reconstruct tool definitions based on observed tools
    tools = []
    for tool_name in observed_tools:
        tools.append({
            "name": tool_name,
            "description": f"Tool schema for {tool_name}",
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
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                first_char = f.read(1).strip()
            if first_char not in ['{', '[']:
                return parse_transcript_jsonl(file_path)
            return parse_session_json(file_path)
        except Exception:
            return parse_transcript_jsonl(file_path)
    else:
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
            fname_lower = filename.lower()
            if fname_lower.endswith('_full.jsonl') or fname_lower.endswith('.full.jsonl'):
                continue
            if fname_lower.endswith('.jsonl') or fname_lower == 'transcript.jsonl':
                files.append(os.path.join(root, filename))
            elif fname_lower == 'session.json' or (fname_lower.endswith('.json') and 'session' in fname_lower):
                files.append(os.path.join(root, filename))
    return files

def discover_session_logs(limit: Optional[int] = 20) -> List[str]:
    """Auto-discovers local session logs across standard tools and current workspace, returning the newest first."""
    discovered = []
    home = Path.home()
    
    candidate_dirs = [
        Path(".").resolve(),  # Current workspace / dir
        home / ".claude" / "projects",
        home / ".claude" / "transcripts",
        home / ".claude",
        home / ".cursor",
        home / ".gemini" / "antigravity-ide" / "brain",
        home / ".aider"
    ]
    
    seen = set()
    for c_dir in candidate_dirs:
        if c_dir.exists() and c_dir.is_dir():
            found = find_transcript_files(str(c_dir))
            for f in found:
                abs_f = os.path.abspath(f)
                if abs_f not in seen:
                    seen.add(abs_f)
                    discovered.append(abs_f)
                    
    # Sort newest first by last modified time
    discovered.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
    
    if limit is not None and limit > 0:
        return discovered[:limit]
    return discovered

