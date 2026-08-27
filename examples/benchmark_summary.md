+-------------------------- context-audit benchmark --------------------------+
|   CROSS-SESSION BENCHMARK SUMMARY                                           |
|   Directory: 27 Discovered Sessions                                         |
|                                                                             |
|   Sessions Analyzed: 27                                                     |
|                                                                             |
|   Cumulative Session Tokens:                                                |
|     Avg: 3.3M | Median: 314.2k | Max: 43.3M                                 |
|   Peak Context Size:                                                        |
|     Avg: 33.2k | Median: 20.1k | Max: 188.9k                                |
|   Final Context Size:                                                       |
|     Avg: 33.2k | Median: 20.1k                                              |
|   Context Reuse Ratio:                                                      |
|     Avg: 92.6% | Median: 94.2%                                              |
|   Average Novel Context Ratio: 7.4%                                         |
|                                                                             |
|   Financial Cost Aggregations (USD):                                        |
|     Total Standard Spend: $269.80                                           |
|     Avg Session Cost (No Cache): $9.99 | Median: $0.94                      |
|     Avg Session Cost (With Cache): $1.09 | Median: $0.15                    |
|     Total Potential Cache Savings: $240.40 (Avg: $8.90 / session, 89.1%)    |
|                                                                             |
+-----------------------------------------------------------------------------+

Top Repeated Artifacts Across All Sessions
+-----------------------------------------------------------------------------+
| Block Snippet /  |         |          |            Total |       Cumulative |
| Name             | Type    | Sessions |      Occurrences |    Repeated Cost |
|------------------+---------+----------+------------------+------------------|
| "Created At:     | Message |        1 |              429 |            $1.47 |
| 2026-08-26T18:4… |         |          |                  |                  |
| Co..."           |         |          |                  |                  |
| "Created At:     | Message |        1 |              410 |            $1.45 |
| 2026-08-26T18:4… |         |          |                  |                  |
| Co..."           |         |          |                  |                  |
| "Created At:     | Message |        1 |              391 |            $1.39 |
| 2026-08-26T18:4… |         |          |                  |                  |
| Co..."           |         |          |                  |                  |
| "The following   | Message |        1 |              225 |            $1.38 |
| is a             |         |          |                  |                  |
| <SYSTEM_MESSAGE> |         |          |                  |                  |
| not ..."         |         |          |                  |                  |
| "Created At:     | Message |        1 |              406 |            $1.37 |
| 2026-08-26T18:4… |         |          |                  |                  |
| Co..."           |         |          |                  |                  |
+-----------------------------------------------------------------------------+

Context Size Scaling Analysis
Does reuse scale linearly, or do larger sessions become exponentially more repetitive?
+-----------------------------------------------------------------------------+
| Session    |            |            |            |            |            |
| Size Class |            |        Avg |  Avg Cache |   Avg Peak |        Avg |
| (Final     |    Session |    Context |    Savings |    Context | Cumulative |
| Turn)      |      Count |    Reuse % |        ($) |       Size |     Tokens |
|------------+------------+------------+------------+------------+------------|
| < 5k       |          1 |      94.2% |      $0.09 |       2.0k |      34.3k |
| tokens     |            |            |            |            |            |
| 5k - 20k   |         12 |      87.4% |      $0.24 |      10.0k |      97.5k |
| tokens     |            |            |            |            |            |
| 20k - 50k  |          8 |      95.6% |      $1.49 |      23.6k |     575.4k |
| tokens     |            |            |            |            |            |
| > 50k      |          6 |      99.0% |     $37.59 |      97.3k |      14.0M |
| tokens     |            |            |            |            |            |
+-----------------------------------------------------------------------------+
