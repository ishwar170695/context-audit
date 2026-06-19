+---------------------------- context-audit v0.1 -----------------------------+
| CONTEXT AUDIT REPORT                                                        |
| Target: transcript.jsonl                                                    |
|                                                                             |
| Cumulative Session Tokens: 2.8M tokens                                      |
| Peak Context Size: 47.0k tokens                                             |
| Final Context Size: 47.0k tokens                                            |
| Total Turns: 123                                                            |
|                                                                             |
| Context Reuse Ratio: 98.3%                                                  |
| Novel Context Ratio: 1.7%                                                   |
|                                                                             |
| Financial Cost Estimates:                                                   |
|   Est. Input Cost (No Caching): $8.40                                       |
|   Est. Cost (With Prompt Caching): $8.24                                    |
|   Potential Cache Savings (this session): $0.16 (1.9%)                      |
|                                                                             |
| [Note: Context Reuse represents cumulative tokens consisting of previously  |
| seen blocks.                                                                |
| Prompt Caching assumes system prompt + tool schemas are cached after the    |
| first turn.]                                                                |
+-----------------------------------------------------------------------------+

Context Timeline (Turn-by-Turn Growth)
+-----------------------------------------------------------------------------+
| Turn | Context Size | Delta | Key Contributors (Heaviest Additions)         |
|------+--------------+-------+-----------------------------------------------|
| 1    |          674 |  +674 | Tool Schemas (442), User Input (198), System  |
|      |              |       | Prompt (34)                                   |
| 2    |          712 |   +38 | Tool message (38), Model message (0)          |
| 3    |         2.0k | +1.2k | Tool message (1.2k), Model message (73)       |
| 4    |         2.0k |   +62 | Tool message (62), Model message (0)          |
| 5    |         2.1k |   +60 | Tool message (60), Model message (0)          |
| 6    |         2.1k |   +64 | Tool message (64), Model message (0)          |
| 7    |         3.4k | +1.3k | Tool message (1.3k), Model message (0)        |
| 8    |         3.6k |  +229 | Tool message (135), Model message (94)        |
| 9    |         3.9k |  +251 | Tool message (251), Model message (0)         |
| 10   |         4.5k |  +637 | Model message (481), Tool message (156)       |
| 11   |         4.7k |  +205 | Tool message (205), Model message (0)         |
| 12   |         5.1k |  +378 | Model message (322), Tool message (56)        |
| 13   |         5.2k |   +77 | Tool message (77), Model message (0)          |
| 14   |         5.3k |   +73 | Tool message (73), Model message (0)          |
| 15   |         5.4k |  +101 | Tool message (101), Model message (0)         |
| 16   |         5.9k |  +550 | Model message (550)                           |
| 17   |         6.7k |  +840 | User message (840), Model message (0)         |
| 18   |         6.8k |   +71 | Model message (71)                            |
| 19   |         7.8k |  +935 | User message (935), Model message (0)         |
| 20   |         7.9k |  +166 | Model message (166)                           |
| 21   |         8.8k |  +839 | User message (839), Model message (0)         |
| 22   |         8.8k |   +48 | Model message (48)                            |
| 23   |         8.8k |     0 | Model message (0)                             |
| 24   |         8.8k |     0 | Model message (0)                             |
| 25   |         8.8k |     0 | Model message (0)                             |
| 26   |         8.8k |     0 | Model message (0)                             |
| 27   |         9.2k |  +389 | Model message (389)                           |
| 28   |         9.8k |  +632 | Model message (632)                           |
| 29   |        10.0k |  +148 | Model message (148)                           |
| 30   |        10.1k |   +90 | Model message (90)                            |
| 31   |        10.1k |     0 | Model message (0)                             |
| 32   |        10.1k |   +73 | Model message (73)                            |
| 33   |        10.1k |     0 | Model message (0)                             |
| 34   |        10.2k |   +77 | Model message (77)                            |
| 35   |        10.3k |   +77 | Tool message (77), Model message (0)          |
| 36   |        10.4k |  +126 | Tool message (126), Model message (0)         |
| 37   |        11.9k | +1.5k | Tool message (1.5k), Model message (0)        |
| 38   |        12.0k |  +128 | Tool message (128), Model message (0)         |
| 39   |        12.3k |  +302 | Tool message (302), Model message (0)         |
| 40   |        12.4k |  +124 | Tool message (124), Model message (0)         |
| 41   |        13.7k | +1.3k | Tool message (1.3k), Model message (0)        |
| 42   |        13.8k |  +129 | Tool message (129), Model message (0)         |
| 43   |        14.7k |  +921 | Tool message (921), Model message (0)         |
| 44   |        14.9k |  +168 | Model message (168)                           |
| 45   |        15.2k |  +298 | Tool message (298), Model message (0)         |
| 46   |        15.3k |   +95 | Model message (95)                            |
| 47   |        16.0k |  +714 | Tool message (714), Model message (0)         |
| 48   |        16.2k |  +213 | Model message (213)                           |
| 49   |        16.9k |  +718 | Tool message (718), Model message (0)         |
| 50   |        17.7k |  +715 | Tool message (715), Model message (0)         |
| 51   |        18.4k |  +711 | Tool message (711), Model message (0)         |
| 52   |        18.4k |   +74 | Tool message (74), Model message (0)          |
| 53   |        19.6k | +1.1k | Tool message (1.1k), Model message (0)        |
| 54   |        19.8k |  +168 | Tool message (101), Model message (67)        |
| 55   |        19.9k |  +132 | Model message (78), Tool message (54)         |
| 56   |        20.0k |   +66 | Tool message (66), Model message (0)          |
| 57   |        20.8k |  +892 | Tool message (892), Model message (0)         |
| 58   |        20.9k |   +63 | Model message (63)                            |
| 59   |        20.9k |     0 | Model message (0)                             |
| 60   |        20.9k |   +42 | Model message (42)                            |
| 61   |        22.2k | +1.3k | User message (992), Tool message (304), Model |
|      |              |       | message (0)                                   |
| 62   |        22.5k |  +238 | Model message (189), Tool message (49)        |
| 63   |        22.6k |  +133 | Model message (133)                           |
| 64   |        22.6k |     0 | Model message (0)                             |
| 65   |        23.7k | +1.1k | Tool message (1.0k), Model message (55)       |
| 66   |        23.7k |     0 | Model message (0)                             |
| 67   |        24.9k | +1.2k | Tool message (1.1k), Model message (79)       |
| 68   |        25.1k |  +269 | Model message (269)                           |
| 69   |        25.2k |   +66 | Model message (66)                            |
| 70   |        25.3k |   +84 | Model message (84)                            |
| 71   |        25.4k |   +95 | Model message (95)                            |
| 72   |        25.5k |  +128 | Tool message (128), Model message (0)         |
| 73   |        26.0k |  +500 | Tool message (500), Model message (0)         |
| 74   |        26.1k |   +81 | Model message (81)                            |
| 75   |        26.2k |  +128 | Tool message (128), Model message (0)         |
| 76   |        26.5k |  +302 | Tool message (302), Model message (0)         |
| 77   |        26.7k |  +141 | Tool message (141), Model message (0)         |
| 78   |        27.6k |  +883 | Tool message (883), Model message (0)         |
| 79   |        27.9k |  +348 | Tool message (276), Model message (72)        |
| 80   |        28.1k |  +200 | Tool message (200), Model message (0)         |
| 81   |        29.0k |  +899 | Tool message (899), Model message (0)         |
| 82   |        30.1k | +1.1k | Tool message (1.1k), Model message (0)        |
| 83   |        30.1k |   +71 | Model message (71)                            |
| 84   |        30.1k |     0 | Model message (0)                             |
| 85   |        30.2k |   +91 | Model message (91)                            |
| 86   |        31.5k | +1.3k | User message (843), Tool message (465), Model |
|      |              |       | message (0)                                   |
| 87   |        31.7k |  +187 | Model message (187)                           |
| 88   |        31.8k |   +87 | Model message (87)                            |
| 89   |        32.9k | +1.1k | Tool message (1.1k), Model message (0)        |
| 90   |        33.0k |   +96 | Model message (96)                            |
| 91   |        33.1k |  +128 | Tool message (128), Model message (0)         |
| 92   |        33.4k |  +302 | Tool message (302), Model message (0)         |
| 93   |        33.7k |  +316 | Tool message (316), Model message (0)         |
| 94   |        33.9k |  +200 | Tool message (200), Model message (0)         |
| 95   |        34.2k |  +276 | Tool message (276), Model message (0)         |
| 96   |        35.0k |  +823 | Tool message (348), Tool message (275), Tool  |
|      |              |       | message (200) (+1 more)                       |
| 97   |        35.5k |  +510 | Tool message (510), Model message (0)         |
| 98   |        36.1k |  +536 | Tool message (536), Model message (0)         |
| 99   |        37.1k |  +999 | Tool message (999), Model message (0)         |
| 100  |        37.1k |   +76 | Model message (76)                            |
| 101  |        38.0k |  +901 | Tool message (521), User message (203), Tool  |
|      |              |       | message (177) (+1 more)                       |
| 102  |        39.1k | +1.1k | Tool message (923), Model message (186)       |
| 103  |        40.5k | +1.3k | Tool message (926), Model message (407)       |
| 104  |        40.7k |  +179 | Tool message (179), Model message (0)         |
| 105  |        40.9k |  +218 | Model message (162), Tool message (56)        |
| 106  |        41.5k |  +596 | Model message (596)                           |
| 107  |        42.0k |  +541 | Tool message (541), Model message (0)         |
| 108  |        42.0k |     0 | Model message (0)                             |
| 109  |        42.4k |  +392 | Tool message (392), Model message (0)         |
| 110  |        42.5k |   +69 | Model message (69)                            |
| 111  |        42.6k |  +128 | Tool message (128), Model message (0)         |
| 112  |        42.9k |  +302 | Tool message (302), Model message (0)         |
| 113  |        43.2k |  +316 | Tool message (316), Model message (0)         |
| 114  |        43.4k |  +200 | Tool message (200), Model message (0)         |
| 115  |        43.7k |  +276 | Tool message (276), Model message (0)         |
| 116  |        44.2k |  +554 | Tool message (354), Tool message (200), Model |
|      |              |       | message (0)                                   |
| 117  |        45.1k |  +877 | Tool message (674), User message (203), Model |
|      |              |       | message (0)                                   |
| 118  |        46.0k |  +845 | User message (778), Model message (67)        |
| 119  |        46.6k |  +645 | Model message (645)                           |
| 120  |        46.8k |  +154 | Model message (154)                           |
| 121  |        46.8k |   +77 | Model message (77)                            |
| 122  |        46.9k |   +71 | Model message (71)                            |
| 123  |        47.0k |  +128 | Tool message (128), Model message (0)         |
+-----------------------------------------------------------------------------+

