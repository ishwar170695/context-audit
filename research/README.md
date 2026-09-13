# context-audit Research & Methodology

This directory contains standalone research scripts, behavioral profiling tools, and reproducible benchmarks used in the public empirical analysis (including the dev.to article and benchmark findings).

---

## 🔬 Contents

### 1. Entropy Distribution Analysis (`entropy_analysis.py`)
Computes Shannon entropy across turns and executes a Mann-Whitney U test comparing tool outputs against conversational turns.
* **Core Finding**: Tool output turns are statistically distinct from user/model turns ($p < 0.0001$), characterized by lower token entropy due to repetitive compiler output and structured formatting.
* **Usage**:
  ```bash
  python research/entropy_analysis.py --sessions-dir sample_data/ --out-dir research/entropy_output/
  ```

### 2. Action Sequence & Cross-Session Aggregator (`aggregate_stats.py`)
Aggregates action sequences (file reads, edits, greps, commands) across transcript files to evaluate macroscopic session trends.
* **Usage**:
  ```bash
  python research/aggregate_stats.py
  ```

### 3. Agent Behavioral Profiler (`agent_profiler.py` & `behavior_profiler/`)
Maps raw agent events to semantic actions (`READ`, `EDIT`, `SEARCH`, `LIST`, `COMMAND`) to measure:
* **Rediscovery Ratio**: Number of times an agent re-reads the same files.
* **Recovery Reads**: Re-reads occurring after long action gaps when context was forgotten.
* **Navigation Loops**: Circular directory inspections or redundant queries.
* **Usage**:
  ```bash
  python research/agent_profiler.py
  ```
