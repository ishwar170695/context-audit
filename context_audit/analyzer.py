import hashlib
import json
import os
import re
import statistics
from typing import Dict, List, Any, Tuple, Set

# Try importing tiktoken, define fallback if not present
try:
    import tiktoken
    _ENCODER = tiktoken.get_encoding("cl100k_base")
    def get_token_count(text: str) -> int:
        if not text:
            return 0
        return len(_ENCODER.encode(text))
    HAS_TIKTOKEN = True
except ImportError:
    def get_token_count(text: str) -> int:
        if not text:
            return 0
        # Fallback estimation: ~4 chars per token for English text
        return max(1, int(len(text) * 0.26))
    HAS_TIKTOKEN = False

class AuditResult:
    def __init__(self):
        self.total_tokens_across_session = 0
        self.peak_context_size = 0
        self.final_context_size = 0
        self.category_breakdown = {
            "System Prompt": 0,
            "Tool Schemas": 0,
            "Chat History": 0,
            "Retrieved Content": 0
        }
        self.timeline = []  # List of dicts representing turns
        self.repeated_blocks = []  # List of dicts representing repeated text blocks
        self.block_occurrences = {}  # Store raw occurrences for benchmarking
        self.top_consumers = []  # List of dicts representing largest components
        self.top_repeated_sources = []  # List of dicts representing largest repeated token counts
        self.context_reuse_ratio = 0.0  # Percentage of tokens that were previously seen blocks
        
        # Cost Metrics
        self.standard_input_cost = 0.0
        self.cached_input_cost = 0.0
        self.potential_cache_savings = 0.0
        self.cache_savings_percentage = 0.0

