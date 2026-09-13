import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

class AgentDetector:
    name: str = "BaseAgent"
    format_name: str = "Unknown"
    format_supported: bool = True
    support_note: str = ""

    def is_installed(self) -> bool:
        """Determines if the agent tool or its configuration exists locally."""
        return False

    def get_candidate_paths(self) -> List[Path]:
        """Returns candidate directories or files where sessions might be stored."""
        return []

    def find_sessions(self) -> List[str]:
        """Finds parseable session log files for this agent."""
        return []

    def inspect(self) -> Dict[str, Any]:
        """Returns a structured diagnostic dict for this agent."""
        installed = self.is_installed()
        sessions = self.find_sessions() if installed and self.format_supported else []
        
        if not installed:
            status_summary = "not detected"
        elif not self.format_supported:
            status_summary = self.support_note or "unsupported format"
        elif len(sessions) == 0:
            status_summary = "0 candidates"
        else:
            status_summary = f"{len(sessions)} session(s) found"

        return {
            "name": self.name,
            "installed": installed,
            "format_name": self.format_name,
            "format_supported": self.format_supported,
            "support_note": self.support_note,
            "status_summary": status_summary,
            "candidate_paths": [str(p) for p in self.get_candidate_paths()],
            "sessions": sessions,
        }

def _scan_for_transcripts(paths: List[Path]) -> List[str]:
    """Helper to scan directories for transcript.jsonl and session.json files."""
    discovered = []
    seen = set()
    
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            fname_lower = p.name.lower()
            if not (fname_lower.endswith('_full.jsonl') or fname_lower.endswith('.full.jsonl')):
                if fname_lower.endswith('.jsonl') or fname_lower.endswith('.json'):
                    abs_p = str(p.resolve())
                    if abs_p not in seen:
                        seen.add(abs_p)
                        discovered.append(abs_p)
            continue
            
        for root, _, filenames in os.walk(str(p)):
            for filename in filenames:
                fname_lower = filename.lower()
                if fname_lower.endswith('_full.jsonl') or fname_lower.endswith('.full.jsonl'):
                    continue
                if fname_lower.endswith('.jsonl') or fname_lower == 'transcript.jsonl':
                    full_path = os.path.abspath(os.path.join(root, filename))
                    if full_path not in seen:
                        seen.add(full_path)
                        discovered.append(full_path)
                elif fname_lower == 'session.json' or (fname_lower.endswith('.json') and 'session' in fname_lower):
                    full_path = os.path.abspath(os.path.join(root, filename))
                    if full_path not in seen:
                        seen.add(full_path)
                        discovered.append(full_path)
    return discovered

class AntigravityDetector(AgentDetector):
    name = "Antigravity"
    format_name = "JSONL Transcripts"
    format_supported = True
    support_note = "Supported"

    def is_installed(self) -> bool:
        home = Path.home()
        candidates = [
            home / ".gemini" / "antigravity-ide",
            home / ".gemini",
        ]
        return any(c.exists() for c in candidates)

    def get_candidate_paths(self) -> List[Path]:
        home = Path.home()
        return [
            home / ".gemini" / "antigravity-ide" / "brain",
            home / ".gemini" / "antigravity-ide" / "logs",
        ]

    def find_sessions(self) -> List[str]:
        return _scan_for_transcripts(self.get_candidate_paths())

class ClaudeCodeDetector(AgentDetector):
    name = "Claude Code"
    format_name = "JSONL Transcripts"
    format_supported = True
    support_note = "Supported"

    def is_installed(self) -> bool:
        if shutil.which("claude") is not None:
            return True
        home = Path.home()
        return (home / ".claude").exists()

    def get_candidate_paths(self) -> List[Path]:
        home = Path.home()
        return [
            home / ".claude" / "projects",
            home / ".claude" / "transcripts",
            home / ".claude" / "chats",
            home / ".claude",
        ]

    def find_sessions(self) -> List[str]:
        return _scan_for_transcripts(self.get_candidate_paths())

class CodexDetector(AgentDetector):
    name = "Codex"
    format_name = "JSON / JSONL logs"
    format_supported = True
    support_note = "Experimental"

    def is_installed(self) -> bool:
        if shutil.which("codex") is not None:
            return True
        home = Path.home()
        return (home / ".codex").exists() or (home / ".openai").exists()

    def get_candidate_paths(self) -> List[Path]:
        home = Path.home()
        return [
            home / ".codex",
            home / ".openai",
        ]

    def find_sessions(self) -> List[str]:
        return _scan_for_transcripts(self.get_candidate_paths())

