# M2 本机验收：2026-09-23

结论：**M2-v3 在本文限定的仿真双目/IMU 感知与状态估计范围内通过本机验收**。
同一冻结版本 13/13 正式病例 PASS，0 FAIL、0 NOT_RUN；其中三次轨迹冷启动全部通过。
最终镜像上另有 M0 原配置四轮各 60 秒回归 PASS（最后两轮补齐窗口截图），以及 M1 速度/末级 Adapter
失联两项选定回归 PASS。普通会话的实际 CLI 操作也已通过。

这不是导航、实机或估计状态驱动推进器的验收。OpenVINS 只接收双目/比力 IMU；
诊断运动仍通过 M1 真值反馈控制器、Guard 和原生推进器执行。
M0/M1 的历史报告、成功/失败目录与镜像标签均保留，未回填新能力。

## 基线、构建与冻结

- 本轮修改前核验 M1-v4 的 110 个冻结文件哈希、54 份历史正式结果。
  原始用户 M0 报告、已有磁盘证据与本轮复测分别记录，不合并计数。
- 本轮实际宿主 Ubuntu 24.04 / RTX 5090 / NVIDIA 580.178.04；未安装宿主 ROS
  或算法依赖，未改驱动、shell、Docker 权限；其他项目容器保持运行。
- 仓库没有 Git HEAD，全部文件未提交。修改前源码归档：
  `/home/hong/.local/share/underwater-stack/reports/m2-baseline-20260923T020801Z/`。
  没有自动 commit/push。每次运行保存真实 dirty 状态和源码归档。
- 最终镜像 `underwater-stack:m2` / `underwater-stack:m2-v3` 实际 ID：
  `sha256:71689218545bc2485aed1f6642594353dfcff335337067ba6b14ff0b6bd02caa`。
- 冻结 `m2-v3`：`2026-09-23T03:19:23.352234+00:00`，151 个文件哈希。
  [冻结文件](history/freezes/m2-freeze.json) 与 [病例清单](../test/m2-acceptance.yaml)
  每次正式运行前检查。M0/M1 来源锁、DDS XML、原配置/空水域/观察适配、
  机器人参数与 M1 控制增益的基线哈希保持一致。
- 保持单容器私有 IPC、512 MiB 容器 SHM、32 MiB/participant、4 MiB 最大消息、
  1024 槽、关闭内建传输、SYSTEM_DEFAULT discovery。
  DDS SHA-256 `ca6961088346410f2e4770396caecb17ade8848974bfa6b427a31d7d307f53f7`。

实际执行：

```bash
UW_IMAGE=underwater-stack:m2 UW_DOCKERFILE=docker/Dockerfile.m2 ./scripts/uw build
UW_IMAGE=underwater-stack:m2 ./scripts/uw test
./scripts/uw test --local
./scripts/uw m2-acceptance --phase formal --cases sensors estimation degeneration faults load --continue-on-failure
UW_IMAGE=underwater-stack:m2 ./scripts/uw acceptance --phase diagnostic --cases vx_positive_1 fault_adapter m0 m0 --continue-on-failure
# 补齐 M0 实际窗口截图，前两轮结果保留：
UW_IMAGE=underwater-stack:m2 ./scripts/uw acceptance --phase diagnostic --cases m0 m0 --continue-on-failure
```

构建成功：Stonefish/ROS wrapper、固定 OpenVINS/Ceres 与 10 个自有 ROS 包。
最终容器 64/64 契约测试 PASS，保留原 M0/M1 断言；本地 56 PASS、8 SKIP
（NumPy/OpenCV 仍仅在容器中）。单元测试不充当仿真验收。
构建/测试原始日志另存 `/home/hong/.local/share/underwater-stack/reports/m2-build-and-tests-20260923/`。
OpenVINS 实际动态链接到 `/opt/uw_ceres/lib/libceres.so.3`，见
`reports/m2-v2-linkage-resolved.txt`；v2/v3 使用相同镜像 ID。

## 实现与上游补丁

完整逐文件列表见 [M2 文件范围](m2-file-changes.md)。新增根目录
`perception/`（严格双目配对、输入校验、FLU 比力）和 `localization/`
（固定 OpenVINS 真正执行、协方差/TF、健康与锁存）。
`simulations/` 增加显式视觉 fixture 与独立 GT；`app/` 负责 schema 3 和组装。
Guard/Controller 只增加状态 frame 参数；CLI 按本轮配置加入 DDS 域。
`benchmark/`、`test/` 保存真实测试、冻结和指标；脚本保持薄入口。

