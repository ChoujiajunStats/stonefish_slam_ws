# M3 全部运行索引

包含诊断、调试、早期冻结、最终评价和回归。原始 verdict 保留；早期单项 PASS
不等于最终 M3 通过。最终版本与复核排除项见 [验收报告](validation-2026-09-23-m3.md)。

路径根为 `$HOME/.local/share/underwater-stack/runs/`。

| run_id | 阶段 | 进程状态 | 原始判定 | CLI 另行判定 |
|---|---|---|---|---|
| `bluerov_empty_water--20260923T090017Z--57ddab05a3f0` | M0 regression | SUCCEEDED | PASS | — |
| `bluerov_empty_water--20260923T090129Z--62b828efb41e` | M0 regression | SUCCEEDED | PASS | — |
| `m3_diagnostic_bootstrap--20260923T080000Z--3af0ab6245dd` | diagnostic | FAILED | FAIL | — |
| `m3_diagnostic_bootstrap--20260923T080133Z--f38f33645fe6` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_bootstrap--20260923T080933Z--63ac69e8636f` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_cancel--20260923T080504Z--e02c10c8de9a` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_fault_actuator_adapter--20260923T080655Z--ec5994c4b080` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_fault_clock_pause--20260923T081156Z--cf9b1fecf22a` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_fault_clock_rewind--20260923T081225Z--465988f84a1c` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_fault_controller--20260923T081026Z--cc4759f5d39b` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_fault_guard--20260923T080626Z--cee31c42dc88` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_fault_images--20260923T080724Z--71a1931cabbe` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_fault_imu--20260923T081127Z--35530f15cd90` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_fault_localization--20260923T081055Z--9b3f94afe51a` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_fault_navigation--20260923T080957Z--0b72feca90f4` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_fault_rviz--20260923T081254Z--299d035277d0` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_fault_tasks--20260923T080557Z--232e838b5fd8` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_diagnostic_invalid_goals--20260923T080439Z--c20722fdea62` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_restart_replay--20260923T081339Z--60c1a43f1acb` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_rotated--20260923T080754Z--8a307aa7a801` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_timeout--20260923T080533Z--0e982d688727` | diagnostic | COMPLETED | PASS | — |
| `m3_diagnostic_timeout--20260923T084320Z--7574550248d0` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_bootstrap--20260923T082705Z--e3e97727630d` | formal | COMPLETED | PASS | — |
| `m3_formal_bootstrap--20260923T083352Z--a37f12bde6a1` | formal | COMPLETED | PASS | — |
| `m3_formal_bootstrap--20260923T084818Z--13f0bb8b465c` | formal | COMPLETED | PASS | — |
| `m3_formal_cancel--20260923T083921Z--c0001398863f` | formal | COMPLETED | PASS | — |
| `m3_formal_cancel--20260923T085348Z--817d46ad4bc5` | formal | COMPLETED | PASS | — |
| `m3_formal_fault_actuator_adapter--20260923T084211Z--b8ce76d67a78` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_actuator_adapter--20260923T085638Z--21c2401e0ec7` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_clock_pause--20260923T085835Z--8940c21f89cb` | formal | COMPLETED | PASS | — |
| `m3_formal_fault_clock_rewind--20260923T085904Z--919b1e099f58` | formal | COMPLETED | PASS | — |
| `m3_formal_fault_controller--20260923T084142Z--b5bf0f31b93f` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_controller--20260923T085609Z--6fa62c018c87` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_guard--20260923T084113Z--0e34fb272446` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_guard--20260923T085540Z--031627011800` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_images--20260923T085737Z--82f529284fe3` | formal | COMPLETED | PASS | — |
| `m3_formal_fault_imu--20260923T085806Z--4e418b1fc643` | formal | COMPLETED | PASS | — |
| `m3_formal_fault_localization--20260923T085707Z--4cbc06ad9a8e` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_navigation--20260923T084044Z--027944d58dd8` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_navigation--20260923T085510Z--338f5f72a56b` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_rviz--20260923T085933Z--3c869d3f56a9` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_tasks--20260923T084015Z--28fb68a081c4` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_fault_tasks--20260923T085441Z--1d4eb84945bc` | formal | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_invalid_goals--20260923T083416Z--e1772e722e8a` | formal | COMPLETED | PASS | — |
| `m3_formal_invalid_goals--20260923T084842Z--509c60c8c813` | formal | COMPLETED | PASS | — |
| `m3_formal_load_1--20260923T082433Z--b09be8cbe5dd` | formal | COMPLETED | PASS | — |
| `m3_formal_load_1--20260923T082801Z--98ca84cc0139` | formal | COMPLETED | PASS | — |
| `m3_formal_load_1--20260923T083120Z--e574028f2912` | formal | COMPLETED | PASS | — |
| `m3_formal_load_1--20260923T084546Z--bd899633b92b` | formal | COMPLETED | PASS | — |
| `m3_formal_load_2--20260923T082549Z--f751b8894d2c` | formal | COMPLETED | PASS | — |
| `m3_formal_load_2--20260923T082917Z--2367e1ce11dd` | formal | COMPLETED | PASS | — |
| `m3_formal_load_2--20260923T083236Z--74536f111882` | formal | COMPLETED | PASS | — |
| `m3_formal_load_2--20260923T084702Z--a3028a7ef0fc` | formal | COMPLETED | PASS | — |
| `m3_formal_m1_velocity--20260923T090240Z--247295e13c8c` | M0 regression | COMPLETED | PASS | — |
| `m3_formal_m1_watchdog--20260923T090316Z--d334196bef35` | M0 regression | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_m2_calibration--20260923T090335Z--db4933521cf0` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_clock_pause--20260923T090907Z--3ecd993a63c6` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_clock_rewind--20260923T090946Z--f1cbd044dcbe` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_empty_water--20260923T090717Z--224ef591eec0` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_estimator_kill--20260923T091025Z--1a754bb40f61` | diagnostic | COMPLETED_WITH_EXPECTED_FAULT | PASS | — |
| `m3_formal_m2_image_dropout--20260923T090748Z--f6f820c0c991` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_imu_dropout--20260923T090828Z--94b5372d73ec` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_imu_tilt--20260923T090402Z--6d3437c9dd0e` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_load_1--20260923T091105Z--da38c3c2aa6e` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_load_2--20260923T091218Z--12a87e2b8be3` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_trajectory_1--20260923T090428Z--60e523f56567` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_trajectory_2--20260923T090525Z--5dab96961bed` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_m2_trajectory_3--20260923T090621Z--639640a96c80` | diagnostic | COMPLETED | PASS | — |
| `m3_formal_mission_1--20260923T083440Z--f643a6bdb042` | formal | COMPLETED | PASS | — |
| `m3_formal_mission_1--20260923T084906Z--9725838765dd` | formal | COMPLETED | PASS | — |
| `m3_formal_mission_2--20260923T083544Z--b6a320f28a52` | formal | COMPLETED | PASS | — |
| `m3_formal_mission_2--20260923T085010Z--49272b8570cc` | formal | COMPLETED | PASS | — |
| `m3_formal_mission_3--20260923T083648Z--efd7a2cdcdef` | formal | COMPLETED | PASS | — |
| `m3_formal_mission_3--20260923T085115Z--5ea7a7b21dbf` | formal | COMPLETED | PASS | — |
| `m3_formal_restart_replay--20260923T083837Z--a30ad6fa9346` | formal | COMPLETED | PASS | — |
| `m3_formal_restart_replay--20260923T085303Z--af5581544824` | formal | COMPLETED | PASS | — |
| `m3_formal_rotated--20260923T083753Z--735a573e0a52` | formal | COMPLETED | PASS | — |
| `m3_formal_rotated--20260923T085219Z--4a48ac9cc654` | formal | COMPLETED | PASS | — |
| `m3_formal_timeout--20260923T083951Z--9d10fe7b3b1f` | formal | FAILED | FAIL | — |
| `m3_formal_timeout--20260923T085417Z--716b0108a0ca` | formal | COMPLETED | PASS | — |
| `m3_manual--20260923T081500Z--ee6db65ddc39` | manual | COMPLETED | PASS | FAIL |
| `m3_manual--20260923T081636Z--6b98831bb9d0` | manual | COMPLETED | PASS | FAIL |
| `m3_manual--20260923T081849Z--84c01d456951` | manual | COMPLETED | PASS | FAIL |
| `m3_manual--20260923T082124Z--d944393fd688` | manual | COMPLETED | PASS | CANCEL_NOT_EXERCISED |
| `m3_manual--20260923T082317Z--40bc1ba0d18c` | manual | COMPLETED | PASS | PASS |
| `m3_manual--20260923T091332Z--a422200ee824` | manual | COMPLETED | PASS | PASS |
| `m3_tuning_mission_1--20260923T080202Z--0bc29d410a9f` | tuning | FAILED | FAIL | — |
| `m3_tuning_mission_1--20260923T080326Z--e82e20b8c684` | tuning | COMPLETED | PASS | — |