class CursorDetector(AgentDetector):
    name = "Cursor"
    format_name = "SQLite (state.vscdb)"
    format_supported = False
    support_note = "unsupported format (SQLite state.vscdb storage)"

    def is_installed(self) -> bool:
        if shutil.which("cursor") is not None:
            return True
        home = Path.home()
        appdata = os.environ.get("APPDATA")
        candidates = [
            home / ".cursor",
            home / ".cursor-tutor",
            Path(appdata) / "Cursor" if appdata else None,
            home / "Library" / "Application Support" / "Cursor",
            home / ".config" / "Cursor",
        ]
        return any(c and c.exists() for c in candidates)

    def get_candidate_paths(self) -> List[Path]:
        home = Path.home()
        appdata = os.environ.get("APPDATA")
        paths = [
            home / ".cursor",
            Path(appdata) / "Cursor" if appdata else None,
            home / "Library" / "Application Support" / "Cursor",
            home / ".config" / "Cursor",
        ]
        return [p for p in paths if p and p.exists()]

    def find_sessions(self) -> List[str]:
        # Cursor currently stores conversation history inside SQLite workspaceStorage vscdb files
        return []

class AiderDetector(AgentDetector):
    name = "Aider"
    format_name = "Markdown Chat Log"
    format_supported = False
    support_note = "unsupported format (Markdown chat history)"

    def is_installed(self) -> bool:
        if shutil.which("aider") is not None:
            return True
        home = Path.home()
        candidates = [
            home / ".aider.chat.history.md",
            home / ".aider.input.history",
            home / ".aider",
            Path(".aider.chat.history.md"),
            Path(".aider.input.history"),
        ]
        return any(c.exists() for c in candidates)

    def get_candidate_paths(self) -> List[Path]:
        home = Path.home()
        candidates = [
            home / ".aider.chat.history.md",
            home / ".aider.input.history",
            home / ".aider",
            Path(".aider.chat.history.md"),
            Path(".aider.input.history"),
        ]
        return [c for c in candidates if c.exists()]

    def find_sessions(self) -> List[str]:
        # Aider records chat history as Markdown files, not turn-based JSON/JSONL messages
        return []

class WorkspaceDetector(AgentDetector):
    name = "Local Workspace"
    format_name = "JSONL / Session JSON"
    format_supported = True
    support_note = "Supported"

    def is_installed(self) -> bool:
        return True

    def get_candidate_paths(self) -> List[Path]:
        return [Path(".").resolve()]

    def find_sessions(self) -> List[str]:
        return _scan_for_transcripts(self.get_candidate_paths())

DEFAULT_DETECTORS = [
    WorkspaceDetector(),
    AntigravityDetector(),
    ClaudeCodeDetector(),
    CodexDetector(),
    CursorDetector(),
    AiderDetector(),
]

class DiscoveryReport:
    def __init__(self, agent_reports: List[Dict[str, Any]], all_sessions: List[str]):
        self.agent_reports = agent_reports
        self.all_sessions = all_sessions

    @property
    def has_sessions(self) -> bool:
        return len(self.all_sessions) > 0

    @property
    def detected_agents(self) -> List[Dict[str, Any]]:
        return [r for r in self.agent_reports if r["installed"]]

def run_discovery(detectors: Optional[List[AgentDetector]] = None, limit: Optional[int] = 20) -> DiscoveryReport:
    """Runs discovery across all registered detectors and collects session files sorted by mtime."""
    if detectors is None:
        detectors = DEFAULT_DETECTORS

    agent_reports = []
    all_sessions = []
    seen = set()

    for detector in detectors:
        report = detector.inspect()
        agent_reports.append(report)
        for s in report.get("sessions", []):
            if s not in seen:
                seen.add(s)
                all_sessions.append(s)

    # Sort all found sessions newest first
    all_sessions.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

    if limit is not None and limit > 0:
        all_sessions = all_sessions[:limit]

    return DiscoveryReport(agent_reports=agent_reports, all_sessions=all_sessions)
