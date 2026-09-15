import json
import os
import sqlite3
import tempfile
import pytest
from pathlib import Path

from context_audit.cursor_extractor import (
    extract_cursor_sessions,
    load_cursor_session,
    find_cursor_databases
)
from context_audit.parser import load_session, Session
from context_audit.analyzer import analyze_session
from context_audit.cli import main

def create_synthetic_cursor_disk_kv_db(db_path: str):
    """Creates a synthetic globalStorage state.vscdb with cursorDiskKV table."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT);")

    # Composer 1: separate bubbles
    comp1_id = "comp-12345-uuid"
    comp1_meta = {
        "composerId": comp1_id,
        "name": "Refactor Auth Middleware",
        "createdAt": 1718000000000,
        "fullConversationHeadersOnly": [
            {"bubbleId": "b1"},
            {"bubbleId": "b2"},
            {"bubbleId": "b3"},
            {"bubbleId": "b4"}
        ],
        "modelConfig": {"modelName": "claude-3-5-sonnet"}
    }
    c.execute("INSERT INTO cursorDiskKV VALUES (?, ?);", (f"composerData:{comp1_id}", json.dumps(comp1_meta)))

    # Bubble 1: User prompt with attached file context
    b1 = {
        "type": 1,
        "text": "Please refactor the auth middleware to support JWT rotation.",
        "context": {
            "selections": [
                {
                    "uri": {"fsPath": "/workspace/src/auth.py"},
                    "text": "def verify_token(token):\n    return jwt.decode(token, SECRET, algorithms=['HS256'])\n"
                }
            ]
        }
    }
    # Bubble 2: Assistant response with tool execution
    b2 = {
        "type": 2,
        "text": "I will inspect the existing token structure and update auth.py.",
        "modelId": "claude-3-5-sonnet",
        "codeBlocks": ["import jwt\n\ndef verify_token_v2(token):\n    pass\n"],
        "toolResults": [
            {"tool": "run_terminal", "result": "Test suite passed: 12 tests OK"}
        ]
    }
    # Bubble 3: User follow-up
    b3 = {
        "type": 1,
        "text": "Now add the refresh token handler."
    }
    # Bubble 4: Assistant follow-up
    b4 = {
        "type": 2,
        "text": "Here is the refresh token implementation.",
        "codeBlocks": ["def refresh_token(token):\n    return create_new_token()\n"]
    }

    c.execute("INSERT INTO cursorDiskKV VALUES (?, ?);", (f"bubbleId:{comp1_id}:b1", json.dumps(b1)))
    c.execute("INSERT INTO cursorDiskKV VALUES (?, ?);", (f"bubbleId:{comp1_id}:b2", json.dumps(b2)))
    c.execute("INSERT INTO cursorDiskKV VALUES (?, ?);", (f"bubbleId:{comp1_id}:b3", json.dumps(b3)))
    c.execute("INSERT INTO cursorDiskKV VALUES (?, ?);", (f"bubbleId:{comp1_id}:b4", json.dumps(b4)))

    # Composer 2: inline conversation format
    comp2_id = "comp-inline-999"
    comp2_meta = {
        "composerId": comp2_id,
        "name": "Database Migration Script",
        "createdAt": 1718000500000,
        "conversation": [
            {
                "type": 1,
                "text": "Create a migration for the user profiles table."
            },
            {
                "type": 2,
                "text": "Here is the migration script:",
                "codeBlocks": ["CREATE TABLE profiles (id INT PRIMARY KEY, bio TEXT);"]
            }
        ]
    }
    c.execute("INSERT INTO cursorDiskKV VALUES (?, ?);", (f"composerData:{comp2_id}", json.dumps(comp2_meta)))

    conn.commit()
    conn.close()

def create_synthetic_workspace_item_table_db(db_path: str):
    """Creates a synthetic workspaceStorage state.vscdb with ItemTable."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB);")

    # 1. composer.composerData
    workspace_comp = {
        "allComposers": [
            {
                "composerId": "ws-comp-1",
                "name": "Workspace API Router",
                "createdAt": 1718001000000,
                "conversation": [
                    {"type": 1, "text": "Set up FastAPI router."},
                    {"type": 2, "text": "Here is the router setup for FastAPI."}
                ]
            }
        ]
    }
    c.execute("INSERT INTO ItemTable VALUES (?, ?);", ("composer.composerData", json.dumps(workspace_comp).encode('utf-8')))

    # 2. workbench.panel.aichat.view.aichat.chatdata
    chat_data = {
        "tabs": [
            {
                "tabId": "tab-alpha",
                "chatTitle": "Explain Regex",
                "bubbles": [
                    {"type": "user", "text": "Explain this regex: ^[a-z0-9]+$"},
                    {"type": "assistant", "text": "This regex matches any alphanumeric string."}
                ]
            }
        ]
    }
    c.execute("INSERT INTO ItemTable VALUES (?, ?);", ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chat_data).encode('utf-8')))

    conn.commit()
    conn.close()

