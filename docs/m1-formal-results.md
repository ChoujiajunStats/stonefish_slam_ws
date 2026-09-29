## 正式病例结果

共需 54 次运行；当前完成 54，计数 {'PASS': 54}，NOT_RUN 0。
过程状态与测试判定分开；预期 SIGKILL 的进程保留真实 -9 退出码。

| 类别 | 应执行 | PASS | FAIL | NOT_RUN |
|---|---:|---:|---:|---:|
| 八通道映射 | 8 | 8 | 0 | 0 |
| 控制权/非法输入 | 2 | 2 | 0 | 0 |
| 四维单轴三次重复 | 24 | 24 | 0 | 0 |
| 附加控制/图形负载 | 7 | 7 | 0 | 0 |
| 真实故障/UI注入 | 11 | 11 | 0 | 0 |
| M0 原配置回归 | 2 | 2 | 0 | 0 |

## 单轴三次独立重复

单元格为 PASS/FAIL 与命令轴稳态 RMSE（线速度 m/s，yaw rate rad/s）。完整其他轴、姿态、回零、全段误差、超调、饱和和延迟在每轮 control-metrics.json。

| 目标 | 第 1 次 | 第 2 次 | 第 3 次 |
|---|---|---|---|
| vx +0.15 | PASS / 0.000330 | PASS / 0.000330 | PASS / 0.000331 |
| vx -0.15 | PASS / 0.000402 | PASS / 0.000390 | PASS / 0.000386 |
| vy +0.15 | PASS / 0.000672 | PASS / 0.000664 | PASS / 0.000661 |
| vy -0.15 | PASS / 0.000661 | PASS / 0.000685 | PASS / 0.000677 |
| vz +0.08 | PASS / 0.001216 | PASS / 0.001224 | PASS / 0.001224 |
| vz -0.08 | PASS / 0.000747 | PASS / 0.000736 | PASS / 0.000743 |
| yaw +0.15 | PASS / 0.000217 | PASS / 0.000235 | PASS / 0.000224 |
| yaw -0.15 | PASS / 0.000859 | PASS / 0.000537 | PASS / 0.000586 |

## 最后一跳与故障注入

| 病例 | 判定 | 原生已应用零设定值延迟 / s | 末端状态 | 被杀进程真实退出 |
|---|---|---:|---|---|
| fault_source | PASS | 0.258719 | FAULT | 无进程注入退出 |
| fault_guard | PASS | 0.235667 | FAULT | guard=-9 |
| fault_controller | PASS | 0.201035 | FAULT | controller=-9 |
| fault_adapter | PASS | 0.211244 | FAULT | actuator_adapter=-9 |
| fault_state | PASS | 0.219744 | FAULT | observation_adapter=-9 |
| fault_state_frozen | PASS | 0.214882 | FAULT | 无进程注入退出 |
| fault_clock_pause | PASS | 0.003531 | FAULT | 无进程注入退出 |
| fault_clock_rewind | PASS | 0.003009 | FAULT | 无进程注入退出 |
| fault_disarm | PASS | 0.001999 | DISARMED | 无进程注入退出 |
| fault_latch | PASS | 0.004456 | FAULT | 无进程注入退出 |
| fault_rviz | PASS | 不适用（UI退出继续控制） | ARMED | rviz=-9 |

## 全部正式 run 索引

数据根为 `/home/hong/.local/share/underwater-stack`，以下目录均在 `runs/`；逐病例报告位于 `reports/m1-formal-0f6d569e49.json`。