def analyze_session(
    session: Any, 
    input_price: float = 3.00, 
    cache_price: float = 0.30
) -> AuditResult:
    result = AuditResult()
    
    sys_prompt = session.system_instructions
    sys_tokens = get_token_count(sys_prompt)
    
    # Tool schemas token count
    tools_tokens = {}
    total_tools_tokens = 0
    for t in session.tools:
        tool_str = json.dumps(t, indent=2)
        tok = get_token_count(tool_str)
        tools_tokens[t["name"]] = tok
        total_tools_tokens += tok
        
    # Analyze message by message to build turn-by-turn context
    turns = []
    current_history_msgs = []
    
    for i, msg in enumerate(session.history):
        if msg.get("role") == "model":
            turns.append({
                "model_msg_index": i,
                "model_thinking": msg.get("content", ""),
                "tool_calls": msg.get("tool_calls", []),
                "history_before": list(current_history_msgs)
            })
        current_history_msgs.append(msg)
        
    if not turns:
        turns.append({
            "model_msg_index": len(session.history),
            "model_thinking": "",
            "tool_calls": [],
            "history_before": list(session.history)
        })

    # Track block occurrences across turns for repetition analysis
    block_occurrences = {} # hash -> {text, type, tokens, occurrences}
    
    def register_block(text: str, block_type: str, name: str = ""):
        if not text:
            return
        h = hashlib.md5(text.encode('utf-8')).hexdigest()
        if h not in block_occurrences:
            block_occurrences[h] = {
                "text": text,
                "type": block_type,
                "name": name or block_type,
                "tokens": get_token_count(text),
                "occurrences": 0
            }
        block_occurrences[h]["occurrences"] += 1

    # Simulate token usage turn by turn
    timeline = []
    total_cumulative_tokens = 0
    prev_total_tokens = 0
    
    standard_input_cost = 0.0
    cached_input_cost = 0.0
    
    for t_idx, turn in enumerate(turns):
        history_before = turn["history_before"]
        
        turn_sys_tokens = sys_tokens
        turn_tool_tokens = total_tools_tokens
        
        turn_chat_tokens = 0
        turn_retrieval_tokens = 0
        
        # Register static blocks for this turn
        register_block(sys_prompt, "System Prompt")
        for t in session.tools:
            tool_str = json.dumps(t, indent=2)
            register_block(tool_str, "Tool Schema", f"tool:{t['name']}")
            
        # Count history tokens
        for msg in history_before:
            role = msg.get("role")
            content = msg.get("content", "")
            msg_tokens = get_token_count(content)
            
            msg_name = f"{role}_message"
            if role == "tool":
                msg_name = f"tool_response:{msg.get('name', 'tool')}"
                
            register_block(content, "Message", msg_name)
            
            if role == "tool":
                turn_retrieval_tokens += msg_tokens
            else:
                turn_chat_tokens += msg_tokens
                
        turn_total_tokens = turn_sys_tokens + turn_tool_tokens + turn_chat_tokens + turn_retrieval_tokens
        total_cumulative_tokens += turn_total_tokens
        
        # Cost Calculations
        standard_input_cost += (turn_total_tokens / 1_000_000) * input_price
        
        # Prompt caching simulation
        prefix_tokens = turn_sys_tokens + turn_tool_tokens
        variable_tokens = turn_chat_tokens + turn_retrieval_tokens
        
        if t_idx == 0:
            cached_input_cost += (turn_total_tokens / 1_000_000) * input_price
        else:
            cached_input_cost += ((prefix_tokens / 1_000_000) * cache_price) + ((variable_tokens / 1_000_000) * input_price)
        
        delta = turn_total_tokens - prev_total_tokens if t_idx > 0 else turn_total_tokens
        
        delta_contributors = []
        if t_idx == 0:
            delta_contributors.append({"name": "System Prompt", "tokens": turn_sys_tokens})
            delta_contributors.append({"name": "Tool Schemas", "tokens": turn_tool_tokens})
            for msg in history_before:
                role = msg.get("role")
                t_count = get_token_count(msg.get("content", ""))
                delta_contributors.append({"name": f"{role.capitalize()} Input", "tokens": t_count})
        else:
            prev_turn = turns[t_idx - 1]
            prev_len = len(prev_turn["history_before"])
            newly_added_msgs = history_before[prev_len:]
            
            for msg in newly_added_msgs:
                role = msg.get("role")
                t_count = get_token_count(msg.get("content", ""))
                delta_contributors.append({"name": f"{role.capitalize()} message", "tokens": t_count})
        
        delta_contributors.sort(key=lambda x: x["tokens"], reverse=True)
        
        timeline.append({
            "turn": t_idx + 1,
            "total_tokens": turn_total_tokens,
            "delta": delta,
            "breakdown": {
                "System Prompt": turn_sys_tokens,
                "Tool Schemas": turn_tool_tokens,
                "Chat History": turn_chat_tokens,
                "Retrieved Content": turn_retrieval_tokens
            },
            "contributors": delta_contributors
        })
        
        result.category_breakdown["System Prompt"] += turn_sys_tokens
        result.category_breakdown["Tool Schemas"] += turn_tool_tokens
        result.category_breakdown["Chat History"] += turn_chat_tokens
        result.category_breakdown["Retrieved Content"] += turn_retrieval_tokens
        
        prev_total_tokens = turn_total_tokens
        
    result.total_tokens_across_session = total_cumulative_tokens
    result.timeline = timeline
    result.block_occurrences = block_occurrences
    
    # Calculate peak & final sizes
    if timeline:
        result.peak_context_size = max(t["total_tokens"] for t in timeline)
        result.final_context_size = timeline[-1]["total_tokens"]
    
    result.standard_input_cost = standard_input_cost
    result.cached_input_cost = cached_input_cost
    result.potential_cache_savings = max(0.0, standard_input_cost - cached_input_cost)
    if standard_input_cost > 0:
        result.cache_savings_percentage = (result.potential_cache_savings / standard_input_cost) * 100
        
    # Process repeated blocks
    repeated_list = []
    total_repeated_tokens = 0
    
    for h, block in block_occurrences.items():
        if block["occurrences"] > 1:
            reused = (block["occurrences"] - 1) * block["tokens"]
            total_repeated_tokens += reused
            repeated_list.append({
                "name": block["name"],
                "type": block["type"],
                "occurrences": block["occurrences"],
                "tokens_per_occurrence": block["tokens"],
                "total_cost": block["occurrences"] * block["tokens"],
                "repeated_tokens": reused,
                "repeated_cost_usd": (reused / 1_000_000) * input_price,
                "text": block["text"]
            })
            
    repeated_list.sort(key=lambda x: x["repeated_tokens"], reverse=True)
    result.repeated_blocks = repeated_list
    
    # Process repeated blocks for waste analysis (top repeated sources)
    called_tools = set()
    for turn in turns:
        for tc in turn["tool_calls"]:
            called_tools.add(tc.get("name"))

    repeated_sources = []
    if len(turns) > 1:
        repeated_sources.append({
            "name": "System Prompt Repetition",
            "type": "System Prompt",
            "repeated_tokens": (len(turns) - 1) * sys_tokens,
            "cost_usd": (((len(turns) - 1) * sys_tokens) / 1_000_000) * input_price,
            "details": f"Repeated {len(turns)} times across turns"
        })
        
    for t in session.tools:
        name = t["name"]
        tok = tools_tokens.get(name, 0)
        if len(turns) > 1:
            if name in called_tools:
                repeated_sources.append({
                    "name": f"Tool Schema Repetition: {name}",
                    "type": "Tool Schema",
                    "repeated_tokens": (len(turns) - 1) * tok,
                    "cost_usd": (((len(turns) - 1) * tok) / 1_000_000) * input_price,
                    "details": f"Repeated {len(turns)} times"
                })
            else:
                repeated_sources.append({
                    "name": f"Unused Tool Schema: {name}",
                    "type": "Tool Schema",
                    "repeated_tokens": len(turns) * tok,
                    "cost_usd": ((len(turns) * tok) / 1_000_000) * input_price,
                    "details": "Tool was declared but never called"
                })
                
    for block in repeated_list:
        if block["type"] == "Message":
            repeated_sources.append({
                "name": f"Message Repetition: {block['name']}",
                "type": "Message History",
                "repeated_tokens": block["repeated_tokens"],
                "cost_usd": block["repeated_cost_usd"],
                "details": f"Repeated {block['occurrences']} times"
            })
            
    repeated_sources.sort(key=lambda x: x["repeated_tokens"], reverse=True)
    result.top_repeated_sources = repeated_sources[:10]
    
    total_reused = sum(r["repeated_tokens"] for r in repeated_sources)
    if total_cumulative_tokens > 0:
        result.context_reuse_ratio = (total_reused / total_cumulative_tokens) * 100
        
    # Top Context Consumers
    consumers = []
    consumers.append({"name": "System Prompt", "type": "System Prompt", "tokens": sys_tokens})
    for t in session.tools:
        name = t["name"]
        consumers.append({"name": f"Tool Schema: {name}", "type": "Tool Schema", "tokens": tools_tokens.get(name, 0)})
    for i, msg in enumerate(session.history):
        role = msg.get("role")
        content = msg.get("content", "")
        tok = get_token_count(content)
        name = f"Turn {i+1} message ({role})"
        if role == "tool":
            name = f"Tool output: {msg.get('name', 'tool')} (Turn {i+1})"
        consumers.append({"name": name, "type": "History Message", "tokens": tok})
        
    consumers.sort(key=lambda x: x["tokens"], reverse=True)
    result.top_consumers = consumers[:10]
    
    return result