Top Repeated Context Blocks
+-----------------------------------------------------------------------------+
| Context       |               |     Repeated |               |              |
| Source        | Type          |       Tokens | Repeated Cost | Details      |
|---------------+---------------+--------------+---------------+--------------|
| Message       | Message       |       147.4k |         $0.44 | Repeated 117 |
| Repetition:   | History       |              |               | times        |
| tool_respons… |               |              |               |              |
| Message       | Message       |       139.9k |         $0.42 | Repeated 121 |
| Repetition:   | History       |              |               | times        |
| tool_respons… |               |              |               |              |
| Message       | Message       |       124.9k |         $0.37 | Repeated 87  |
| Repetition:   | History       |              |               | times        |
| tool_respons… |               |              |               |              |
| Message       | Message       |       103.6k |         $0.31 | Repeated 83  |
| Repetition:   | History       |              |               | times        |
| tool_respons… |               |              |               |              |
| Message       | Message       |        97.2k |         $0.29 | Repeated 105 |
| Repetition:   | History       |              |               | times        |
| user_message  |               |              |               |              |
+-----------------------------------------------------------------------------+

Largest Context Consumers (Single Blocks)
+-----------------------------------------------------------------------------+
| Component Name                           | Type             | Size (Tokens) |
|------------------------------------------+------------------+---------------|
| Tool output: system_message (Turn 57)    | History Message  |          1.5k |
| Tool output: view_file (Turn 13)         | History Message  |          1.3k |
| Tool output: system_message (Turn 65)    | History Message  |          1.3k |
| Tool output: generic (Turn 5)            | History Message  |          1.2k |
| Tool output: run_command (Turn 86)       | History Message  |          1.1k |
+-----------------------------------------------------------------------------+

