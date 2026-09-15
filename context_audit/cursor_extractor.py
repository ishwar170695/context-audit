import json
import os
import platform
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from context_audit.parser import Session

# In-memory cache for fast metadata lookup (mtime, size, title)
_SESSION_META_CACHE: Dict[str, Dict[str, Any]] = {}

def find_cursor_databases() -> List[str]:
    """Scans standard OS locations for Cursor state.vscdb databases."""
    system = platform.system()
    home = Path.home()
    base_dirs = []

    if system == "Darwin":  # macOS
        base_dirs = [
            home / "Library" / "Application Support",
            home / ".config"
        ]
    elif system == "Linux":
        base_dirs = [
            home / ".config",
            home / ".local" / "share"
        ]
    elif system == "Windows":
        appdata = os.environ.get('APPDATA')
        localappdata = os.environ.get('LOCALAPPDATA')
        if appdata:
            base_dirs.append(Path(appdata))
        if localappdata:
            base_dirs.append(Path(localappdata))
        base_dirs.append(home / "AppData" / "Roaming")
        base_dirs.append(home / "AppData" / "Local")
        base_dirs.append(home)
    else:
        base_dirs = [home / ".config", home]

    cursor_dirs = []
    for base in base_dirs:
        if base and base.exists():
            c_dir = base / "Cursor"
            if c_dir.exists():
                cursor_dirs.append(c_dir)
            c_dir_tutor = base / ".cursor"
            if c_dir_tutor.exists():
                cursor_dirs.append(c_dir_tutor)

    found_dbs = []
    for c_dir in set(cursor_dirs):
        # 1. Global storage (contains composer sessions in cursorDiskKV)
        global_db = c_dir / "User" / "globalStorage" / "state.vscdb"
        if global_db.exists():
            found_dbs.append(str(global_db))

        # 2. Workspace storage (contains workspace composers & chat in ItemTable)
        ws_dir = c_dir / "User" / "workspaceStorage"
        if ws_dir.exists():
            for ws_sub in ws_dir.iterdir():
                if ws_sub.is_dir():
                    ws_db = ws_sub / "state.vscdb"
                    if ws_db.exists():
                        found_dbs.append(str(ws_db))

    return found_dbs

def open_sqlite_readonly(db_path: str) -> sqlite3.Connection:
    """Safely opens an SQLite database in read-only mode to prevent lockups."""
    try:
        abs_path = os.path.abspath(db_path).replace("\\", "/")
        return sqlite3.connect(f"file:{abs_path}?mode=ro", uri=True, timeout=5.0)
    except Exception:
        return sqlite3.connect(db_path, timeout=5.0)

def extract_cursor_sessions(db_path: str) -> List[Dict[str, Any]]:
    """
    Extracts all conversation/composer sessions from a Cursor state.vscdb SQLite file.
    Returns a list of dicts:
    {
        'id': str,
        'title': str,
        'created_at': float (epoch seconds),
        'last_updated_at': float (epoch seconds),
        'model': Optional[str],
        'session': Session,
        'message_count': int,
        'byte_size': int
    }
    """
    if not os.path.exists(db_path):
        return []

    conn = open_sqlite_readonly(db_path)
    sessions = []

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = set(r[0] for r in cursor.fetchall())

        if "cursorDiskKV" in tables:
            sessions.extend(_extract_from_cursor_disk_kv(cursor, db_path))

        if "ItemTable" in tables:
            sessions.extend(_extract_from_item_table(cursor, db_path))

    except Exception:
        pass
    finally:
        conn.close()

    # Cache metadata for quick access by session_ref_mtime / session_ref_size
    file_mtime = os.path.getmtime(db_path) if os.path.exists(db_path) else 0.0
    for s in sessions:
        ref_key = f"{db_path}#{s['id']}"
        mtime = s.get("last_updated_at") or s.get("created_at") or file_mtime
        _SESSION_META_CACHE[ref_key] = {
            "mtime": float(mtime),
            "size": s.get("byte_size", 0),
            "title": s.get("title", ""),
            "message_count": s.get("message_count", 0)
        }

    # Sort sessions newest first
    sessions.sort(key=lambda x: x.get("last_updated_at") or x.get("created_at") or 0.0, reverse=True)
    return sessions