| 病例 | 判定 | run_id |
|---|---|---|
| load_1 | PASS | `formal_load_1--20260921T183501Z--8f92b95eebe7` |
| load_2 | PASS | `formal_load_2--20260921T183629Z--f4ca9000d841` |
| m0 | PASS | `bluerov_empty_water--20260921T183758Z--d3942fbab30c` |
| m0 | PASS | `bluerov_empty_water--20260921T183909Z--6f5b14c5ace8` |
| probe_0 | PASS | `formal_probe_0--20260921T184020Z--e755cb397993` |
| probe_1 | PASS | `formal_probe_1--20260921T184039Z--e55d3158a52b` |
| probe_2 | PASS | `formal_probe_2--20260921T184100Z--ff8832db4bc1` |
| probe_3 | PASS | `formal_probe_3--20260921T184121Z--b255b1eb4500` |
| probe_4 | PASS | `formal_probe_4--20260921T184141Z--4960a3263e08` |
| probe_5 | PASS | `formal_probe_5--20260921T184202Z--ce4339a8d6ea` |
| probe_6 | PASS | `formal_probe_6--20260921T184223Z--af10b16edc82` |
| probe_7 | PASS | `formal_probe_7--20260921T184243Z--3f9158f08a8e` |
| authority_validation | PASS | `formal_authority_validation--20260921T184304Z--6cfdf4eef9c0` |
| authority_velocity | PASS | `formal_authority_velocity--20260921T184318Z--d29f5eda97a1` |
| vx_positive_1 | PASS | `formal_vx_positive_1--20260921T184331Z--34fba31a796d` |
| vx_positive_2 | PASS | `formal_vx_positive_2--20260921T184408Z--90b32e740e8b` |
| vx_positive_3 | PASS | `formal_vx_positive_3--20260921T184445Z--75714725db88` |
| vx_negative_1 | PASS | `formal_vx_negative_1--20260921T184522Z--b9db7853c402` |
| vx_negative_2 | PASS | `formal_vx_negative_2--20260921T184559Z--e41ef7e2735b` |
| vx_negative_3 | PASS | `formal_vx_negative_3--20260921T184635Z--013c96d32729` |
| vy_positive_1 | PASS | `formal_vy_positive_1--20260921T184712Z--342fc8133055` |
| vy_positive_2 | PASS | `formal_vy_positive_2--20260921T184749Z--d38da00a66ab` |
| vy_positive_3 | PASS | `formal_vy_positive_3--20260921T184826Z--0fdc0e3d054d` |
| vy_negative_1 | PASS | `formal_vy_negative_1--20260921T184903Z--daa54113d204` |
| vy_negative_2 | PASS | `formal_vy_negative_2--20260921T184939Z--ddda9e0668e0` |
| vy_negative_3 | PASS | `formal_vy_negative_3--20260921T185016Z--d725e9e32af3` |
| vz_positive_1 | PASS | `formal_vz_positive_1--20260921T185053Z--5e8dc866f2c9` |
| vz_positive_2 | PASS | `formal_vz_positive_2--20260921T185130Z--9abc9936b223` |
| vz_positive_3 | PASS | `formal_vz_positive_3--20260921T185207Z--7e7f961dec33` |
| vz_negative_1 | PASS | `formal_vz_negative_1--20260921T185244Z--9487c0d7f27f` |
| vz_negative_2 | PASS | `formal_vz_negative_2--20260921T185321Z--e4ac3f319f2f` |
| vz_negative_3 | PASS | `formal_vz_negative_3--20260921T185358Z--0998d2e15afd` |
| yaw_positive_1 | PASS | `formal_yaw_positive_1--20260921T185435Z--5014d763af74` |
| yaw_positive_2 | PASS | `formal_yaw_positive_2--20260921T185511Z--26050c4747e6` |
| yaw_positive_3 | PASS | `formal_yaw_positive_3--20260921T185548Z--ba874a191553` |
| yaw_negative_1 | PASS | `formal_yaw_negative_1--20260921T185625Z--f9ecd5f020a0` |
| yaw_negative_2 | PASS | `formal_yaw_negative_2--20260921T185702Z--bffd9aea7574` |
| yaw_negative_3 | PASS | `formal_yaw_negative_3--20260921T185739Z--7283d98e98d8` |
| yaw90_body_vx | PASS | `formal_yaw90_body_vx--20260921T185815Z--8377e6f3d18c` |
| tilted_level | PASS | `formal_tilted_level--20260921T185852Z--69af300dfc4b` |
| combined | PASS | `formal_combined--20260921T185934Z--63f86e6f04b4` |
| zero30 | PASS | `formal_zero30--20260921T190011Z--bd67b955eca7` |
| saturation_recovery | PASS | `formal_saturation_recovery--20260921T190108Z--ff65dadc5b6d` |
| fault_source | PASS | `formal_fault_source--20260921T190151Z--471045a78697` |
| fault_guard | PASS | `formal_fault_guard--20260921T190210Z--f84dbcea5522` |
| fault_controller | PASS | `formal_fault_controller--20260921T190229Z--17b7b8cc5dd0` |
| fault_adapter | PASS | `formal_fault_adapter--20260921T190249Z--5c5893c1a143` |
| fault_state | PASS | `formal_fault_state--20260921T190308Z--b9ffdd4ebded` |
| fault_state_frozen | PASS | `formal_fault_state_frozen--20260921T190328Z--cc22fbc85e39` |
| fault_clock_pause | PASS | `formal_fault_clock_pause--20260921T190347Z--008db61c0b7d` |
| fault_clock_rewind | PASS | `formal_fault_clock_rewind--20260921T190405Z--b80edd7f4b34` |
| fault_disarm | PASS | `formal_fault_disarm--20260921T190424Z--c1d5b69ea3ce` |
| fault_latch | PASS | `formal_fault_latch--20260921T190442Z--22dccb60cc65` |
| fault_rviz | PASS | `formal_fault_rviz--20260921T190501Z--2a54ca6baf39` |
