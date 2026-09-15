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

def split_session_ref(file_path: str) -> tuple:
    """Splits Cursor sub-session refs of the form path/to/state.vscdb#composer_id.

    Returns (filesystem_path, session_id). session_id is None when the path is a
    real file or has no valid #suffix.
    """
    if not file_path:
        return file_path, None
    if os.path.exists(file_path):
        return file_path, None
    if "#" not in file_path:
        return file_path, None
    base_path, sub_id = file_path.rsplit("#", 1)
    if sub_id and os.path.exists(base_path):
        return base_path, sub_id
    return file_path, None


def session_fs_path(file_path: str) -> str:
    """Filesystem path for exists/mtime/size checks, stripping a #session suffix."""
    return split_session_ref(file_path)[0]


def session_ref_exists(file_path: str) -> bool:
    """Returns True if the referenced session file or database exists."""
    fs_path, sub_id = split_session_ref(file_path)
    if not os.path.exists(fs_path):
        return False
    if sub_id:
        return True
    return os.path.isfile(fs_path)


def session_ref_mtime(file_path: str) -> float:
    """Returns the true last-modified epoch timestamp for a session ref or file."""
    fs_path, sub_id = split_session_ref(file_path)
    if not os.path.exists(fs_path):
        return 0.0

    if sub_id or fs_path.lower().endswith(".vscdb"):
        try:
            from context_audit.cursor_extractor import get_cursor_session_meta
            meta = get_cursor_session_meta(fs_path, sub_id)
            if meta.get("mtime"):
                return float(meta["mtime"])
        except Exception:
            pass

    try:
        return os.path.getmtime(fs_path)
    except OSError:
        return 0.0


def session_ref_size(file_path: str, session: Optional[Session] = None) -> int:
    """Returns the true byte payload size for a session ref or file."""
    fs_path, sub_id = split_session_ref(file_path)
    if session is not None and (sub_id or fs_path.lower().endswith(".vscdb")):
        # Calculate real payload byte size for extracted SQLite session
        history_bytes = sum(len(m.get("content", "").encode("utf-8")) for m in session.history)
        sys_bytes = len(session.system_instructions.encode("utf-8")) if session.system_instructions else 0
        return history_bytes + sys_bytes

    if sub_id or fs_path.lower().endswith(".vscdb"):
        try:
            from context_audit.cursor_extractor import get_cursor_session_meta
            meta = get_cursor_session_meta(fs_path, sub_id)
            if meta.get("size"):
                return int(meta["size"])
        except Exception:
            pass

    try:
        return os.path.getsize(fs_path) if os.path.exists(fs_path) else 0
    except OSError:
        return 0


def format_display_ref(file_path: str, max_len: int = 55) -> str:
    """Formats a session ref or file path for clean console display."""
    from context_audit.reporter import format_display_path
    fs_path, sub_id = split_session_ref(file_path)
    base_display = format_display_path(fs_path, max_len=max_len)
    if sub_id:
        try:
            from context_audit.cursor_extractor import get_cursor_session_meta
            meta = get_cursor_session_meta(fs_path, sub_id)
            title = meta.get("title")
            if title and title != sub_id:
                return f"{base_display} [{title}]"
        except Exception:
            pass
        return f"{base_display} [session: {sub_id[:8]}]"
    return base_display


def expand_session_refs(file_paths: List[str]) -> List[str]:
    """Expands bare state.vscdb paths into one ref per Composer/Chat session."""
    from context_audit.cursor_extractor import extract_cursor_sessions

    expanded: List[str] = []
    for path in file_paths:
        fs_path, session_id = split_session_ref(path)
        if session_id:
            expanded.append(path)
            continue
        if fs_path.lower().endswith(".vscdb") and os.path.isfile(fs_path):
            try:
                extracted = extract_cursor_sessions(fs_path)
            except Exception:
                extracted = []
            if extracted:
                for item in extracted:
                    expanded.append(f"{fs_path}#{item['id']}")
            continue
        expanded.append(path)
    return expanded


def load_session(file_path: str, session_id: Optional[str] = None) -> Session:
    """Loads a session from a file, automatically detecting the format."""
    fs_path, ref_session_id = split_session_ref(file_path)
    file_path = fs_path
    if session_id is None:
        session_id = ref_session_id

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()

    if ext_lower == '.vscdb':
        from context_audit.cursor_extractor import load_cursor_session
        return load_cursor_session(file_path, session_id=session_id)

    if ext_lower in ['.jsonl', '.json']:
        pass
    elif session_id or ext_lower in ['.sqlite', '.db']:
        from context_audit.cursor_extractor import load_cursor_session
        return load_cursor_session(file_path, session_id=session_id)

    if ext_lower == '.jsonl':
        return parse_transcript_jsonl(file_path)
    elif ext_lower == '.json':
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

def find_transcript_files(directory_path: str, max_depth: int = 5) -> List[str]:
    """Finds all transcript.jsonl, session.json, and state.vscdb files recursively under directory_path with directory pruning and depth limits."""
    files = []
    if not os.path.isdir(directory_path):
        return files
        
    from pathlib import Path
    from context_audit.detectors import EXCLUDED_DIRS
    resolved_path = Path(directory_path).resolve()
    base_depth = len(resolved_path.parts)
    is_home = (resolved_path == Path.home().resolve())
    effective_depth = 1 if is_home else max_depth

    for root, dirs, filenames in os.walk(str(resolved_path), topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in EXCLUDED_DIRS]
        cur_depth = len(Path(root).resolve().parts) - base_depth
        if cur_depth >= effective_depth:
            dirs[:] = []
        for filename in filenames:
            fname_lower = filename.lower()
            if fname_lower.endswith('_full.jsonl') or fname_lower.endswith('.full.jsonl'):
                continue
            if fname_lower.endswith('.jsonl') or fname_lower == 'transcript.jsonl':
                files.append(os.path.join(root, filename))
            elif fname_lower == 'session.json' or (fname_lower.endswith('.json') and 'session' in fname_lower):
                files.append(os.path.join(root, filename))
            elif fname_lower.endswith('.vscdb') or fname_lower == 'state.vscdb':
                files.append(os.path.join(root, filename))
    return files

def discover_session_logs(limit: Optional[int] = 20) -> List[str]:
    """Auto-discovers local session logs across standard tools and current workspace, returning the newest first."""
    from context_audit.detectors import run_discovery
    report = run_discovery(limit=limit)
    return report.all_sessions