def _normalize_timestamp(ts: Any, fallback: float) -> float:
    """Converts millisecond or second timestamps to epoch seconds float."""
    if ts is None:
        return fallback
    try:
        val = float(ts)
        # If timestamp is in milliseconds (> year 2000 in ms is ~946684800000)
        if val > 1e11:
            return val / 1000.0
        return val
    except (ValueError, TypeError):
        return fallback

def _extract_from_cursor_disk_kv(cursor: sqlite3.Cursor, db_path: str) -> List[Dict[str, Any]]:
    """Extracts composers, file attachments, and tool outputs from cursorDiskKV table."""
    sessions = []
    file_mtime = os.path.getmtime(db_path) if os.path.exists(db_path) else 0.0

    cursor.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'")
    composer_rows = cursor.fetchall()

    for key, val_str in composer_rows:
        if not val_str:
            continue
        try:
            data = json.loads(val_str)
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        composer_id = data.get("composerId") or key.split(":", 1)[1]
        name = data.get("name") or data.get("title") or f"Composer {composer_id[:8]}"
        created_at = _normalize_timestamp(data.get("createdAt"), file_mtime)
        last_updated_at = _normalize_timestamp(data.get("lastUpdatedAt"), created_at)
        model = data.get("modelConfig", {}).get("modelName") if isinstance(data.get("modelConfig"), dict) else None

        # Extract system prompt / workspace instructions / custom rules if stored
        system_instructions = (
            data.get("customInstructions") or
            data.get("rules") or
            data.get("systemPrompt") or
            data.get(".cursorrules") or
            data.get("workspaceRules") or
            "You are Cursor AI, an advanced coding assistant with agentic editing and terminal execution capabilities."
        )

        messages = []
        observed_tools = set()

        # Extract declared capabilities/tools if present
        capabilities = data.get("capabilities", {})
        if isinstance(capabilities, dict):
            for cap_name in capabilities.keys():
                observed_tools.add(str(cap_name))

        # Format A: Inline conversation list
        inline_conv = data.get("conversation")
        if isinstance(inline_conv, list) and len(inline_conv) > 0:
            for b_idx, bubble in enumerate(inline_conv):
                _process_bubble(bubble, b_idx, messages, observed_tools)
        else:
            # Format B: Separate bubble keys (bubbleId:{composerId}:{bubbleId})
            headers = data.get("fullConversationHeadersOnly") or data.get("conversationOrder") or []
            bubble_order = []
            if isinstance(headers, list):
                for h in headers:
                    if isinstance(h, dict) and "bubbleId" in h:
                        bubble_order.append(h["bubbleId"])
                    elif isinstance(h, str):
                        bubble_order.append(h)

            cursor.execute(
                "SELECT key, value FROM cursorDiskKV WHERE key LIKE ?",
                (f"bubbleId:{composer_id}:%",)
            )
            bubble_dict = {}
            for b_key, b_val in cursor.fetchall():
                if not b_val:
                    continue
                try:
                    b_id = b_key.split(":")[-1]
                    bubble_dict[b_id] = json.loads(b_val)
                except Exception:
                    continue

            ordered_bubbles = []
            if bubble_order:
                for b_id in bubble_order:
                    if b_id in bubble_dict:
                        ordered_bubbles.append(bubble_dict[b_id])
                for b_id, b_data in bubble_dict.items():
                    if b_id not in bubble_order:
                        ordered_bubbles.append(b_data)
            else:
                ordered_bubbles = list(bubble_dict.values())

            for b_idx, bubble in enumerate(ordered_bubbles):
                _process_bubble(bubble, b_idx, messages, observed_tools)

        if messages:
            # Always ensure standard Cursor agent capabilities are in schema so tool overhead is realistic
            default_tools = ["codebase_search", "read_file", "edit_file", "terminal_command"]
            for dt in default_tools:
                observed_tools.add(dt)

            tools = [{"name": t, "description": f"Tool schema for {t}"} for t in observed_tools]
            session_obj = Session(
                system_instructions=str(system_instructions),
                tools=tools,
                history=messages
            )

            # Compute real extracted byte size
            total_bytes = sum(len(m.get("content", "").encode("utf-8")) for m in messages)
            sessions.append({
                "id": composer_id,
                "title": name,
                "created_at": created_at,
                "last_updated_at": last_updated_at,
                "model": model,
                "session": session_obj,
                "message_count": len(messages),
                "byte_size": total_bytes
            })

    return sessions

