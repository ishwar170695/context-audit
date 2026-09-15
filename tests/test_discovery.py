import os
import sys
import tempfile
import pytest
from pathlib import Path
from context_audit.detectors import (
    AgentDetector,
    AntigravityDetector,
    ClaudeCodeDetector,
    CodexDetector,
    CursorDetector,
    AiderDetector,
    WorkspaceDetector,
    DiscoveryReport,
    run_discovery
)
from context_audit.cli import run_doctor, run_demo, run_auto_discover
from context_audit.reporter import console

def test_base_agent_detector_contract():
    detector = AgentDetector()
    assert detector.name == "BaseAgent"
    assert not detector.is_installed()
    assert detector.get_candidate_paths() == []
    assert detector.find_sessions() == []
    
    inspect_data = detector.inspect()
    assert inspect_data["installed"] is False
    assert inspect_data["status_summary"] == "not detected"

def test_workspace_detector():
    detector = WorkspaceDetector()
    assert detector.is_installed() is True
    assert detector.format_supported is True
    assert len(detector.get_candidate_paths()) > 0
    inspect_data = detector.inspect()
    assert inspect_data["name"] == "Local Workspace"
    assert inspect_data["installed"] is True

def test_cursor_supported_and_aider_unsupported_status():
    cursor_det = CursorDetector()
    assert cursor_det.name == "Cursor"
    assert cursor_det.format_supported is True
    assert "SQLite" in cursor_det.format_name

    aider_det = AiderDetector()
    assert aider_det.name == "Aider"
    assert aider_det.format_supported is False
    assert "Markdown" in aider_det.support_note
    assert aider_det.find_sessions() == []

def test_claude_and_codex_detectors():
    claude_det = ClaudeCodeDetector()
    assert claude_det.name == "Claude Code"
    assert claude_det.format_supported is True
    assert len(claude_det.get_candidate_paths()) > 0

    codex_det = CodexDetector()
    assert codex_det.name == "Codex"
    assert codex_det.format_supported is True

def test_run_discovery_aggregation():
    # Create custom mock detector with a temp transcript file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "transcript.jsonl"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('{"type":"USER_INPUT","content":"hello"}\n')
            f.write('{"type":"PLANNER_RESPONSE","thinking":"hi"}\n')

        class MockDetector(AgentDetector):
            name = "MockAgent"
            format_name = "JSONL"
            format_supported = True
            def is_installed(self):
                return True
            def get_candidate_paths(self):
                return [Path(tmpdir)]
            def find_sessions(self):
                return [str(test_file)]

        report = run_discovery(detectors=[MockDetector()], limit=10)
        assert isinstance(report, DiscoveryReport)
        assert report.has_sessions is True
        assert len(report.all_sessions) == 1
        assert report.all_sessions[0] == str(test_file)
        assert len(report.detected_agents) == 1
        assert report.detected_agents[0]["name"] == "MockAgent"

def test_doctor_command_runs_without_error(capsys):
    run_doctor()

def test_demo_command_runs_without_error():
    # Should execute full analysis on sample transcript
    run_demo()

def test_auto_discover_no_sessions_fallback(monkeypatch, capsys):
    # Mock run_discovery to return 0 sessions
    class EmptyDetector(AgentDetector):
        name = "EmptyClaude"
        format_name = "JSONL"
        format_supported = True
        def is_installed(self):
            return True
        def find_sessions(self):
            return []

    from context_audit import cli
    monkeypatch.setattr(cli, "run_discovery", lambda: DiscoveryReport(
        agent_reports=[EmptyDetector().inspect()],
        all_sessions=[]
    ))
    
    # Should not raise, should show helpful fallback advice
    cli.run_auto_discover()

def test_workspace_detector_skips_home_directory(monkeypatch):
    detector = WorkspaceDetector()
    monkeypatch.setattr(Path, "cwd", lambda: Path.home())
    # When CWD is home, WorkspaceDetector must not attempt to recursively scan home
    sessions = detector.find_sessions()
    assert sessions == []

def test_scan_for_transcripts_prunes_excluded_dirs_and_depth():
    from context_audit.detectors import _scan_for_transcripts
    from context_audit.parser import find_transcript_files

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create excluded directory structure
        (root / "node_modules" / "pkg").mkdir(parents=True)
        with open(root / "node_modules" / "pkg" / "session.json", "w") as f:
            f.write('{"turns": []}')
            
        (root / ".git" / "logs").mkdir(parents=True)
        with open(root / ".git" / "logs" / "transcript.jsonl", "w") as f:
            f.write('{"type":"USER_INPUT"}\n')

        # Create valid transcript in shallow directory
        (root / "project" / "logs").mkdir(parents=True)
        valid_file = root / "project" / "logs" / "transcript.jsonl"
        with open(valid_file, "w") as f:
            f.write('{"type":"USER_INPUT"}\n')

        # Create deep transcript beyond max_depth 2
        (root / "a" / "b" / "c" / "d").mkdir(parents=True)
        deep_file = root / "a" / "b" / "c" / "d" / "transcript.jsonl"
        with open(deep_file, "w") as f:
            f.write('{"type":"USER_INPUT"}\n')

        found = _scan_for_transcripts([root], max_depth=2)
        assert str(valid_file.resolve()) in found
        assert not any("node_modules" in f for f in found)
        assert not any(".git" in f for f in found)
        assert str(deep_file.resolve()) not in found

        parser_found = find_transcript_files(str(root), max_depth=2)
        assert any(str(valid_file.name) in f for f in parser_found)
        assert not any("node_modules" in f for f in parser_found)
        assert not any(".git" in f for f in parser_found)
        assert not any(str(deep_file.resolve()) in f for f in parser_found)