Repeated Blocks Analysis
+-----------------------------------------------------------------------------+
| Block Snippet /   |         |       |                  |     Total Repeated |
| Name              | Type    | Count | Token Cost/Occur |               Cost |
|-------------------+---------+-------+------------------+--------------------|
| "Created At:      | Message |   117 |             1.3k |              $0.44 |
| 2026-06-19T03:30… |         |       |                  |                    |
| Complet..."       |         |       |                  |                    |
| "Created At:      | Message |   121 |             1.2k |              $0.42 |
| 2026-06-19T03:29… |         |       |                  |                    |
| Complet..."       |         |       |                  |                    |
| "The following is | Message |    87 |             1.5k |              $0.37 |
| a                 |         |       |                  |                    |
| <SYSTEM_MESSAGE>  |         |       |                  |                    |
| not ..."          |         |       |                  |                    |
| "The following is | Message |    83 |             1.3k |              $0.31 |
| a                 |         |       |                  |                    |
| <SYSTEM_MESSAGE>  |         |       |                  |                    |
| not ..."          |         |       |                  |                    |
| "<USER_REQUEST>   | Message |   105 |              935 |              $0.29 |
| This is now in    |         |       |                  |                    |
| the range ..."    |         |       |                  |                    |
+-----------------------------------------------------------------------------+