新增补丁单独列出；父锁与 0001–0006 保留：

| 补丁                                                         | 用途                               | SHA-256                                                          |
| ---------------------------------------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| [0007](../vendor/patches/0007-m2-sensor-semantics.patch)   | 显式比力、随渲染/PBO 保存采样时间；默认路径不改 M0/M1 | b6d1cba2592cb03a44bca038728553db176d9158273877b7dcbc8597e3a594a3 |
| [0008](../vendor/patches/0008-m2-acquisition-stamps.patch) | 显式采样戳、无真值姿态 IMU、连续相机有限队列         | 03a6d8bb95ada1b98c79b7079f1c3a1461fbac7b3716dfb619fe9d2815bd0924 |

OpenVINS v2.7 固定 `93adc241390d13e99232652cf05cbe18a93c7bea`，Ceres 2.1.0
固定 `f68321e7de8929fbcdb95dd42877531e64f72f66`。原因、公式、许可证及来源见
[ADR-0003](adr-0003-sensor-time-and-estimator-authority.md) 与 [来源](sources.md)。
没有修改质量、浮力、阻尼、推进器参数或物理 100 Hz 步长。

## 正式全部病例

数据根目录：`/home/hong/.local/share/underwater-stack/runs/`。下表每行均有独立 run、manifest、metrics、
原始 JSONL/日志、MCAP、参数、源码/锁、图表和进程退出记录。
批次索引：`reports/m2-formal-c81fb4438f.json`。

| 病例 | 判定 | run_id |
|---|---|---|
| calibration | PASS | `m2_formal_calibration--20260923T031929Z--518ce904f4b5` |
| imu_tilt | PASS | `m2_formal_imu_tilt--20260923T031955Z--137f14833bfb` |
| trajectory_1 | PASS | `m2_formal_trajectory_1--20260923T032021Z--9bb8c7e5767c` |
| trajectory_2 | PASS | `m2_formal_trajectory_2--20260923T032117Z--f9657c28456a` |
| trajectory_3 | PASS | `m2_formal_trajectory_3--20260923T032213Z--6034b36ba7b8` |
| empty_water | PASS | `m2_formal_empty_water--20260923T032310Z--bf9ad465c8b2` |
| image_dropout | PASS | `m2_formal_image_dropout--20260923T032340Z--21c02249dbd4` |
| imu_dropout | PASS | `m2_formal_imu_dropout--20260923T032419Z--393b70b352ab` |
| clock_pause | PASS | `m2_formal_clock_pause--20260923T032459Z--edc112f17d45` |
| clock_rewind | PASS | `m2_formal_clock_rewind--20260923T032538Z--f07c3d8d162e` |
| estimator_kill | PASS | `m2_formal_estimator_kill--20260923T032617Z--f6a005f56378` |
| load_1 | PASS | `m2_formal_load_1--20260923T032656Z--a16762e086bc` |
| load_2 | PASS | `m2_formal_load_2--20260923T032809Z--6cd3005a1d49` |

传感器病例验证真实棋盘角点投影、米制基线、同采样时刻、倾斜比力和 frame。
固定体诊断只作为传感器证据；不替代自由运动估计。v3 的固定体保持静止初始化，
不产生虚构的运动估计。自由运动由真实八推进器产生；未直接写位姿/速度或理想外力。

三次轨迹均为相同视觉诊断场景的独立冷启动重复，不是不同随机种子或环境泛化。
速度表是估计与真实 body FLU 速度的误差。评价只用首个共同姿态对齐偏航和平移，
不拟合尺度或全程轨迹，统计整个有效估计段。

| 重复 | 首次跟踪 s | 位置 RMSE m | 位置最大误差 m | vx/vy/vz RMSE m/s | roll/pitch/yaw RMSE ° |
|---|---|---|---|---|---|
| trajectory_1 | 8.388 | 0.02016 | 0.02616 | 0.0018/0.0011/0.0010 | 0.0201/0.0482/0.1080 |
| trajectory_2 | 8.389 | 0.02265 | 0.02755 | 0.0019/0.0011/0.0010 | 0.0177/0.0453/0.0594 |
| trajectory_3 | 8.352 | 0.02337 | 0.02962 | 0.0022/0.0009/0.0008 | 0.0292/0.0344/0.0497 |

原门槛：初始化 15 s，位置 RMSE 0.20 m，速度各轴 RMSE 0.05 m/s，
roll/pitch 3°、yaw 5°，15 秒后的 TRACKING 比例 90%，发布时延 p95 0.20 s。
三次重复后段 TRACKING 均 100%；没有选最好窗口，也没有拼接早期版本结果。

