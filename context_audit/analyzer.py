import hashlib
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional
from context_audit.events import SemanticEvent

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

def compute_token_entropy(text: str) -> float:
    """Computes Shannon entropy (base 2) in bits over token distribution."""
    if not text:
        return 0.0
    tokens = text.split()
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = len(tokens)
    if len(counts) <= 1:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values())

def extract_claims_locally(text: str) -> List[Dict[str, str]]:
    """Extracts factual/architectural claims using local heuristic patterns."""
    if not text:
        return []
    claims = []
    
    # Split sentences by period followed by whitespace/end, or newline/semicolon, or 'and'
    sentences = re.split(r'(?:\.\s+|\n+|;\s*|\band\s+)', text)
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
            
        # Strip common discourse prefixes from sentence
        sent_clean = re.sub(r'^(?:we\s+are\s+using|we\s+use|using|we\s+also\s+know\s+that|we\s+know\s+that|note\s+that|also|and)\s+', '', sent, flags=re.IGNORECASE).strip()



        # 1. Port rule
        port_match = re.search(r'([A-Za-z0-9_\-\s]{2,25}?)\s+(?:is\s+on|is\s+running\s+on|port\s+is|is\s+at)\s+(?:port\s+)?(\d{2,5})', sent_clean, re.IGNORECASE)
        if port_match:
            raw_entity = port_match.group(1).strip()
            val = port_match.group(2).strip().rstrip('.,;:')
            raw_entity = re.sub(r'^(?:the|a|an)\s+', '', raw_entity, flags=re.IGNORECASE).strip()
            if raw_entity.lower() not in ["it", "this", "that", "we", "they", "there"]:
                clean_entity = raw_entity
                if not clean_entity.lower().endswith("port"):
                    clean_entity = f"{clean_entity} port"
                claims.append({
                    "entity": clean_entity.lower(),
                    "value": val,
                    "source_sentence": sent
                })
                continue

        # 2. Location rule
        loc_match = re.search(r'([A-Za-z0-9_\-\s]{2,25}?)\s+(?:is\s+located\s+at|is\s+running\s+at|location\s+is)\s+([/\w\.\-:]+(?:\:[0-9]+)?)', sent_clean, re.IGNORECASE)
        if loc_match:
            raw_entity = loc_match.group(1).strip()
            val = loc_match.group(2).strip().rstrip('.,;:')
            raw_entity = re.sub(r'^(?:the|a|an)\s+', '', raw_entity, flags=re.IGNORECASE).strip()
            if raw_entity.lower() not in ["it", "this", "that", "we", "they", "there"]:
                clean_entity = raw_entity
                if not clean_entity.lower().endswith("location"):
                    clean_entity = f"{clean_entity} location"
                claims.append({
                    "entity": clean_entity.lower(),
                    "value": val,
                    "source_sentence": sent
                })
                continue

        # 3. Version rule
        ver_match = re.search(r'([A-Za-z0-9_\-\s]{2,25}?)\s+(?:version\s+is|version)\s+([\d\.]+)', sent_clean, re.IGNORECASE)
        if ver_match:
            raw_entity = ver_match.group(1).strip()
            val = ver_match.group(2).strip().rstrip('.,;:')
            raw_entity = re.sub(r'^(?:the|a|an)\s+', '', raw_entity, flags=re.IGNORECASE).strip()
            if raw_entity.lower() not in ["it", "this", "that", "we", "they", "there"]:
                clean_entity = raw_entity
                if not clean_entity.lower().endswith("version"):
                    clean_entity = f"{clean_entity} version"
                claims.append({
                    "entity": clean_entity.lower(),
                    "value": val,
                    "source_sentence": sent
                })
                continue

    return claims

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
        
        # Advanced Analysis
        self.tool_entropy_results = []
        self.belief_drift_results = []
        self.context_pressure_map = []

