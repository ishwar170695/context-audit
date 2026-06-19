
+-------------------------- context-audit benchmark --------------------------+
|     CROSS-SESSION BENCHMARK SUMMARY                                         |
|     Directory: C:\\Users\\ishu\\.gemini\\antigravity-ide\\brain             |
|                                                                             |
|     Sessions Analyzed: 27                                                   |
|                                                                             |
|     Cumulative Session Tokens:                                              |
|       Avg: 9.3M | Median: 1.2M | Max: 76.3M                                 |
|     Peak Context Size:                                                      |
|       Avg: 58.7k | Median: 35.2k | Max: 246.0k                              |
|     Final Context Size:                                                     |
|       Avg: 58.7k | Median: 35.2k                                            |
|     Context Reuse Ratio:                                                    |
|       Avg: 94.5% | Median: 97.1%                                            |
|     Average Novel Context Ratio: 5.5%                                       |
|                                                                             |
|     Financial Cost Aggregations (USD):                                      |
|       Total Standard Spend: $753.24                                         |
|       Avg Session Cost (No Cache): $27.90 | Median: $3.48                   |
|       Avg Session Cost (With Cache): $27.63 | Median: $3.37                 |
|       Total Potential Cache Savings: $7.33 (Avg: $0.27 / session, 1.0%)     |
|                                                                             |
+-----------------------------------------------------------------------------+

Top Repeated Artifacts Across All Sessions
+-----------------------------------------------------------------------------+
| Block Snippet /  |         |          |            Total |       Cumulative |
| Name             | Type    | Sessions |      Occurrences |    Repeated Cost |
|------------------+---------+----------+------------------+------------------|
| "Created At:     | Message |        1 |              493 |            $2.30 |
| 2026-06-18T04:2… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "The following   | Message |        1 |              493 |            $2.15 |
| is a             |         |          |                  |                  |
| <SYSTEM_MESSAGE> |         |          |                  |                  |
| not ..."         |         |          |                  |                  |
| "Created At:     | Message |        1 |              615 |            $2.13 |
| 2026-06-14T02:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              561 |            $2.11 |
| 2026-06-18T04:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              603 |            $2.11 |
| 2026-06-14T02:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              612 |            $2.09 |
| 2026-06-14T02:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              613 |            $2.04 |
| 2026-06-14T02:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              614 |            $1.95 |
| 2026-06-14T02:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              472 |            $1.95 |
| 2026-06-14T02:3… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
| "Created At:     | Message |        1 |              611 |            $1.95 |
| 2026-06-14T02:1… |         |          |                  |                  |
| Complet..."      |         |          |                  |                  |
+-----------------------------------------------------------------------------+

Context Size Scaling Analysis
Does reuse scale linearly, or do larger sessions become exponentially more 
repetitive?
+-----------------------------------------------------------------------------+
| Session    |            |            |            |            |            |
| Size Class |            |        Avg |  Avg Cache |   Avg Peak |        Avg |
| (Final     |    Session |    Context |    Savings |    Context | Cumulative |
| Turn)      |      Count |    Reuse % |        ($) |       Size |     Tokens |
|------------+------------+------------+------------+------------+------------|
| < 5k       |          2 |      66.3% |    $0.0015 |       1.6k |       4.9k |
| tokens     |            |            |            |            |            |
| 5k - 20k   |          5 |      92.5% |      $0.04 |      12.7k |     226.6k |
| tokens     |            |            |            |            |            |
| 20k - 50k  |         11 |      96.8% |      $0.10 |      32.5k |       1.2M |
| tokens     |            |            |            |            |            |
| > 50k      |          9 |      99.2% |      $0.68 |     129.0k |      26.3M |
| tokens     |            |            |            |            |            |
+-----------------------------------------------------------------------------+

