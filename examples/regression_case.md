# Experiment 2: Non-Disk-Backed User Preferences (Regression Case)

This case study demonstrates the critical regression that occurs when chat history is pruned blindly without distinguishing between technical state (disk-backed) and social/design preferences (conversation-only).

---

## 🧪 Setup: The Prompt
We replayed a hypothetical **Turn 124** prompt inside our developer session:
> *"Should we add an LLM-as-a-judge step to score the relevance of repeated blocks, and should we generate a glassmorphic HTML dashboard?"*

We evaluated the model's response under two configurations.

---

## 📊 Side-by-Side Comparison

| Configuration A: Full History Context (No Pruning) | Configuration B: Naively Pruned Context (Last 15 Turns) |
| :--- | :--- |
| **Context Size**: ~47.0k tokens (entire conversation history) | **Context Size**: ~5.0k tokens (System + Tools + Turns 108–123) |
| **Model Response**: | **Model Response**: |
| *"We should avoid both. In Turns 20 and 30, we explicitly decided to drop the HTML dashboard to avoid over-engineering, and we banned LLM-as-a-judge/AI-judging to keep the tool fast, deterministic, and objective (relying strictly on MD5 exact block hashing)."* | *"Yes, that is a great idea! We can use a lightweight model like GPT-4o-mini to score the semantic relevance of blocks on a scale of 1-5, and we can output a beautiful interactive HTML dashboard with glassmorphism to make the cost summaries highly visual."* |
| **Result**: **CORRECT & ALIGNED** | **Result**: **CRITICAL REGRESSION** |
| **Verdict**: The model retains social constraints and user preferences that only existed in the chat history. | **Verdict**: The model reverts to generic AI helpfulness, suggesting exactly the features the user explicitly rejected. |

---

## 💡 The Dividing Line: Technical State vs. Social State

1. **Technical State is Disk-Backed**
   - *Examples*: Command outputs, code files, test suites, directory listings.
   - *Verdict*: **Candidate for compaction** (often recoverable from the workspace). Once code is written or a command is run, the workspace reflects the final state. An agent can always query the disk to reconstruct technical details. Technical history is often recoverable from the workspace and therefore a candidate for compaction (representing over 80% of the session token footprint in this session).

2. **Social State is Not Disk-Backed**
   - *Examples*: User preferences, constraints, style guides, rejected choices, design philosophies.
   - *Verdict*: **Must persist**. These preferences reside *only* in the conversational thread. If you strip them, the agent has no way to retrieve them from the environment, leading to alignment regressions.
