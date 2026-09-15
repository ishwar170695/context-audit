import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest

def run_cli_in_env(args, env_vars, cwd):
    """Executes context-audit CLI in a controlled isolated environment."""
    env = os.environ.copy()
    env.update(env_vars)
    # Ensure PYTHONPATH includes repo root so context_audit is importable
    repo_root = str(Path(__file__).resolve().parent.parent)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = repo_root + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    
    cmd = [sys.executable, "-m", "context_audit.cli"] + args
    result = subprocess.run(
        cmd,
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result

def test_scenario_a_clean_machine_no_agents():
    """Test A: Fresh machine with zero agent tools and zero logs."""
    with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as fake_cwd:
        env_vars = {
            "USERPROFILE": fake_home,
            "HOME": fake_home,
            "HOMEPATH": fake_home,
            "APPDATA": os.path.join(fake_home, "AppData", "Roaming"),
            "LOCALAPPDATA": os.path.join(fake_home, "AppData", "Local"),
        }
        
        # 1. Zero-config invocation
        res = run_cli_in_env([], env_vars, fake_cwd)
        assert res.returncode == 0, f"Failed with stderr: {res.stderr}"
        assert "No compatible session found." in res.stdout
        assert "context-audit doctor" in res.stdout
        assert "context-audit demo" in res.stdout
        assert "context-audit run" in res.stdout
        assert "Traceback" not in res.stderr
        
        # 2. Doctor command
        res_doc = run_cli_in_env(["doctor"], env_vars, fake_cwd)
        assert res_doc.returncode == 0
        assert "context-audit doctor" in res_doc.stdout
        assert "No auditable sessions found." in res_doc.stdout
        assert "Traceback" not in res_doc.stderr

        # 3. Demo command on clean machine
        res_demo = run_cli_in_env(["demo"], env_vars, fake_cwd)
        assert res_demo.returncode == 0
        assert "Demo audit" in res_demo.stdout
        assert "Cumulative Session Tokens" in res_demo.stdout
        assert "Context Reuse Ratio" in res_demo.stdout
        assert "Traceback" not in res_demo.stderr

def test_scenario_b_claude_code():
    """Test B: Fresh machine with Claude Code transcripts."""
    with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as fake_cwd:
        # Create Claude Code transcripts structure
        transcripts_dir = Path(fake_home) / ".claude" / "projects" / "sample-project" / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        
        sample_claude_log = transcripts_dir / "session_1234.jsonl"
        with open(sample_claude_log, "w", encoding="utf-8") as f:
            f.write('{"type":"user","message":{"role":"user","content":[{"type":"text","text":"List the directory files."}]}}\n')
            f.write('{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"toolu_01","name":"Bash","input":{"command":"ls -la"}}]}}\n')
            f.write('{"type":"tool_result","message":{"role":"tool","content":[{"type":"tool_result","tool_use_id":"toolu_01","content":"total 0\\n-rw-r--r-- 1 user staff 0 Sep 3 10:00 app.py"}]}}\n')
            f.write('{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Found app.py in the directory."}]}}\n')

        env_vars = {
            "USERPROFILE": fake_home,
            "HOME": fake_home,
            "HOMEPATH": fake_home,
            "APPDATA": os.path.join(fake_home, "AppData", "Roaming"),
            "LOCALAPPDATA": os.path.join(fake_home, "AppData", "Local"),
        }
        
        # 1. Zero-config auto-discovery should find the Claude Code session automatically
        res = run_cli_in_env([], env_vars, fake_cwd)
        assert res.returncode == 0, f"Failed with stderr: {res.stderr}\nstdout: {res.stdout}"
        assert "Discovered 1 agent session log(s)" in res.stdout
        assert "context-audit summary" in res.stdout or "BENCHMARK SUMMARY" in res.stdout or "CONTEXT AUDIT REPORT" in res.stdout
        assert "Traceback" not in res.stderr

        # 2. Doctor should report Claude Code detected with 1 candidate
        res_doc = run_cli_in_env(["doctor"], env_vars, fake_cwd)
        assert res_doc.returncode == 0
        assert "Claude Code" in res_doc.stdout
        assert "1 candidate(s)" in res_doc.stdout

def test_scenario_c_cursor():
    """Test C: Fresh machine where Cursor is installed."""
    with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as fake_cwd:
        # Create Cursor folder
        cursor_dir = Path(fake_home) / ".cursor"
        cursor_dir.mkdir(parents=True, exist_ok=True)

        env_vars = {
            "USERPROFILE": fake_home,
            "HOME": fake_home,
            "HOMEPATH": fake_home,
            "APPDATA": os.path.join(fake_home, "AppData", "Roaming"),
            "LOCALAPPDATA": os.path.join(fake_home, "AppData", "Local"),
        }
        
        # 1. Zero-config auto-discovery should detect Cursor
        res = run_cli_in_env([], env_vars, fake_cwd)
        assert res.returncode == 0
        assert "Cursor" in res.stdout
        assert "0 candidates" in res.stdout
        assert "Traceback" not in res.stderr

        # 2. Doctor should report Cursor as SQLite-supported with no sessions yet
        res_doc = run_cli_in_env(["doctor"], env_vars, fake_cwd)
        assert res_doc.returncode == 0
        assert "Cursor" in res_doc.stdout
        assert "SQLite" in res_doc.stdout


def test_scenario_c_cursor_with_vscdb():
    """Zero-config should audit a Cursor Composer session from state.vscdb."""
    with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as fake_cwd:
        global_dir = Path(fake_home) / ".cursor" / "User" / "globalStorage"
        global_dir.mkdir(parents=True, exist_ok=True)
        db_path = global_dir / "state.vscdb"

        import json
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT);")
        meta = {
            "composerId": "comp-iso",
            "name": "Iso Cursor Session",
            "createdAt": 1718000000000,
            "conversation": [
                {"type": 1, "text": "List the workspace files."},
                {
                    "type": 2,
                    "text": "Listing files now.",
                    "toolResults": [{"tool": "run_terminal", "result": "app.py\nmain.py"}],
                },
            ],
        }
        c.execute(
            "INSERT INTO cursorDiskKV VALUES (?, ?);",
            ("composerData:comp-iso", json.dumps(meta)),
        )
        conn.commit()
        conn.close()

        env_vars = {
            "USERPROFILE": fake_home,
            "HOME": fake_home,
            "HOMEPATH": fake_home,
            "APPDATA": os.path.join(fake_home, "AppData", "Roaming"),
            "LOCALAPPDATA": os.path.join(fake_home, "AppData", "Local"),
        }

        res = run_cli_in_env([], env_vars, fake_cwd)
        assert res.returncode == 0, f"Failed with stderr: {res.stderr}\nstdout: {res.stdout}"
        assert "Discovered" in res.stdout
        assert "agent session log" in res.stdout
        assert "Traceback" not in res.stderr
        assert "Audited most recent session:" in res.stdout

        res_doc = run_cli_in_env(["doctor"], env_vars, fake_cwd)
        assert res_doc.returncode == 0
        assert "Cursor" in res_doc.stdout
        assert "1 candidate(s)" in res_doc.stdout