| 故障 | 故障检测墙钟 s | 注入/显式诊断 DISARM 至末端设定值中和 s | 判定 |
|---|---|---|---|
| image_dropout | 0.517055 | 0.001200 | PASS |
| imu_dropout | 0.560301 | 0.001135 | PASS |
| clock_pause | 0.533349 | 0.001836 | PASS |
| clock_rewind | 0.088729 | 0.001876 | PASS |
| estimator_kill | SIGKILL -9；状态输出停止 | 0.001179 | PASS |

五项均在有效跟踪/非零执行输出下真实注入；消息恢复后没有自动重新 ARM 或清除
估计故障。时钟 fixture 使用本轮唯一原生时钟，不发布第二个 /clock。
SIGKILL 的真实 -9 退出码保留，过程状态为 COMPLETED_WITH_EXPECTED_FAULT。
**这些病例由测试程序显式 DISARM 真值控制的诊断运动，不能作为“估计健康自动
撤销电机控制”的证据。** 原生 RPM、推力和机器人余动均保留，不要求断推后刚体瞬停。

两轮图形负载各观察 60 秒，RViz、左右真实图像与 debug bag 同时运行；传感器沿用
M0 的 2 秒接收/1 秒 ROS 新鲜度门槛。估计最初约 8 秒仍在初始化，不称连续 60 秒
有效 VIO。动态图 GID 核验和唯一 /clock 均通过。

| 负载 | 位置 RMSE m | 时延 p95 s | 左/右图像数 | 15 s 后 TRACKING |
|---|---|---|---|---|
| load_1 | 0.02712 | 0.010 | 1196/1196 | 100.0% |
| load_2 | 0.02447 | 0.010 | 1196/1196 | 100.0% |

所有正式轮次首个时钟为 0.01 秒，初态、默认 DISARMED、新 run 身份均验证。
只承诺进程冷启动隔离，不宣称热重置、数值逐位确定性或 DDS 身份安全。

## M0/M1 本轮回归

同一 M2-v3 镜像和最终源码；沿用原病例及原断言，未覆盖历史目录。
M1 是选定范围回归，不把历史 54 次 PASS 记成本轮重跑。

| 项目 | 结果 | run_id |
|---|---|---|
| vx_positive_1 | PASS | `diagnostic_vx_positive_1--20260923T032924Z--3a6a17ca6db7` |
| fault_adapter | PASS | `diagnostic_fault_adapter--20260923T033000Z--c992bc019828` |
| m0 | PASS | `bluerov_empty_water--20260923T033019Z--993818e09bab` |
| m0 | PASS | `bluerov_empty_water--20260923T033130Z--a8e39a3b1fe6` |
| m0 | PASS | `bluerov_empty_water--20260923T033519Z--e871a6f27cab` |
| m0 | PASS | `bluerov_empty_water--20260923T033630Z--37e442ddc818` |

最后一个外部 Adapter 被 SIGKILL 后，Stonefish 继续推进，原生接收设定值在 **0.192378 秒**中和，低于原 0.50 秒门槛；真实 -9 退出及 FAULT 锁存保留。

M0 四轮各连续 60 秒、原 RViz/debug bag：原观测、TF、唯一时钟及正常退出通过。
独立 graph 检查均只有一个 /clock 发布者、没有推进器相关 ROS 话题。
首两轮因截图监听器到期缺少窗口截图，额外运行两轮补齐；四轮结果均保留。
原 probe 的 unverified 字段保留；额外 graph、bag 和实际截图独立补充，未改写原指标。
四轮 bag 首个时钟、初始 ENU 位置与 RGB 样本见各自 `bag-inspection.json`。

## 早期失败与修复

完整清单见 [全部运行索引](m2-run-index.md)，原失败文件均保留。

- 初次构建：GL 头文件 Scalar 类型不可见；改用 double。Ceres 2.2 不再提供
  OpenVINS v2.7 所需接口，固定隔离 Ceres 2.1；未升级估计器或修改其数学实现。
- 首次实际启动发现 OpenCV YAML 缩进和连续相机负频率转无符号队列问题，修复后
  重建。后续诊断暴露 NumPy bool 序列化与 rclpy 消息信息无 publisher_gid，修复并
  用 C++ 实际 RMW GID 核验 TF。原错误轮次仍为 FAIL。
- 首轮轨迹初始化 15.61 s 超过 15 s，FAIL 保留。收紧内部零速位移判定至 0.05 px；
  一个调参轮次 Stonefish 提前以 0 退出、未产生完成指标，原因日志未定位，不计通过。
