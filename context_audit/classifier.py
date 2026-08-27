from typing import List
from context_audit.events import RawEvent, SemanticEvent

def classify_raw_event(raw: RawEvent) -> List[SemanticEvent]:
    # Antigravity native tools
    if raw.raw_type in ["view_file", "read_file"]:
        return [SemanticEvent(raw.index, "RESOURCE_ACCESSED", "READ", raw.target, 1.0)]
    elif raw.raw_type in ["replace_file_content", "multi_replace_file_content", "write_to_file"]:
        return [SemanticEvent(raw.index, "RESOURCE_ACCESSED", "EDIT", raw.target, 1.0)]
    elif raw.raw_type == "grep_search":
        return [SemanticEvent(raw.index, "RESOURCE_DISCOVERY", "SEARCH", raw.target, 1.0)]
    elif raw.raw_type == "list_dir":
        return [SemanticEvent(raw.index, "RESOURCE_DISCOVERY", "LIST", raw.target, 1.0)]
        
    # Shell commands (Antigravity's run_command or Claude's Bash)
    if raw.raw_type in ["run_command", "Bash"]:
        cmd_str = raw.target.strip()
        if not cmd_str:
            return []
            
        events = []
        # split by pipe or && to handle chains
        tokens = cmd_str.replace(";", " ; ").replace("|", " | ").replace("&&", " && ").split()
        
        current_cmd = []
        for token in tokens:
            if token in ["|", "&&", ";"]:
                if current_cmd:
                    events.extend(classify_bash_command(raw.index, current_cmd))
                current_cmd = []
            else:
                current_cmd.append(token)
        if current_cmd:
            events.extend(classify_bash_command(raw.index, current_cmd))
            
        if not events:
            # Fallback
            events.append(SemanticEvent(raw.index, "COMMAND_EXECUTED", "COMMAND", cmd_str, 1.0))
            
        return events

    # Unknown
    return [SemanticEvent(raw.index, "UNKNOWN", "UNKNOWN", raw.target, 0.0)]

def classify_bash_command(index: int, tokens: List[str]) -> List[SemanticEvent]:
    if not tokens:
        return []
    
    prog = tokens[0]
    
    # Read
    if prog in ["cat", "less", "head", "tail", "bat", "more"]:
        resource = tokens[1] if len(tokens) > 1 else ""
        return [SemanticEvent(index, "RESOURCE_ACCESSED", "READ", resource, 0.9)]
        
    # Search
    if prog in ["grep", "rg", "ag", "ack"]:
        query = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        return [SemanticEvent(index, "RESOURCE_DISCOVERY", "SEARCH", query, 0.9)]
    
    # Git
    if prog == "git":
        subcmd = tokens[1] if len(tokens) > 1 else ""
        if subcmd == "grep":
            query = " ".join(tokens[2:]) if len(tokens) > 2 else ""
            return [SemanticEvent(index, "RESOURCE_DISCOVERY", "SEARCH", query, 0.95)]
        if subcmd in ["ls-files", "ls-tree"]:
            return [SemanticEvent(index, "RESOURCE_DISCOVERY", "LIST", "git", 0.9)]
        return [SemanticEvent(index, "COMMAND_EXECUTED", "COMMAND", " ".join(tokens), 1.0)]

    # List
    if prog in ["ls", "tree"]:
        target = tokens[1] if len(tokens) > 1 else "."
        return [SemanticEvent(index, "RESOURCE_DISCOVERY", "LIST", target, 0.9)]
    if prog in ["find", "fd"]:
        target = tokens[1] if len(tokens) > 1 else "."
        return [SemanticEvent(index, "RESOURCE_DISCOVERY", "LIST", target, 0.8)]
        
    # Edit
    if prog in ["sed", "awk", "mv", "cp", "rm", "mkdir", "touch", "echo", "tee", "perl"]:
        target = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        return [SemanticEvent(index, "RESOURCE_ACCESSED", "EDIT", target, 0.8)]
        
    # Python/Node (often commands, sometimes scripts)
    if prog in ["python", "python3", "node", "npm", "go", "cargo", "pytest", "make"]:
        return [SemanticEvent(index, "COMMAND_EXECUTED", "COMMAND", " ".join(tokens), 1.0)]
        
    # Default unclassified
    return [SemanticEvent(index, "COMMAND_EXECUTED", "COMMAND", " ".join(tokens), 1.0)]
