# 职责边界重构与运行验证：2026-09-29

本轮把领域实现移回所属包，保留 13 个根目录 ROS 包。容器构建与 95 项契约测试
通过；最终同版 M0、ORB 在线短程、RTAB-Map 路径回归均通过。早期 RViz 退出
失败保留，没有把 Probe PASS 改写成整轮 PASS。

## 实际变更

| 实现 | 变化与用途 |
|---|---|
| `localization/uw_localization/{orbslam3,rtabmap,artifacts}.py` | 接管原生标定/参数、Atlas 输出与 RTAB 数据库检查；显式输入 namespace、标定与默认文件 |
| `ui/uw_ui/{layouts,window}.py` | 接管 RViz 布局和 X11；只匹配本轮窗口，无控制权 |
| `simulations/uw_simulations/survey_scene.py` | 接管洞穴变换、灯光和水体设置 |
| `guard/uw_guard/configuration.py` | 路线安全包络，拒绝空或非有限路线 |
| `robot/uw_robot/{frames,description}.py` | 共用姿态数学与独立 SLAM 视觉模型；controller 保留数组兼容接口 |
| `app/uw_app/composition/estimation.py`、M2/M3 launch | 组装实现通过安装后的模块导入，移除按兄弟 launch 文件名动态加载 |
| `benchmark/`、`runtime/` | 评价不再导入控制器；runtime 只管理运行证据，不再理解 SLAM 地图格式 |
| CMake、package.xml、CLI Python 路径 | 安装 UI/定位 Python 模块，补齐真实依赖并移除无用依赖 |
| `test/test_module_boundaries.py`、`test/fixtures/` | 7 项新增测试；涵盖 launch 的依赖约束、旧配置一致性、坐标和场景契约 |

原有 88 项测试的断言语义保留，相关导入指向新职责包。
基线配置在修改前从 `878e0d7` 提取，5 种 RViz 布局、ORB 标定和两种 RTAB 参数
逐项一致。安装后的 Python 模块也已在无额外源码 PYTHONPATH 的容器中实际导入。
边界说明见 [模块职责](repository-structure.md)，范围见 [实施计划](cohesion-refactor-plan.md)。

没有新增上游补丁。vendor、机器人配置、根运行配置、DDS 相对 `878e0d7`
均无变化；原 `StoneFish_Nav` 的 319 个记录文件全部保持原哈希。

## 构建与命令

最终运行源码 `eb4b8da820fa6b37568098101071e974ef5ec7f6`，三轮均 dirty=false。
后续提交只补充报告与证据。镜像使用独立的 `stonefish-slam:orbslam3`，实际本地 ID：
`sha256:96d562e68ec6eca606e2b366f079112a17f3fd767ec292a129561f5f5e57c6a1`。
旧 `underwater-stack:*` 标签不变；上游 Eigen 弃用警告如实保留。

```bash
./scripts/uw build --profile orbslam3
./scripts/uw test --local
./scripts/uw test --profile orbslam3
./scripts/uw run config/run.empty_water.example.yaml --profile orbslam3
./scripts/uw porth config/run.porth-orbslam3-short.yaml --profile orbslam3 --arm
./scripts/uw orb-report porth_orbslam3_short_v2--20260929T022133Z--e233f46fa7cd --profile orbslam3
./scripts/uw porth config/run.porth.yaml --profile orbslam3 --arm
./scripts/uw slam-export porth_slam--20260929T022328Z--348bd7a0ba4d --profile orbslam3
```

构建 13/13 包通过，完整 overlay 重建 23.2 秒。宿主测试 87 PASS / 8 SKIP
（不安装宿主 NumPy/OpenCV）；容器 95 PASS / 0 SKIP。两个地图报告 CLI 均退出 0。
[构建日志](assets/cohesion-2026-09-29/build.log)、[测试日志](assets/cohesion-2026-09-29/container-tests.log)。

## 五次实际运行，包含失败

目录均位于 `$HOME/.local/share/stonefish-slam/runs/`：