def test_scenario_d_aider():
    """Test D: Fresh machine where Aider is present."""
    with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as fake_cwd:
        # Create Aider history file
        aider_file = Path(fake_home) / ".aider.chat.history.md"
        aider_file.write_text("# Aider chat history\n\n> USER: hello\n\nMODEL: hi\n", encoding="utf-8")

        env_vars = {
            "USERPROFILE": fake_home,
            "HOME": fake_home,
            "HOMEPATH": fake_home,
            "APPDATA": os.path.join(fake_home, "AppData", "Roaming"),
            "LOCALAPPDATA": os.path.join(fake_home, "AppData", "Local"),
        }
        
        # 1. Zero-config auto-discovery should detect Aider and report unsupported format
        res = run_cli_in_env([], env_vars, fake_cwd)
        assert res.returncode == 0
        assert "Aider" in res.stdout
        assert "unsupported format" in res.stdout
        assert "Traceback" not in res.stderr

        # 2. Doctor should report Aider with Markdown unsupported note
        res_doc = run_cli_in_env(["doctor"], env_vars, fake_cwd)
        assert res_doc.returncode == 0
        assert "Aider" in res_doc.stdout
        assert "Markdown" in res_doc.stdout

def test_scenario_e_antigravity():
    """Test E: Fresh machine with Antigravity transcripts."""
    with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as fake_cwd:
        brain_dir = Path(fake_home) / ".gemini" / "antigravity-ide" / "brain" / "conv_abc" / ".system_generated" / "logs"
        brain_dir.mkdir(parents=True, exist_ok=True)
        
        transcript_file = brain_dir / "transcript.jsonl"
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write('{"type":"USER_INPUT","content":"Check file."}\n')
            f.write('{"type":"PLANNER_RESPONSE","thinking":"listing","tool_calls":[{"name":"list_dir","args":{}}]}\n')
            f.write('{"type":"LIST_DIRECTORY","content":"file.txt"}\n')
            f.write('{"type":"PLANNER_RESPONSE","thinking":"done","tool_calls":[]}\n')

        env_vars = {
            "USERPROFILE": fake_home,
            "HOME": fake_home,
            "HOMEPATH": fake_home,
            "APPDATA": os.path.join(fake_home, "AppData", "Roaming"),
            "LOCALAPPDATA": os.path.join(fake_home, "AppData", "Local"),
        }
        
        # 1. Zero-config should find and analyze the Antigravity session
        res = run_cli_in_env([], env_vars, fake_cwd)
        assert res.returncode == 0, f"Failed with stderr: {res.stderr}\nstdout: {res.stdout}"
        assert "Discovered 1 agent session log(s)" in res.stdout
        assert "Traceback" not in res.stderr

        # 2. Doctor should report Antigravity detected with 1 candidate
        res_doc = run_cli_in_env(["doctor"], env_vars, fake_cwd)
        assert res_doc.returncode == 0
        assert "Antigravity" in res_doc.stdout
        assert "1 candidate(s)" in res_doc.stdout
