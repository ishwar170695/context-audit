import pytest
from context_audit.analyzer import (
    compute_token_entropy,
    extract_claims_locally,
    analyze_session,
    AuditResult
)
from context_audit.parser import Session

def test_entropy_computation():
    # Repetitive patterns of a single token should have 0.0 entropy
    low_ent = compute_token_entropy(" hello" * 100)
    assert low_ent == 0.0

    # More diverse strings should have higher entropy
    text_diverse = "The quick brown fox jumps over the lazy dog. 1234567890!@#$%"
    high_ent = compute_token_entropy(text_diverse)
    assert high_ent > 1.0

    # Empty string should yield 0.0
    assert compute_token_entropy("") == 0.0

def test_local_claims_extraction():
    # Port rule match
    text1 = "The auth service is on port 8080. We also know that database port is 5432."
    claims1 = extract_claims_locally(text1)
    assert len(claims1) == 2
    assert claims1[0]["entity"] == "auth service port"
    assert claims1[0]["value"] == "8080"
    assert claims1[1]["entity"] == "database port"
    assert claims1[1]["value"] == "5432"

    # Location rule match
    text2 = "The cache is located at /var/run/redis.sock and api is running at http://localhost:9000."
    claims2 = extract_claims_locally(text2)
    assert len(claims2) == 2
    assert claims2[0]["entity"] == "cache location"
    assert claims2[0]["value"] == "/var/run/redis.sock"
    assert claims2[1]["entity"] == "api location"
    assert claims2[1]["value"] == "http://localhost:9000"

    # Version rule match
    text3 = "We are using node version 18.2.0 and python version 3.12."
    claims3 = extract_claims_locally(text3)
    assert len(claims3) == 2
    assert claims3[0]["entity"] == "node version"
    assert claims3[0]["value"] == "18.2.0"
    assert claims3[1]["entity"] == "python version"
    assert claims3[1]["value"] == "3.12"

    # Ignore pronouns / common non-entities
    text4 = "It is running on port 3000."
    claims4 = extract_claims_locally(text4)
    assert len(claims4) == 0

def test_tool_entropy_anomaly_detection():
    # Build a session with a series of tool responses
    # Turn 1: normal outputs
    # Turn 2: normal outputs
    # Turn 3: normal outputs
    # Turn 4: highly repetitive output (anomaly spike/drop)
    history = [
        # Turn 1
        {"role": "user", "content": "hello"},
        {"role": "model", "content": "calling tool", "tool_calls": [{"name": "run_cmd"}]},
        {"role": "tool", "name": "run_cmd", "content": "total 40\ndrw-r--r--  3 root  root  4096 Jun 24 12:00 .\n-rw-r--r--  1 root  root   320 Jun 24 12:00 file.txt"},
        # Turn 2
        {"role": "model", "content": "calling tool again", "tool_calls": [{"name": "run_cmd"}]},
        {"role": "tool", "name": "run_cmd", "content": "total 32\ndrw-r--r--  2 root  root  2048 Jun 24 12:05 .\n-rw-r--r--  1 root  root   150 Jun 24 12:05 main.py"},
        # Turn 3
        {"role": "model", "content": "calling tool third time", "tool_calls": [{"name": "run_cmd"}]},
        {"role": "tool", "name": "run_cmd", "content": "total 48\ndrw-r--r--  4 root  root  8192 Jun 24 12:10 .\n-rw-r--r--  1 root  root   500 Jun 24 12:10 test.py"},
        # Turn 4 (Anomaly: totally different format or empty/repetitive error)
        {"role": "model", "content": "calling tool fourth time", "tool_calls": [{"name": "run_cmd"}]},
        {"role": "tool", "name": "run_cmd", "content": "ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR"}
    ]

    session = Session(
        system_instructions="You are a helper.",
        tools=[{"name": "run_cmd"}],
        history=history
    )

    result = analyze_session(session, entropy_threshold=1.5)
    
    assert len(result.tool_entropy_results) == 4
    # The fourth tool call (ERROR ERROR...) should have a very low entropy and trigger an anomaly spike
    # since the other outputs are standard directory listings with high token variation.
    anomalies = [r for r in result.tool_entropy_results if r["status"] == "Anomaly Spike"]
    assert len(anomalies) >= 1
    assert anomalies[0]["tool_name"] == "run_cmd"
    assert anomalies[0]["turn"] == 4

def test_belief_drift_detection():
    history = [
        # Turn 1: Auth is on 8080
        {"role": "user", "content": "Where is auth?"},
        {"role": "model", "content": "The auth service is on port 8080."},
        
        # Turn 2: General chat
        {"role": "user", "content": "ok thanks"},
        {"role": "model", "content": "You are welcome."},
        
        # Turn 3: Auth is on 9090 (Belief flip!)
        {"role": "user", "content": "What port is auth running on now?"},
        {"role": "model", "content": "The auth service is on port 9090."}
    ]

    session = Session(
        system_instructions="You are a helper.",
        tools=[],
        history=history
    )

    result = analyze_session(session)
    assert len(result.belief_drift_results) == 1
    drift = result.belief_drift_results[0]
    assert drift["entity"] == "auth service port"
    assert drift["first_claim"]["turn"] == 1
    assert drift["first_claim"]["value"] == "8080"
    assert drift["second_claim"]["turn"] == 3
    assert drift["second_claim"]["value"] == "9090"

def test_context_pressure_and_risk():
    # Create a long session where context size is large and oldest content contains critical guidelines
    sys_inst = "Guidelines: You must never write raw code blocks without explanations. This is a constraint."
    
    # Create history to generate enough tokens
    history = []
    # Turn 1 (contains task definition)
    history.append({"role": "user", "content": "Please implement a web server. This is our primary task."})
    history.append({"role": "model", "content": "I will do that."})
    
    # Lots of tool outputs and messages to inflate context
    for i in range(20):
        history.append({"role": "user", "content": f"check progress {i}"})
        history.append({"role": "tool", "name": "dummy", "content": "data " * 200}) # 200 tokens
        history.append({"role": "model", "content": f"ok turn {i}"})

    session = Session(
        system_instructions=sys_inst,
        tools=[{"name": "dummy"}],
        history=history
    )

    # Use a small context limit to trigger pressure risk
    result = analyze_session(session, context_limit=5000)
    
    assert len(result.context_pressure_map) > 0
    # Check that in later turns, the limit percentage is high and risk is flagged
    last_turn_pm = result.context_pressure_map[-1]
    assert last_turn_pm["total_tokens"] > 1000
    assert last_turn_pm["limit_percentage"] > 0
    
    # Ensure breakdown contains expected categories
    breakdown = last_turn_pm["breakdown_pct"]
    assert "system" in breakdown
    assert "tools" in breakdown
    assert "user" in breakdown
    assert "tool_outputs" in breakdown
    assert "reasoning" in breakdown
    
    # Risk flag check (high pressure and critical elements in oldest 20%)
    # Let's see if risk is flagged in the timeline
    risks = [pm for pm in result.context_pressure_map if pm["risk_flag"]]
    assert len(risks) > 0
    assert "System Prompt constraints" in risks[0]["oldest_content_info"]["high_value_details"]