| 病例 | run_id | 结果 |
|---|---|---|
| 首轮 M0 / c7ef3b8 | `bluerov_empty_water--20260929T021557Z--9f53a252a50e` | FAIL；60 秒 Probe PASS，RViz 退出 -2 |
| 5 秒 UI 诊断 / dirty 修复版 | `ui_close_diagnostic--20260929T021853Z--6758503e5234` | PASS；5 个进程退出 0，不充作 60 秒验收 |
| 最终 M0 / eb4b8da | `bluerov_empty_water--20260929T022003Z--465c44d95c2e` | PASS；60 秒连续观测，6 个进程退出 0 |
| 最终 ORB / eb4b8da | `porth_orbslam3_short_v2--20260929T022133Z--e233f46fa7cd` | PASS；约 6 m，12 个进程退出 0 |
| 最终 RTAB / eb4b8da | `porth_slam--20260929T022328Z--348bd7a0ba4d` | PASS；预设路径，14 个进程退出 0 |

合计 5 次，4 PASS / 1 FAIL；最终同版三个回归全部 PASS。不是三次相同病例的
重复试验，也没有重新完成全套 M1/M2/M3 正式评价。

首轮 RViz 的合成按键未可靠保存布局，标题仍有星号，关闭后最终被 SIGINT 终止。
修复在 ui 内完成：匹配本轮唯一窗口，验证焦点后用 XTest 发送完整 Ctrl+S，
检查保存标题，再发送 WM_DELETE_WINDOW。5 秒诊断与三个最终运行均正常关闭。
早期负退出码、失败 manifest 和 bag 均保留。

最终 M0：墙钟 66.38 秒，bag 33,143 条；图像/IMU/TF 沿用原门槛。
实际 graph 只有一个 `/clock` 发布者，没有推进器控制话题。Probe 的 `unverified`
保持原文，截图与 graph 独立补充。

ORB：目标截断为 6 m，路线进度 6.076 m；752/752 帧跟踪，0 lost / 0 dropped，
p99 延迟 0.05 秒。关闭后原生输出 62 个关键帧、3,209 个稀疏点。
原始在线位置 RMSE 0.03127 m，仅初始 yaw/平移对齐，不做全轨迹拟合。
Atlas 62/62 关键帧重读 PASS，最大 pose 分量差约 5e-8，原文件哈希未变。
控制仍使用 `PRIVILEGED_DEBUG`；ORB 输入仅双目。

RTAB：实时图 45 节点、56,163 点，报告观察到 18 次回环事件；不是全部独立回环的
人工复核。关闭后 SQLite 122 个 Node，完整性 `ok`，真实图像/深度 payload 非空。
原生重读导出 73,267 点、45 行姿态，原 DB 哈希不变；重读轨迹 RMSE 0.06371 m。
此分支路径控制采用 OpenVINS，真值仅用于独立评价。

## 证据与边界

[完整轮次索引](assets/cohesion-2026-09-29/summary.json) 包含实际路径、源码、镜像、
字节数与状态；同目录保留各轮原始 manifest、指标、退出记录和图形证据。

- [M0 RViz](assets/cohesion-2026-09-29/m0/rviz.png)
- [ORB RViz](assets/cohesion-2026-09-29/orb/rviz.png)、[Stonefish](assets/cohesion-2026-09-29/orb/stonefish.png)、[在线误差](assets/cohesion-2026-09-29/orb/report-online-tracking.png)
- [RTAB RViz](assets/cohesion-2026-09-29/rtabmap/rviz.png)、[实际地图](assets/cohesion-2026-09-29/rtabmap/slam-map.png)、[重读轨迹](assets/cohesion-2026-09-29/rtabmap/export-reloaded-trajectory.png)

大型原始证据在 runs，不进入 Git。ORB 报告位于
`reports/orb-evaluation-porth_orbslam3_short_v2--20260929T022133Z--e233f46fa7cd/`；
RTAB 报告位于 `reports/slam-export-20260929T022523Z-53a8539a/`。

本轮新增运行数据约 6.73 GB，包含失败录制；未删历史数据。所有本项目 run 容器与
网络已清理；其他项目仿真实例保持运行。未安装宿主算法依赖、修改驱动或全局 shell。

本轮验证职责拆分后的部署与有限路径运行，不宣称完整洞穴重建、长程精度改善、
全套故障注入重新验收或实机能力。Python/launch 的静态边界检查不等于证明所有
运行时 topic 依赖绝无问题；不同后端仍需各自的真实集成测试。
