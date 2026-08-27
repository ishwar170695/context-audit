from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SemanticEvent:
    index: int
    category: str # "RESOURCE_ACCESSED", "RESOURCE_DISCOVERY", "COMMAND_EXECUTED", "UNKNOWN"
    method: str   # "READ", "EDIT", "SEARCH", "LIST", "COMMAND", "UNKNOWN"
    resource: str
    confidence: float

@dataclass
class RawEvent:
    index: int
    raw_type: str
    target: str