def _extract_from_item_table(cursor: sqlite3.Cursor, db_path: str) -> List[Dict[str, Any]]:
    """Extracts workspace composers and chats from ItemTable."""
    sessions = []
    file_mtime = os.path.getmtime(db_path) if os.path.exists(db_path) else 0.0

    # 1. composer.composerData
    try:
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'composer.composerData'")
        row = cursor.fetchone()
        if row and row[0]:
            val_bytes = row[0]
            val_str = val_bytes.decode('utf-8') if isinstance(val_bytes, bytes) else val_bytes
            data = json.loads(val_str)
            all_composers = data.get("allComposers", [])
            if isinstance(all_composers, list):
                for comp in all_composers:
                    if not isinstance(comp, dict):
                        continue
                    c_id = comp.get("composerId", "workspace-composer")
                    name = comp.get("name") or "Workspace Composer"
                    c_time = _normalize_timestamp(comp.get("createdAt"), file_mtime)
                    u_time = _normalize_timestamp(comp.get("lastUpdatedAt"), c_time)
                    model = comp.get("modelConfig", {}).get("modelName") if isinstance(comp.get("modelConfig"), dict) else None
                    
                    system_instructions = (
                        comp.get("customInstructions") or
                        comp.get("rules") or
                        "You are Cursor AI, an intelligent coding assistant."
                    )

                    messages = []
                    observed_tools = {"codebase_search", "read_file", "edit_file", "terminal_command"}
                    conv = comp.get("conversation", [])
                    if isinstance(conv, list):
                        for b_idx, bubble in enumerate(conv):
                            _process_bubble(bubble, b_idx, messages, observed_tools)

                    if messages:
                        tools = [{"name": t, "description": f"Tool: {t}"} for t in observed_tools]
                        total_bytes = sum(len(m.get("content", "").encode("utf-8")) for m in messages)
                        sessions.append({
                            "id": c_id,
                            "title": name,
                            "created_at": c_time,
                            "last_updated_at": u_time,
                            "model": model,
                            "session": Session(
                                system_instructions=str(system_instructions),
                                tools=tools,
                                history=messages
                            ),
                            "message_count": len(messages),
                            "byte_size": total_bytes
                        })
    except Exception:
        pass

    # 2. workbench.panel.aichat.view.aichat.chatdata
    try:
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'workbench.panel.aichat.view.aichat.chatdata'")
        row = cursor.fetchone()
        if row and row[0]:
            val_bytes = row[0]
            val_str = val_bytes.decode('utf-8') if isinstance(val_bytes, bytes) else val_bytes
            data = json.loads(val_str)
            tabs = data.get("tabs", [])
            if isinstance(tabs, list):
                for tab in tabs:
                    if not isinstance(tab, dict):
                        continue
                    tab_id = tab.get("tabId", "chat-tab")
                    title = tab.get("chatTitle") or "Cursor Chat"
                    bubbles = tab.get("bubbles", [])
                    
                    messages = []
                    observed_tools = set()
                    if isinstance(bubbles, list):
                        for b_idx, bubble in enumerate(bubbles):
                            _process_bubble(bubble, b_idx, messages, observed_tools)

                    if messages:
                        total_bytes = sum(len(m.get("content", "").encode("utf-8")) for m in messages)
                        sessions.append({
                            "id": tab_id,
                            "title": title,
                            "created_at": file_mtime,
                            "last_updated_at": file_mtime,
                            "model": None,
                            "session": Session(
                                system_instructions="You are Cursor AI, an intelligent coding assistant.",
                                tools=[],
                                history=messages
                            ),
                            "message_count": len(messages),
                            "byte_size": total_bytes
                        })
    except Exception:
        pass

    return sessions

