# M2 全部本轮运行索引

所有目录位于 `$HOME/.local/share/underwater-stack/runs/`。
过程状态与测试判定分别保留；M0 的 SUCCEEDED 由原 probe 的 PASS 支持。
v1 的五项原始 PASS 被独立复核否决（倾斜固定体估计发散），其余八项未运行；
v2 因 CLI 域接线问题停在五项 PASS，其余八项未运行。最终只采用 v3 完整 13 项。
未覆盖任何原始判定或日志，详情见 [验收报告](validation-2026-09-23-m2.md)。

| 阶段/版本 | 测试判定 | 过程状态 | run_id |
|---|---|---|---|
| diagnostic | FAIL | FAILED | `m2_diagnostic_calibration--20260923T023930Z--57565500090d` |
| diagnostic | FAIL | FAILED | `m2_diagnostic_calibration--20260923T024406Z--029fb8aa66c8` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_calibration--20260923T024545Z--e241ae487ee6` |
| diagnostic | FAIL | FAILED | `m2_diagnostic_imu_tilt--20260923T024611Z--07c4df74e23f` |
| diagnostic | FAIL | FAILED | `m2_diagnostic_imu_tilt--20260923T024702Z--2c93ff9d03c3` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_imu_tilt--20260923T024940Z--1856582fb118` |
| tuning | FAIL | FAILED | `m2_tuning_trajectory_1--20260923T025051Z--1656bff6886d` |
| tuning | FAIL | FAILED | `m2_tuning_trajectory_1--20260923T025639Z--d77888d0e42e` |
| tuning | PASS | COMPLETED | `m2_tuning_trajectory_1--20260923T025800Z--89f3983a552b` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_empty_water--20260923T025926Z--ae1f71c7da24` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_image_dropout--20260923T025957Z--71ab148122d3` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_imu_dropout--20260923T030036Z--02f6cf0dc9aa` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_clock_pause--20260923T030116Z--d5aa857fca0f` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_clock_rewind--20260923T030208Z--f51abe78cda9` |
| diagnostic | FAIL | FAILED | `m2_diagnostic_estimator_kill--20260923T030247Z--2d4f3b30c37e` |
| diagnostic | PASS | COMPLETED_WITH_EXPECTED_FAULT | `m2_diagnostic_estimator_kill--20260923T030422Z--7c0e49396705` |
| diagnostic | PASS | COMPLETED | `m2_diagnostic_load_1--20260923T030501Z--58d643629da2` |
| m2-v1 | PASS | COMPLETED | `m2_formal_calibration--20260923T030703Z--74e6bfca977c` |
| m2-v1 | PASS | COMPLETED | `m2_formal_imu_tilt--20260923T030729Z--87e6fe5882ba` |
| m2-v1 | PASS | COMPLETED | `m2_formal_trajectory_1--20260923T030755Z--4308a098687d` |
| m2-v1 | PASS | COMPLETED | `m2_formal_trajectory_2--20260923T030851Z--65d34e1d5014` |
| m2-v1 | PASS | COMPLETED | `m2_formal_trajectory_3--20260923T030948Z--4400d4de18cc` |
| tuning | PASS | COMPLETED | `m2_tuning_imu_tilt--20260923T031101Z--043314814636` |
| tuning | PASS | COMPLETED | `m2_tuning_trajectory_1--20260923T031140Z--572df6234c7f` |
| m2-v2 | PASS | COMPLETED | `m2_formal_calibration--20260923T031419Z--d46d3110a110` |
| m2-v2 | PASS | COMPLETED | `m2_formal_imu_tilt--20260923T031445Z--a4c690b715b0` |
| m2-v2 | PASS | COMPLETED | `m2_formal_trajectory_1--20260923T031511Z--8f06d23bfb99` |
| m2-v2 | PASS | COMPLETED | `m2_formal_trajectory_2--20260923T031608Z--6e67f1ece11a` |
| m2-v2 | PASS | COMPLETED | `m2_formal_trajectory_3--20260923T031704Z--94036defe8e3` |
| manual | PASS | COMPLETED | `m2_manual--20260923T031806Z--794271962e0f` |
| m2-v3 | PASS | COMPLETED | `m2_formal_calibration--20260923T031929Z--518ce904f4b5` |
| m2-v3 | PASS | COMPLETED | `m2_formal_imu_tilt--20260923T031955Z--137f14833bfb` |
| m2-v3 | PASS | COMPLETED | `m2_formal_trajectory_1--20260923T032021Z--9bb8c7e5767c` |
| m2-v3 | PASS | COMPLETED | `m2_formal_trajectory_2--20260923T032117Z--f9657c28456a` |
| m2-v3 | PASS | COMPLETED | `m2_formal_trajectory_3--20260923T032213Z--6034b36ba7b8` |
| m2-v3 | PASS | COMPLETED | `m2_formal_empty_water--20260923T032310Z--bf9ad465c8b2` |
| m2-v3 | PASS | COMPLETED | `m2_formal_image_dropout--20260923T032340Z--21c02249dbd4` |
| m2-v3 | PASS | COMPLETED | `m2_formal_imu_dropout--20260923T032419Z--393b70b352ab` |
| m2-v3 | PASS | COMPLETED | `m2_formal_clock_pause--20260923T032459Z--edc112f17d45` |
| m2-v3 | PASS | COMPLETED | `m2_formal_clock_rewind--20260923T032538Z--f07c3d8d162e` |
| m2-v3 | PASS | COMPLETED_WITH_EXPECTED_FAULT | `m2_formal_estimator_kill--20260923T032617Z--f6a005f56378` |
| m2-v3 | PASS | COMPLETED | `m2_formal_load_1--20260923T032656Z--a16762e086bc` |
| m2-v3 | PASS | COMPLETED | `m2_formal_load_2--20260923T032809Z--6cd3005a1d49` |
| diagnostic | PASS | COMPLETED | `diagnostic_vx_positive_1--20260923T032924Z--3a6a17ca6db7` |
| diagnostic | PASS | COMPLETED_WITH_EXPECTED_FAULT | `diagnostic_fault_adapter--20260923T033000Z--c992bc019828` |
| regression | PASS | SUCCEEDED | `bluerov_empty_water--20260923T033019Z--993818e09bab` |
| regression | PASS | SUCCEEDED | `bluerov_empty_water--20260923T033130Z--a8e39a3b1fe6` |
| regression | PASS | SUCCEEDED | `bluerov_empty_water--20260923T033519Z--e871a6f27cab` |
| regression | PASS | SUCCEEDED | `bluerov_empty_water--20260923T033630Z--37e442ddc818` |

## 原始记录计数（不代替版本复核结论）

| 阶段 | PASS | FAIL | NOT_RUN |
|---|---|---|---|
| diagnostic | 11 | 5 | 0 |
| tuning | 3 | 2 | 0 |
| manual | 1 | 0 | 0 |
| formal | 23 | 0 | 0 |
| regression | 4 | 0 | 0 |

formal 原始 23 PASS = v1 五项 + v2 五项 + v3 十三项；只有 v3 完整验收被接受。
诊断行包含两项最终 M1 回归；regression 为四轮 M0。构建失败不计入仿真 run 数。
