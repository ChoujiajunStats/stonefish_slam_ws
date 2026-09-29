# Porth 全洞采集运行索引

所有目录位于 `$HOME/.local/share/underwater-stack/runs/`。
进程运行、采集检查和故障处置分别判定；NOT_RUN 表示没有完成采集判定。

| run_id | 进程 | 采集 | 行程 m | 回环 | 故障保护 |
|---|---|---|---:|---:|---|
| porth_survey_calibration_v1--20260923T202301Z--3f7d897a15df | FAILED | NOT_RUN | — | — | — |
| porth_survey_calibration_v1--20260923T202326Z--859e1ce3d6c4 | FAILED | NOT_RUN | — | — | — |
| porth_survey_calibration_v1--20260923T202435Z--851b880a10e6 | FAILED | NOT_RUN | — | — | — |
| porth_survey_calibration_v1--20260923T202727Z--61e235c65895 | COMPLETED | PASS | 8.41 | 0 | — |
| porth_survey_turn_calibration--20260923T202858Z--613da2b0549c | FAILED | FAIL | 27.08 | 0 | — |
| porth_survey_turn_calibration--20260923T203304Z--66ce6e1310b0 | COMPLETED | PASS | 30.27 | 0 | — |
| porth_survey_full_v1--20260923T203629Z--4608fd787e42 | FAILED | FAIL | 169.34 | 0 | — |
| porth_survey_end_calibration--20260923T205525Z--dd0875d0cce7 | FAILED | FAIL | 4.22 | 0 | — |
| porth_survey_end_calibration--20260923T205726Z--e7dc373f5397 | COMPLETED | PASS | 8.48 | 5 | — |
| porth_survey_full_v2--20260923T205930Z--30d8d7470a29 | FAILED | FAIL | 28.18 | 0 | — |
| porth_survey_branch_calibration--20260923T210325Z--5de01c4278df | FAILED | FAIL | — | 0 | — |
| porth_survey_branch_interior_v1--20260923T212202Z--d60365e97f40 | FAILED | FAIL | — | 0 | — |
| porth_survey_branch_interior_v1--20260923T212424Z--194b1d480234 | FAILED | FAIL | — | 0 | — |
| porth_survey_cyan_lamps_v1--20260923T212718Z--8fb91a693d49 | COMPLETED | PASS | 16.40 | 18 | — |
| porth_survey_branch1_cyan_v1--20260923T213015Z--1fa309da00d3 | COMPLETED | PASS | 17.28 | 23 | — |
| porth_survey_branch2_cyan_v1--20260923T213317Z--361e84df9240 | COMPLETED | PASS | 16.92 | 22 | — |
| porth_survey_optical_adapter_kill--20260923T213529Z--8d4d88be5257 | FAILED | FAIL | 2.45 | 0 | PASS |
| porth_survey_full_v3--20260923T213639Z--e880633b9f71 | FAILED | FAIL | 552.57 | 312 | 原生中和，FAULT 锁存 |
| porth_survey_full_v4--20260923T224043Z--c68841acc630 | COMPLETED | PASS | 566.97 | 217 | DISARMED，原生中和 |

共 19 次尝试：采集 PASS 7、FAIL 9、NOT_RUN 3。NOT_RUN 的三次启动失败
保留，没有伪称实际采集成功。单独的末级适配 SIGKILL 病例故障保护 PASS，
其采集 FAIL 原样保留。v4 是一次完整长路线通过，没有三次完整重复。

v3 的路线进度为 555.797 m，表中的行程为独立真值轨迹累计 552.57 m；二者
定义不同。v3 因视觉词典更新阻塞触发 SLAM 新鲜度保护，不能算全程完成。

另行执行的 M0 回归：`bluerov_empty_water--20260923T223214Z--a411af33f5e7`，
原观察配置连续 60 s、SUCCEEDED/PASS，六个必要进程退出 0。

[验证与失败原因](validation-2026-09-24-porth-survey.md) · [文件范围](porth-survey-file-changes.md)