- v1 的五个已执行病例按旧断言均 PASS，但复核发现倾斜固定棋盘 VIO 发散，位置
  RMSE 92.90 m 而状态仍 TRACKING。**整批复核否决**，其余 8 项 NOT_RUN。
  开启上游惯性卡方零速检验（乘子 1），加入 1 m/s 合理性锁存和固定体估计误差断言。
  旧数值验收门槛未放宽。独立复核证据 `reports/m2-v1-review/`。
- v2 执行五项 PASS 后，实际 CLI 查询暴露 DDS 域不一致；修复客户端读取本轮域。
  其余 8 项 NOT_RUN；v3 从头重跑全部 13 项，不复用前两版的成功结果。
- SIGKILL 后 DDS 图可能保留原端点直到租约过期；改用同一 GID、实际 -9 退出及
  消息停止联合判断。修复前的图断言失败仍保留。
- 普通 M2 会话实测 `status`、零速 ARM 8 s、vx=0.12 ARM 5 s、DISARM、状态查询，
  均返回成功；启动 DISARMED、两次授权代际分别 1/2，有限请求末尾显式 DISARM。
  run：`m2_manual--20260923T031806Z--794271962e0f`，见 `manual-cli-evidence.json`。

## 真实图表与证据

[速度/姿态](assets/m2-v3/velocity-attitude-unwrapped.png)、
[实际轨迹](assets/m2-v3/trajectory.png)、[故障时间线](assets/m2-v3/fault-timeline.png)、
[RViz 截图](assets/m2-v3/rviz.png)、[Stonefish 截图](assets/m2-v3/stonefish.png)。
来源与哈希在 [图像索引](assets/m2-v3/provenance.json)。所有图像来自本轮数据/窗口。

原内置图的 yaw 采用 Euler 主值，跨 ±π 时显示 360° 折返；原误差指标已使用周期
残差，不受影响。报告单独离线绘制解包后的角度显示，并核对重算指标与原指标相同。
原图/数据不覆盖，脚本、来源哈希在 `reports/m2-v3-derived/`，不是修改轨迹以通过门槛。

每轮留存 requested/resolved config、IMU/相机标定、模型/纹理锁、控制参数、源归档、
父/M2 锁、依赖清单、DDS XML/哈希、进程 PID/退出码、bag metadata、原始事件/指标。
最终运行文件哈希另核验与冻结一致。无残留本项目运行容器/网络；其他项目未停止。

本轮新增 runs 数据约 **15.08 GB**，低于 25 GB 预算；没有删除旧证据。

## 已知边界与结论

- 视觉通过范围为显式人工纹理、理想针孔/同步相机和研究噪声的仿真场景。
  不包含真实曝光/折射/硬件同步或传感器标定；无纹理空水域 DEGRADED 是预期。
- 未输出深度图、主动灯光策略、持久地图/回环；不把 OpenVINS 内部局部特征状态
  称作独立建图能力。未验证广泛视觉外点、遮挡、深度/光照变化或协方差统计一致性。
- 原生插值偶有移除零 dt 边界样本的上游警告；APT 仍按构建仓库解析。
  当前支持可追溯构建与测量，不代表全部上游问题或逐位重现已解决。
- 控制输入继续是明确隔离的 PRIVILEGED_DEBUG；估计状态推进器闭环、导航、
  ArduSub、学习、多 worker 和真实硬件均未实现/未测试。不自动进入 M3。

```text
M0_REGRESSION = PASS (4 × 60 s; final 2 include window screenshots)
M1_SELECTED_CONTROL_REGRESSION = PASS
M1_TERMINAL_WATCHDOG_REGRESSION = PASS
M2_SENSOR_CONTRACTS = PASS
M2_STEREO_IMU_ESTIMATION = PASS (bounded visual fixture)
M2_HEALTH_FAULT_INJECTION = PASS
M2_RESTART_ISOLATION = PASS (process restart)
M2_GRAPHICS_LOAD = PASS (2 × 60 s)
M2 = PASS (scope above)
STATE_SOURCE = OPENVINS_STEREO_IMU
DIAGNOSTIC_CONTROL_STATE_SOURCE = PRIVILEGED_DEBUG
ESTIMATED_STATE_CONTROL_IMPLEMENTED = NO
ESTIMATOR_IMPLEMENTED = YES
NAVIGATION_IMPLEMENTED = NO
REAL_HARDWARE_TESTED = NO
```

可直接运行的启动/解锁/停止命令见 [M2 运行指南](runbook-m2.md)。
