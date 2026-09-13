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

def test_cursor_and_aider_unsupported_status():
    cursor_det = CursorDetector()
    assert cursor_det.name == "Cursor"
    assert cursor_det.format_supported is False
    assert "SQLite" in cursor_det.support_note
    assert cursor_det.find_sessions() == []

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