class BenchmarkSummary:
    def __init__(self):
        self.total_sessions = 0
        
        self.cumulative_tokens = []
        self.peak_context_sizes = []
        self.final_context_sizes = []
        self.reuse_ratios = []
        self.turn_counts = []
        self.file_sizes = []
        
        self.standard_costs = []
        self.cached_costs = []
        self.savings_list = []
        
        self.repeated_blocks = []
        
        self.buckets = {
            "< 5k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []},
            "5k - 20k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []},
            "20k - 50k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []},
            "> 50k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []}
        }

def run_benchmark(
    directory_path: str, 
    input_price: float = 3.00, 
    cache_price: float = 0.30
) -> BenchmarkSummary:
    from context_audit.parser import find_transcript_files, load_session
    
    summary = BenchmarkSummary()
    files = find_transcript_files(directory_path)
    
    if not files:
        return summary
        
    parsed_count = 0
    global_blocks = {}
    
    for f_path in files:
        try:
            session = load_session(f_path)
            result = analyze_session(session, input_price=input_price, cache_price=cache_price)
            
            summary.cumulative_tokens.append(result.total_tokens_across_session)
            summary.peak_context_sizes.append(result.peak_context_size)
            summary.final_context_sizes.append(result.final_context_size)
            summary.reuse_ratios.append(result.context_reuse_ratio)
            summary.turn_counts.append(len(result.timeline))
            summary.file_sizes.append(os.path.getsize(f_path))
            
            summary.standard_costs.append(result.standard_input_cost)
            summary.cached_costs.append(result.cached_input_cost)
            summary.savings_list.append(result.potential_cache_savings)
            
            final_size = result.final_context_size
            if final_size < 5000:
                b_name = "< 5k tokens"
            elif final_size < 20000:
                b_name = "5k - 20k tokens"
            elif final_size < 50000:
                b_name = "20k - 50k tokens"
            else:
                b_name = "> 50k tokens"
                
            summary.buckets[b_name]["count"] += 1
            summary.buckets[b_name]["reuse_ratios"].append(result.context_reuse_ratio)
            summary.buckets[b_name]["peak_sizes"].append(result.peak_context_size)
            summary.buckets[b_name]["cumulative_tokens"].append(result.total_tokens_across_session)
            summary.buckets[b_name]["savings"].append(result.potential_cache_savings)
            
            for h, block in result.block_occurrences.items():
                if h not in global_blocks:
                    global_blocks[h] = {
                        "text": block["text"],
                        "type": block["type"],
                        "name": block["name"],
                        "tokens": block["tokens"],
                        "occurrences_per_file": {}
                    }
                global_blocks[h]["occurrences_per_file"][f_path] = block["occurrences"]
            
            parsed_count += 1
        except Exception:
            continue
            
    summary.total_sessions = parsed_count
    
    repeated_blocks_list = []
    for h, g_block in global_blocks.items():
        sessions_count = len(g_block["occurrences_per_file"])
        total_occurrences = sum(g_block["occurrences_per_file"].values())
        
        total_repeated = 0
        for f_path, count in g_block["occurrences_per_file"].items():
            if count > 1:
                total_repeated += (count - 1) * g_block["tokens"]
                
        if total_occurrences > 1:
            repeated_blocks_list.append({
                "name": g_block["name"],
                "type": g_block["type"],
                "tokens_per_occurrence": g_block["tokens"],
                "total_occurrences": total_occurrences,
                "sessions_count": sessions_count,
                "total_repeated": total_repeated,
                "total_repeated_cost_usd": (total_repeated / 1_000_000) * input_price,
                "text": g_block["text"]
            })
            
    repeated_blocks_list.sort(key=lambda x: x["total_repeated"], reverse=True)
    summary.repeated_blocks = repeated_blocks_list
    
    return summary