def _process_bubble(bubble: Dict[str, Any], step_idx: int, messages: List[Dict[str, Any]], observed_tools: set):
    """
    Parses a single Cursor bubble into normalized history messages with full payload fidelity.
    Extracts:
    - User message text
    - File selections, attached context, notepads, codebase chunks
    - Assistant thinking, generated code, diffs
    - Tool calls & tool execution output (terminal stdout, stderr, linter results)
    """
    if not isinstance(bubble, dict):
        return

    b_type = bubble.get("type")
    is_user = (b_type == 1 or b_type == "user")
    is_assistant = (b_type == 2 or b_type == "assistant" or b_type == "ai")

    text = bubble.get("text") or bubble.get("rawText") or bubble.get("content") or ""

    if is_user:
        # Extract all attached workspace context
        context_parts = []
        
        # 1. Attached selections & files
        selections = bubble.get("selections", [])
        context_obj = bubble.get("context", {})
        if isinstance(context_obj, dict):
            selections = selections or context_obj.get("selections", [])
            file_selections = context_obj.get("fileSelections", [])
            if isinstance(file_selections, list):
                for fsel in file_selections:
                    if isinstance(fsel, dict):
                        fpath = fsel.get("uri", {}).get("fsPath") or fsel.get("file", "")
                        fcontent = fsel.get("text") or fsel.get("rawText") or ""
                        if fpath or fcontent:
                            context_parts.append(f"--- File: {fpath} ---\n{fcontent}")

            # 2. Notepads / rules
            notepads = context_obj.get("notepads", [])
            if isinstance(notepads, list):
                for np in notepads:
                    if isinstance(np, dict):
                        np_name = np.get("name", "Notepad")
                        np_text = np.get("text", "")
                        if np_text:
                            context_parts.append(f"--- Context Rule / Notepad: {np_name} ---\n{np_text}")

            # 3. Codebase chunks
            cb_chunks = context_obj.get("codebaseContext") or context_obj.get("codebaseResults") or []
            if isinstance(cb_chunks, list):
                for chunk in cb_chunks:
                    if isinstance(chunk, dict):
                        c_file = chunk.get("file") or chunk.get("path", "")
                        c_text = chunk.get("text") or chunk.get("snippet", "")
                        if c_text:
                            context_parts.append(f"--- Codebase Match: {c_file} ---\n{c_text}")

            # 4. Terminal selections
            term_sels = context_obj.get("terminalSelections") or []
            if isinstance(term_sels, list):
                for ts in term_sels:
                    if isinstance(ts, dict):
                        t_txt = ts.get("text", "")
                        if t_txt:
                            context_parts.append(f"--- Attached Terminal Output ---\n{t_txt}")

        if isinstance(selections, list):
            for sel in selections:
                if isinstance(sel, dict):
                    fpath = sel.get("uri", {}).get("fsPath") or sel.get("file", "")
                    snippet = sel.get("text") or sel.get("rawText") or ""
                    rng = sel.get("range")
                    loc_desc = f" (lines {rng.get('startLineNumber')}-{rng.get('endLineNumber')})" if isinstance(rng, dict) else ""
                    if fpath or snippet:
                        context_parts.append(f"--- Code Selection: {fpath}{loc_desc} ---\n{snippet}")

        full_user_content = text
        if context_parts:
            full_user_content = f"{text}\n\n" + "\n\n".join(context_parts)

        messages.append({
            "role": "user",
            "content": str(full_user_content),
            "step_index": step_idx
        })

    elif is_assistant:
        tool_calls = []
        tool_results = (
            bubble.get("toolResults") or 
            bubble.get("tool_results") or 
            bubble.get("terminalCommandResults") or 
            bubble.get("commandResults") or 
            []
        )
        
        if isinstance(tool_results, list) and tool_results:
            for tr in tool_results:
                tname = "terminal_command"
                if isinstance(tr, dict):
                    tname = tr.get("tool") or tr.get("name") or ("terminal_command" if "command" in tr else "tool")
                observed_tools.add(tname)
                tool_calls.append({"name": tname, "args": tr if isinstance(tr, dict) else {}})

        # Extract code blocks & diffs
        content_parts = [text]
        code_blocks = bubble.get("codeBlocks") or bubble.get("suggestedCodeBlocks") or []
        if isinstance(code_blocks, list):
            for cb in code_blocks:
                if isinstance(cb, dict) and "code" in cb:
                    content_parts.append(cb["code"])
                elif isinstance(cb, str):
                    content_parts.append(cb)

        diffs = bubble.get("diffHistories") or bubble.get("codeBlockDiff") or []
        if isinstance(diffs, list):
            for d in diffs:
                if isinstance(d, dict):
                    diff_text = d.get("diff") or d.get("text") or ""
                    if diff_text:
                        content_parts.append(f"```diff\n{diff_text}\n```")
                elif isinstance(d, str):
                    content_parts.append(f"```diff\n{d}\n```")

        msg_item = {
            "role": "model",
            "content": "\n\n".join(filter(None, content_parts)),
            "step_index": step_idx
        }
        if tool_calls:
            msg_item["tool_calls"] = tool_calls
        messages.append(msg_item)

        # Inject real tool results as tool roles so the analyzer measures tool payload and repeated terminal logs
        if isinstance(tool_results, list) and tool_results:
            for tr in tool_results:
                t_name = "terminal_command"
                t_content = ""
                if isinstance(tr, dict):
                    t_name = tr.get("tool") or tr.get("name") or ("terminal_command" if "command" in tr else "tool")
                    t_content = tr.get("result") or tr.get("output") or tr.get("stdout") or tr.get("stderr") or json.dumps(tr)
                else:
                    t_content = str(tr)

                messages.append({
                    "role": "tool",
                    "name": str(t_name),
                    "content": str(t_content),
                    "step_index": step_idx
                })
    else:
        if text:
            messages.append({
                "role": "user" if "user" in str(b_type).lower() else "model",
                "content": str(text),
                "step_index": step_idx
            })