def test_extract_cursor_disk_kv_sessions():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_cursor_disk_kv_db(db_path)

        sessions = extract_cursor_sessions(db_path)
        assert len(sessions) == 2

        # Verify comp1
        comp1 = next(s for s in sessions if s["id"] == "comp-12345-uuid")
        assert comp1["title"] == "Refactor Auth Middleware"
        assert comp1["model"] == "claude-3-5-sonnet"
        assert comp1["message_count"] >= 4

        sess1 = comp1["session"]
        assert isinstance(sess1, Session)
        assert len(sess1.history) >= 4
        # Check that attached file context was extracted
        user_msg = sess1.history[0]
        assert user_msg["role"] == "user"
        assert "auth.py" in user_msg["content"]
        assert "verify_token" in user_msg["content"]

        # Check assistant and tool results
        asst_msg = sess1.history[1]
        assert asst_msg["role"] == "model"
        assert "verify_token_v2" in asst_msg["content"]

        # Verify comp2 (inline)
        comp2 = next(s for s in sessions if s["id"] == "comp-inline-999")
        assert comp2["title"] == "Database Migration Script"
        assert comp2["message_count"] == 2

def test_extract_workspace_item_table():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_workspace_item_table_db(db_path)

        sessions = extract_cursor_sessions(db_path)
        assert len(sessions) == 2

        titles = [s["title"] for s in sessions]
        assert "Workspace API Router" in titles
        assert "Explain Regex" in titles

def test_load_session_with_cursor_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_cursor_disk_kv_db(db_path)

        # Default load: most recently created composer (inline, 2 messages)
        session_default = load_session(db_path)
        assert isinstance(session_default, Session)
        assert len(session_default.history) == 2

        # Specific session via parameter
        session_specific = load_session(db_path, session_id="comp-12345-uuid")
        assert len(session_specific.history) >= 4

        # Specific session via # URL syntax
        session_hash = load_session(f"{db_path}#comp-inline-999")
        assert len(session_hash.history) == 2

def test_analyze_cursor_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_cursor_disk_kv_db(db_path)

        session = load_session(f"{db_path}#comp-12345-uuid")
        res = analyze_session(session)

        assert res.total_tokens_across_session > 0
        assert res.peak_context_size > 0
        assert res.context_reuse_ratio >= 0
        assert len(res.timeline) >= 2

def test_split_session_ref_and_expand():
    from context_audit.parser import split_session_ref, session_fs_path, expand_session_refs

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_cursor_disk_kv_db(db_path)

        fs_path, sid = split_session_ref(f"{db_path}#comp-inline-999")
        assert fs_path == db_path
        assert sid == "comp-inline-999"
        assert session_fs_path(f"{db_path}#comp-inline-999") == db_path
        assert session_fs_path(db_path) == db_path

        expanded = expand_session_refs([db_path])
        assert f"{db_path}#comp-12345-uuid" in expanded
        assert f"{db_path}#comp-inline-999" in expanded
        assert db_path not in expanded

def test_benchmark_and_discovery_accept_hash_refs():
    from context_audit.analyzer import run_benchmark
    from context_audit.detectors import AgentDetector, run_discovery

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_cursor_disk_kv_db(db_path)
        jsonl_path = os.path.join(tmpdir, "older.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write('{"type":"USER_INPUT","content":"hello"}\n')
            f.write('{"type":"PLANNER_RESPONSE","thinking":"hi"}\n')

        os.utime(jsonl_path, (1_700_000_000, 1_700_000_000))
        os.utime(db_path, (1_800_000_000, 1_800_000_000))

        hash_ref = f"{db_path}#comp-inline-999"
        summary = run_benchmark([hash_ref])
        assert summary.total_sessions == 1
        assert len(summary.file_sizes) == 1
        assert summary.file_sizes[0] > 0

        dir_summary = run_benchmark(tmpdir)
        assert dir_summary.total_sessions >= 2

        class MockDetector(AgentDetector):
            name = "MockCursor"
            format_name = "SQLite"
            format_supported = True
            def is_installed(self):
                return True
            def find_sessions(self):
                return [hash_ref, jsonl_path]

        report = run_discovery(detectors=[MockDetector()], limit=10)
        assert report.all_sessions[0] == hash_ref

def test_analyze_cursor_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "state.vscdb")
        create_synthetic_cursor_disk_kv_db(db_path)

        # Multi-turn session
        session_multi = load_session(f"{db_path}#comp-12345-uuid")
        res_multi = analyze_session(session_multi)
        assert res_multi.total_tokens_across_session > 0
        assert res_multi.peak_context_size > 0
        assert res_multi.context_reuse_ratio >= 0
        assert len(res_multi.timeline) >= 2

        # Newest session by default
        session_default = load_session(db_path)
        res_default = analyze_session(session_default)
        assert res_default.total_tokens_across_session > 0
        assert len(res_default.timeline) >= 1