def analyze_session(
    session: Any, 
    input_price: float = 3.00, 
    cache_price: float = 0.30,
    context_limit: int = 100000,
    use_llm: bool = False,
    entropy_threshold: float = 2.0
) -> AuditResult:
    result = AuditResult()
    
    sys_prompt = getattr(session, "system_instructions", "") or ""
    sys_tokens = get_token_count(sys_prompt)
    
    # Tool schemas token count
    tools_tokens = {}
    total_tools_tokens = 0
    tools = getattr(session, "tools", []) or []
    for t in tools:
        tool_name = t.get("name", "unknown") if isinstance(t, dict) else getattr(t, "name", "unknown")
        tool_str = json.dumps(t, indent=2) if isinstance(t, dict) else str(t)
        tok = get_token_count(tool_str)
        tools_tokens[tool_name] = tok
        total_tools_tokens += tok
        
    history = getattr(session, "history", []) or []
    turns = []
    current_history_msgs = []
    
    for i, msg in enumerate(history):
        if msg.get("role") == "model":
            turns.append({
                "model_msg_index": i,
                "model_thinking": msg.get("content", ""),
                "tool_calls": msg.get("tool_calls", []) or [],
                "history_before": list(current_history_msgs)
            })
        current_history_msgs.append(msg)
        
    if not turns:
        turns.append({
            "model_msg_index": len(history),
            "model_thinking": "",
            "tool_calls": [],
            "history_before": list(history)
        })

    # Precompute tokens and md5 hashes once per message to avoid quadratic tokenization
    cached_msgs = []
    for i, msg in enumerate(history):
        role = msg.get("role", "user")
        content = msg.get("content", "") or ""
        tok = get_token_count(content)
        h = hashlib.md5(content.encode('utf-8')).hexdigest() if content else ""
        msg_name = f"{role}_message"
        if role == "tool":
            msg_name = f"tool_response:{msg.get('name', 'tool')}"
        cached_msgs.append({
            "index": i,
            "role": role,
            "name": msg.get("name", "tool"),
            "content": content,
            "tokens": tok,
            "hash": h,
            "block_name": msg_name
        })

    # Track block occurrences across turns for repetition analysis
    block_occurrences = {}
    
    def register_block(h: str, text: str, block_type: str, tok_count: int, name: str = ""):
        if not text or not h:
            return
        if h not in block_occurrences:
            block_occurrences[h] = {
                "text": text,
                "type": block_type,
                "name": name or block_type,
                "tokens": tok_count,
                "occurrences": 0
            }
        block_occurrences[h]["occurrences"] += 1

    sys_h = hashlib.md5(sys_prompt.encode('utf-8')).hexdigest() if sys_prompt else ""
    tool_blocks = []
    for t in tools:
        tool_name = t.get("name", "unknown") if isinstance(t, dict) else str(t)
        tool_str = json.dumps(t, indent=2) if isinstance(t, dict) else str(t)
        t_h = hashlib.md5(tool_str.encode('utf-8')).hexdigest()
        tool_blocks.append((t_h, tool_str, f"tool:{tool_name}", tools_tokens.get(tool_name, 0)))

    # Simulate token usage turn by turn
    timeline = []
    total_cumulative_tokens = 0
    prev_total_tokens = 0
    
    standard_input_cost = 0.0
    cached_input_cost = 0.0
    
    for t_idx, turn in enumerate(turns):
        history_before_len = len(turn["history_before"])
        msgs_before = cached_msgs[:history_before_len]
        
        turn_sys_tokens = sys_tokens
        turn_tool_tokens = total_tools_tokens
        
        turn_chat_tokens = 0
        turn_retrieval_tokens = 0
        
        # Register static blocks for this turn
        if sys_h:
            register_block(sys_h, sys_prompt, "System Prompt", sys_tokens)
        for t_h, tool_str, t_name, tok in tool_blocks:
            register_block(t_h, tool_str, "Tool Schema", tok, t_name)
            
        # Count history tokens
        for cm in msgs_before:
            register_block(cm["hash"], cm["content"], "Message", cm["tokens"], cm["block_name"])
            
            if cm["role"] == "tool":
                turn_retrieval_tokens += cm["tokens"]
            else:
                turn_chat_tokens += cm["tokens"]
                
        turn_total_tokens = turn_sys_tokens + turn_tool_tokens + turn_chat_tokens + turn_retrieval_tokens
        total_cumulative_tokens += turn_total_tokens
        standard_input_cost += (turn_total_tokens / 1_000_000) * input_price
        
        # 1. Static Prefix Caching Simulation (System + Tools only)
        static_prefix_tokens = turn_sys_tokens + turn_tool_tokens
        static_variable_tokens = turn_chat_tokens + turn_retrieval_tokens
        
        # 2. Dynamic Full Prefix Caching Simulation (Anthropic/OpenAI style: prior turns are cached)
        if t_idx == 0:
            dynamic_cached_tokens = 0
            dynamic_new_tokens = turn_total_tokens
            cached_input_cost += (turn_total_tokens / 1_000_000) * input_price
        else:
            dynamic_cached_tokens = prev_total_tokens
            dynamic_new_tokens = max(0, turn_total_tokens - prev_total_tokens)
            cached_input_cost += ((dynamic_cached_tokens / 1_000_000) * cache_price) + ((dynamic_new_tokens / 1_000_000) * input_price)
        
        delta = turn_total_tokens - prev_total_tokens if t_idx > 0 else turn_total_tokens
        
        delta_contributors = []
        if t_idx == 0:
            delta_contributors.append({"name": "System Prompt", "tokens": turn_sys_tokens})
            delta_contributors.append({"name": "Tool Schemas", "tokens": turn_tool_tokens})
            for cm in msgs_before:
                delta_contributors.append({"name": f"{cm['role'].capitalize()} Input", "tokens": cm["tokens"]})
        else:
            prev_len = len(turns[t_idx - 1]["history_before"])
            newly_added_cached = cached_msgs[prev_len:history_before_len]
            
            for cm in newly_added_cached:
                delta_contributors.append({"name": f"{cm['role'].capitalize()} message", "tokens": cm["tokens"]})
        
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
    for h, block in block_occurrences.items():
        if block["occurrences"] > 1:
            reused = (block["occurrences"] - 1) * block["tokens"]
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
        
    for t in tools:
        tool_name = t.get("name", "unknown") if isinstance(t, dict) else str(t)
        tok = tools_tokens.get(tool_name, 0)
        if len(turns) > 1:
            if tool_name in called_tools:
                repeated_sources.append({
                    "name": f"Tool Schema Repetition: {tool_name}",
                    "type": "Tool Schema",
                    "repeated_tokens": (len(turns) - 1) * tok,
                    "cost_usd": (((len(turns) - 1) * tok) / 1_000_000) * input_price,
                    "details": f"Repeated {len(turns)} times"
                })
            else:
                repeated_sources.append({
                    "name": f"Unused Tool Schema: {tool_name}",
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
    for t in tools:
        tool_name = t.get("name", "unknown") if isinstance(t, dict) else str(t)
        consumers.append({"name": f"Tool Schema: {tool_name}", "type": "Tool Schema", "tokens": tools_tokens.get(tool_name, 0)})
    for i, msg in enumerate(history):
        role = msg.get("role")
        content = msg.get("content", "")
        tok = get_token_count(content)
        name = f"Turn {i+1} message ({role})"
        if role == "tool":
            name = f"Tool output: {msg.get('name', 'tool')} (Turn {i+1})"
        consumers.append({"name": name, "type": "History Message", "tokens": tok})
        
    consumers.sort(key=lambda x: x["tokens"], reverse=True)
    result.top_consumers = consumers[:10]

    # Advanced Analysis 1: Tool Output Entropy & Anomaly Detection
    tool_entropy_list = []
    entropies_by_tool = defaultdict(list)
    
    current_turn = 0
    for step_idx, msg in enumerate(history):
        if msg.get("role") == "model":
            current_turn += 1
        elif msg.get("role") == "tool":
            t_name = msg.get("name", "tool")
            content = msg.get("content", "")
            ent = compute_token_entropy(content)
            tok_count = get_token_count(content)
            
            baseline = entropies_by_tool[t_name]
            if len(baseline) >= 2:
                mean_ent = statistics.mean(baseline)
                std_ent = statistics.stdev(baseline)
                if std_ent > 1e-4:
                    z_score = abs(ent - mean_ent) / std_ent
                else:
                    z_score = 0.0 if abs(ent - mean_ent) < 1e-4 else 3.0
                    
                status = "Anomaly Spike" if z_score >= entropy_threshold else "Normal"
            else:
                mean_ent = statistics.mean(baseline) if baseline else ent
                std_ent = 0.0
                z_score = 0.0
                status = "Insufficient baseline"
                
            entropies_by_tool[t_name].append(ent)
            
            tool_entropy_list.append({
                "turn": current_turn,
                "index": step_idx + 1,
                "tool_name": t_name,
                "token_count": tok_count,
                "entropy": ent,
                "baseline_mean": mean_ent,
                "baseline_std": std_ent,
                "anomaly_score": z_score,
                "status": status,
                "content_preview": (content[:40] + "...") if len(content) > 40 else content
            })
            
    result.tool_entropy_results = tool_entropy_list
    
    # Advanced Analysis 2: Belief Drift / Flip Detection
    claims_history = defaultdict(list)
    curr_turn = 1
    for msg in history:
        if msg.get("role") == "model":
            text = msg.get("content", "")
            extracted = extract_claims_locally(text)
            for c in extracted:
                claims_history[c["entity"]].append({
                    "turn": curr_turn,
                    "value": c["value"],
                    "source_sentence": c.get("source_sentence", "")
                })
            curr_turn += 1
        elif msg.get("role") == "user":
            pass

    drift_list = []
    for entity, claims in claims_history.items():
        if len(claims) > 1:
            first_c = claims[0]
            for later_c in claims[1:]:
                if later_c["value"] != first_c["value"]:
                    drift_list.append({
                        "entity": entity,
                        "first_claim": first_c,
                        "second_claim": later_c
                    })
                    break
    result.belief_drift_results = drift_list

    # Advanced Analysis 3: Context Pressure & Composition Map
    pressure_map = []
    for t in timeline:
        total_tok = t["total_tokens"]
        cap_pct = (total_tok / context_limit) * 100.0 if context_limit > 0 else 0.0
        
        # Calculate composition percentages
        bd = t["breakdown"]
        sys_pct = (bd["System Prompt"] / total_tok) * 100 if total_tok > 0 else 0
        tool_pct = (bd["Tool Schemas"] / total_tok) * 100 if total_tok > 0 else 0
        retrieval_pct = (bd["Retrieved Content"] / total_tok) * 100 if total_tok > 0 else 0
        chat_pct = (bd["Chat History"] / total_tok) * 100 if total_tok > 0 else 0
        
        user_pct = chat_pct * 0.7
        reasoning_pct = chat_pct * 0.3
        
        # Risk assessment: context pressure high + critical system guidelines or task definitions in oldest content
        risk_flag = False
        risk_reason = ""
        high_value_details = ""
        
        if total_tok > 1000 or cap_pct > 60:
            if "guidelines" in sys_prompt.lower() or "constraint" in sys_prompt.lower():
                risk_flag = True
                high_value_details = "System Prompt constraints"
                risk_reason = "Critical system constraints reside in oldest context under high pressure"
                
        pressure_map.append({
            "turn": t["turn"],
            "total_tokens": total_tok,
            "limit_percentage": cap_pct,
            "breakdown_pct": {
                "system": sys_pct,
                "tools": tool_pct,
                "user": user_pct,
                "tool_outputs": retrieval_pct,
                "reasoning": reasoning_pct
            },
            "risk_flag": risk_flag,
            "risk_reason": risk_reason,
            "oldest_content_info": {
                "high_value_details": high_value_details
            }
        })
    result.context_pressure_map = pressure_map
    
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
        self.overhead_pcts = []
        
        self.repeated_blocks = []
        
        self.buckets = {
            "< 5k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []},
            "5k - 20k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []},
            "20k - 50k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []},
            "> 50k tokens": {"count": 0, "reuse_ratios": [], "peak_sizes": [], "cumulative_tokens": [], "savings": []}
        }

def run_benchmark(
    target: Any, 
    input_price: float = 3.00, 
    cache_price: float = 0.30
) -> BenchmarkSummary:
    from context_audit.parser import find_transcript_files, load_session
    
    summary = BenchmarkSummary()
    if isinstance(target, (list, tuple, set)):
        files = list(target)
    elif isinstance(target, str):
        if os.path.isfile(target):
            files = [target]
        else:
            files = find_transcript_files(target)
    else:
        files = []
    
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
            
            overhead_tok = result.category_breakdown.get("System Prompt", 0) + result.category_breakdown.get("Tool Schemas", 0)
            overhead_pct = (overhead_tok / result.final_context_size * 100) if result.final_context_size > 0 else 0.0
            summary.overhead_pcts.append(overhead_pct)
            
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
        except Exception as e:
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

class BehaviorAnalyzer:
    def __init__(self, events: List[SemanticEvent]):
        self.events = events
        
    def analyze(self) -> Dict[str, Any]:
        if not self.events:
            return {}

        file_reads = defaultdict(list)
        
        for event in self.events:
            if event.method == "READ" and event.category == "RESOURCE_ACCESSED":
                file_reads[event.resource].append(event.index)
                
        unique_files_read = len(file_reads)
        total_reads = sum(len(reads) for reads in file_reads.values())
        rediscovery_ratio = total_reads / max(1, unique_files_read)

        all_gaps = []
        for reads in file_reads.values():
            if len(reads) > 1:
                for i in range(1, len(reads)):
                    all_gaps.append(reads[i] - reads[i-1])

        session_median_gap = statistics.median(all_gaps) if all_gaps else 0
        recovery_threshold = max(5, session_median_gap * 2)

        total_recovery_reads = 0
        for reads in file_reads.values():
            if len(reads) > 1:
                for i in range(1, len(reads)):
                    if (reads[i] - reads[i-1]) > recovery_threshold:
                        total_recovery_reads += 1

        navigation_loops = 0
        for i, event in enumerate(self.events):
            if event.method == "READ" and i >= 3:
                prev1 = self.events[i-1]
                prev2 = self.events[i-2]
                prev3 = self.events[i-3]
                if prev1.method == "SEARCH" and prev2.method == "READ" and prev3.method == "SEARCH":
                    navigation_loops += 1
            if event.method == "LIST" and i >= 1:
                if self.events[i-1].method == "LIST":
                    navigation_loops += 1

        return {
            "unique_files_read": unique_files_read,
            "total_reads": total_reads,
            "rediscovery_ratio": rediscovery_ratio,
            "session_median_gap": session_median_gap,
            "recovery_threshold_used": recovery_threshold,
            "total_recovery_reads": total_recovery_reads,
            "navigation_loops": navigation_loops,
            "total_events": len(self.events)
        }