def load_cursor_session(db_path: str, session_id: Optional[str] = None) -> Session:
    """Loads a specific or most active session from a Cursor state.vscdb database."""
    sessions = extract_cursor_sessions(db_path)
    if not sessions:
        raise ValueError(f"No active Cursor sessions or conversations found in: {db_path}")

    if session_id:
        for s in sessions:
            if str(s["id"]).lower() == str(session_id).lower():
                return s["session"]
        try:
            idx = int(session_id)
            if 0 <= idx < len(sessions):
                return sessions[idx]["session"]
        except ValueError:
            pass
        raise ValueError(f"Session '{session_id}' not found in {db_path}. Available: {[s['id'] for s in sessions]}")

    # Default to newest active session
    return sessions[0]["session"]

def get_cursor_session_meta(db_path: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Returns cached or extracted metadata (mtime, size, title) for a session ref."""
    ref_key = f"{db_path}#{session_id}" if session_id else db_path
    if ref_key in _SESSION_META_CACHE:
        return _SESSION_META_CACHE[ref_key]

    # Populate cache by extracting sessions
    sessions = extract_cursor_sessions(db_path)
    if ref_key in _SESSION_META_CACHE:
        return _SESSION_META_CACHE[ref_key]

    # Fallback
    file_mtime = os.path.getmtime(db_path) if os.path.exists(db_path) else 0.0
    return {
        "mtime": file_mtime,
        "size": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "title": os.path.basename(db_path),
        "message_count": 0
    }
