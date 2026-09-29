# M1 实现与本机验收：2026-09-22

M1-v4 已完成实际构建、测试及全部 54 次正式运行，**54 PASS、0 FAIL、0 NOT_RUN，M1 本机验收通过**。
正常控制、最后一跳失联保护、原 M0 回归三类结论均有本轮独立证据。
以下保留 v1/v2/v3 的全部失败；最终通过不拼接旧版本结果。
历史 M0 用户报告与本轮结果分别保留，不改写 [历史 M0 验收](runtime-validation-2026-09-21.md)。
实施前审计见 [范围与计划](m1-implementation-plan.md)，原生语义见 [推进器审计](m1-thruster-audit.md)。

## 最终本轮结论

统一冻结版本 `m1-v4`，批次 `m1-formal-0f6d569e49`：
八通道 8/8、控制权 2/2、四维单轴三次重复 24/24、附加控制/图形负载 7/7、
真实故障/UI 注入 11/11、原 M0 回归 2/2，全为 PASS。不存在以单元测试代替集成的必需病例。
每个方向的三个结果与全部 54 个 run_id 见 [完整表](m1-formal-results.md)。

**正常控制**：实际原生推进器驱动自由运动 BlueROV2；24 次单轴病例中，命令线速度
稳态 RMSE 最大 0.001224 m/s，命令 yaw rate 最大 0.000859 rad/s；
未命令线速度 RMS 最大 0.000036 m/s，非转向 yaw rate RMS 最大 0.000041 rad/s。
滚转/俯仰稳态 RMS 最大分别 0.122429° / 0.152710°，
回零线速度/yaw rate RMS 最大 0.002174 m/s / 0.001961 rad/s。
这些是规定稳态窗口统计；全段 RMSE、超调、瞬态峰值、位移、饱和和控制周期另存
`reports/m1-v4-performance.csv`，不以稳态结果掩盖起步/回零瞬态。
附加 yaw90、±5° 初态恢复、组合轴、30 秒零速度、饱和恢复均通过。

**最后一跳保护**：命令停止、Guard/Controller/末级 Adapter/状态适配进程 SIGKILL、
状态冻结、唯一时钟暂停/回跳、DISARM、锁存 FAULT 及旧授权重放均实际执行。
10 个中和病例最大实际应用零设定值延迟为 0.258719 s，低于冻结的 0.50 s。
模拟器在外部 Adapter 被杀死后继续推进物理，故障不靠退出回调处理。
11 个故障/UI 轮均有独立原生运动记录；RPM/推力衰减与残余运动见各轮图表。
UI SIGKILL 单独通过，核心控制继续；它不属于中和延迟统计。
预期被杀进程保留真实 -9；其他进程退出 0。没有将 FAULT 或 SIGKILL 改写为正常退出。

**M0 回归**：原配置两次 60 秒、RViz/双图像/原 debug bag 全部通过；
原观测/TF 门槛保持，唯一时钟，无推进器控制入口，正常退出全 0。
两轮 M1 完整图形负载也通过，原请求到原生接收端年龄 p99 最大约 32.36 ms。
Probe `unverified` 原样保留，新增控制与人工可视证据独立补充。
完整观测计数、首时钟、初始位置和 bag 大小见 [负载与回归](m1-load-regression.md)。

52 个 M1 冷启动均检查新 run、初始 DISARMED、零实际设定值；body 模式同时验证积分清零。
其中 49 轮实际注入上一轮原生命令并确认无效；`load_1`、`probe_0`、`authority_velocity`
三轮没有可用的上一轮控制消息，未虚称做过该项重放。所有 M1 全段状态均在冻结包络内，
ENU z 范围 -2.7652 至 -0.7925 m；没有到水面外计算通过结果。

54 轮的 110 个运行文件哈希、镜像、DDS、源码归档校验和与退出码均复核通过。
每轮 `evidence-index.json` 另记录原始日志、MCAP、图表和源码等实际文件的 SHA-256。
本项目容器/网络无残留，原先运行的其他项目容器仍在运行；本轮新增 runs 数据约
24.309 GB，低于 25 GB。没有删除旧证据。
最终另按仓库路径哈希核对并清理了本项目构建/测试的空 Compose 网络；无连接端点。
该网络在本轮前已存在，来源与移除记录为 `reports/m1-v4-dev-network-cleanup.json`。
机器可读结论为数据根 `reports/m1-v4-delivery.json`，独立审计工具归档于
`reports/m1-v4-inspection-tools/`；构建、57 项测试和两个 C++ 生命周期回归日志在
`reports/m1-v4-build-evidence/`。

```text
M0_REGRESSION = PASS
M1_ACTUATOR_MAPPING = PASS
M1_CONTROL_AUTHORITY = PASS
M1_TERMINAL_WATCHDOG = PASS
M1_BODY_VELOCITY_CONTROL = PASS
M1_ATTITUDE_STABILIZATION = PASS
M1_FAULT_INJECTION = PASS
M1_RESTART_ISOLATION = PASS
STATE_SOURCE = PRIVILEGED_DEBUG
ESTIMATOR_IMPLEMENTED = NO
NAVIGATION_IMPLEMENTED = NO
REAL_HARDWARE_TESTED = NO
```

## 实施与构建证据

本轮先读取源码、锁、场景、URDF、DDS XML、实际历史运行目录和未提交文件。
仓库原本没有 HEAD，全部工程文件未跟踪；没有 reset、commit 或 push。
修改前内容保存在 `.cache/m1/baseline.tar.gz` 与 `baseline-hashes.json`。
每轮保存完整源码归档/逐文件哈希；无 HEAD 时不能伪造 Git dirty diff。

镜像 `underwater-stack:m1` 实际内容 ID：
`sha256:03ba64865883949afb1b2a01ef293d5ad92e4bba11697cecc66fd8891b7d0550`（m1-v4）。
历史 v3 为 `sha256:f4e85e93b44fce91afdbc67f8c674d31b300cc2aff6bdd133084dc6c16f6afc1`。
历史 v2 为 `sha256:9a518e8fdae5a2d93ed8846c6f6afbc504253d2679c961e249172851c978810e`。
历史 v1 镜像 ID 为 `sha256:5f418d00804327e4cd103e58bc54fb6bab231188beb5f8fd1140ee030f36aa12`。
这是本地镜像内容 ID，未发布到 registry，不能把它称为远程 RepoDigest。
派生父镜像是已验收 M0：
`sha256:2a925f1bd1ff5d6eb1067e6f50f7160e232c98c6f66a6e6c3622a060de737ab6`。
Stonefish 库、两个上游 ROS 包、同版本 RViz common/默认插件和八个本项目包均实际构建成功。
未升级上游提交、未修改水动力参数，保留 cstdint 与原时钟补丁。

实际命令：

```bash
./scripts/uw build
./scripts/uw test
python3 test/rviz_lifecycle/run.py underwater-stack:m1-v4
./scripts/uw acceptance --phase diagnostic --cases mapping
./scripts/uw acceptance --phase tuning --cases vx_positive_1 vy_positive_1 vz_positive_1 yaw_positive_1 --continue-on-failure
./scripts/uw acceptance --phase formal --cases load_1 load_2 m0 m0 mapping authority velocity yaw90_body_vx tilted_level combined zero30 saturation_recovery fault
```

构建日志 `.cache/m1/build-1.log`、`build-3-offline.log`、`build-4-plots.log`；
`build-2.log` 保留了一次上游 fetch 超时失败。后续改用已验证父镜像中的固定源码重放补丁，
不通过 latest 绕过网络问题。APT/Python 版本清单、父镜像、锁/补丁哈希都在每轮证据中。
最终 57 项 Python 测试通过，日志 `.cache/m1/tests-v4-frozen.log`；另有修补后 C++/ASan 生命周期回归通过。保留原 41 项测试，
包集合断言扩展为实际新增的三个包，原 M0 配置/观测/TF/场景拒绝语义不放宽。

新增上游补丁有以下四项，源锁记录各自完整提交、顺序与哈希：

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `0003-pre-actuator-safety-hook.patch` | 原生推进器更新前的默认空 hook | `d5df9a50fb23eea40e99f5f41e2220780ba66054dc7509e1dde3ce70a84b905c` |
| `0004-terminal-command-lease.patch` | 独立末端接收/墙钟保护/执行反馈/诊断 fixture | `ea70ffc618403d5e0bfbc655526bfb6a6b8a3014e01ae78e4345c176b7a995de` |
| `0005-rviz-idempotent-image-unsubscribe.patch` | 同版本 RViz 14.1.23 图像取消订阅 UAF 修复 | `55fd803d8ee7922baf2bac3d88569a6b6491a985f4b5181b9c800902ad68d912` |
| `0006-rviz-release-view-manager.patch` | 释放 ViewManager 持有的 ROS 服务，避免遗留到 DDS 静态清理 | `39f3065889ad2406def504c1302cb5aa429a0ac6404f1ff15c8993b078eb5bd2` |

理由与源码边界见 [ADR](adr-0002-control-authority-and-watchdog.md)。
DDS 文件保持原 SHA-256 `ca6961088346410f2e4770396caecb17ade8848974bfa6b427a31d7d307f53f7`；
单容器私有 IPC、32 MiB participant、4 MiB 消息、1024 队列、关闭内建传输和
SYSTEM_DEFAULT 未改变。宿主没有安装 ROS/算法依赖，也未改驱动、权限或全局 shell。

## 冻结前的调参与失败

共 57 个实际预检/调参/CLI/内存诊断 run：46 PASS、11 FAIL；
另有 1 次启动前构建失败，NOT_RUN。完整清单在数据根 `reports/m1-preliminary-all-v4.json`。
较早的 50 轮汇总保留在 `m1-preliminary-runs-final.json`；新增 7 轮 RViz 诊断/修补预检
详见文末。内存调试运行不充当正式通过证据。所有失败目录保留，没有拿后续结果覆盖。

| 失败 run | 实际问题与处理 |
|---|---|
| `m1_probe_0--20260921T153431Z--0bad2d1022d8` | 初始主 ROS executor 被图形启动阻塞，末端状态过期；改为独立 executor，并要求 ARM 前健康稳定 1 秒。未放宽超时。 |
| `diagnostic_authority_validation--20260921T154916Z--f15ef5eb4d2c` | 测试运行器在首条末端消息前读取名称；改为读取已锁定 profile。 |
| `tuning_vz_positive_1--20260921T155507Z--c9f088dda677` | 控制指标 PASS，但观察节点退出异常，整轮 FAIL。 |
| `tuning_zero30--20260921T160450Z--fbafe26b299c` | 同类 rclpy 消息接收期间的信号异常，不能忽略非零退出码。 |
| `diagnostic_fault_state_frozen--20260921T160940Z--67873d89d7a3` | 安全处置约 0.21 秒、断言 PASS，但观察节点退出异常，整轮 FAIL。 |
| `v2_gui_save_close--20260921T165453Z--5cc83777df17` | RViz 关闭时报 Owner died，退出 -6；失败记录保留。 |
| `v2_gui_drained_close--20260921T165725Z--a7f38b3204b8` | 分阶段关闭仍发生 RViz -11；该预检没有通过。 |

最终信号处理只设置退出标志，由主循环关闭节点；状态冻结、时钟暂停恢复和 zero30
复测均 PASS、正常进程退出码 0。早期进程状态字段有 COMPLETED 而测试 FAIL 的轮次，
其原始退出记录仍保留；最终实现单独记录进程结果与病例判定，不将 SIGKILL 写成正常退出。

预检报告 `m1-tuning-65ba6d1987.json` 最后一项误关联了前一轮 run：当时 launch glob
包含 `__pycache__` 导致 overlay 构建失败，实际 yaw 病例没有启动，应为 NOT_RUN。
原报告不改写；此处及 preliminary 汇总给出勘误。已修正 glob 和启动失败的报告关联逻辑。

速度/姿态增益在有限试运行中没有数值扫参，当前值见控制器参数文件。M1-A 的八通道、
源停发、Guard 与最后外部 Adapter 死亡、授权校验先通过，才进入自由运动闭环。
冻结前已实际检查各轴正负、yaw90、±5° 初态、组合轴、饱和恢复与 30 秒零速度。
这些仅属预检，正式结论使用统一 m1-v4 下的新运行。

## 正式评价方法

`test/m1-acceptance.yaml` 预先保存全部输入、初态、时段、门槛、证据和清理要求；
`test/m1-freeze.json` 记录 runtime 文件/参数/镜像哈希。每个冻结版本内部保持代码/参数/镜像不变。v1 的退出故障修复明确升级为 v2，
v2/v3 仍发现退出错误后分别升级，最终 v4 重新执行全套，不混用版本结果。文档可补写；v1 清单中误包含的 README
作为纯文档排除，原清单哈希与排除记录保留。

四维单轴为 ±0.15 m/s 的 vx/vy、±0.08 m/s 的 vz、±0.15 rad/s 的 yaw rate，
各三个独立冷启动。零目标 5 秒、非零 10 秒、回零 8 秒、DISARM 2 秒，最后 4 秒
作为各稳态窗口。沿用用户门槛；报告全段误差/超调/饱和/位移，不拼接最佳窗口。
这些是重复运行，不是不同随机种子或场景泛化。

`full_rmse` 的全段是 ARM 到 DISARM 前的完整受控区间，包含起步零目标、非零目标、
饱和病例的恢复段及回零段；DISARM 后不存在速度跟踪承诺。原始样本和图表仍保留
ARM 前与 DISARM 后的实际运动，安全包络离线检查覆盖全部状态样本。

水平目标来自滚转/俯仰角反馈，不只是零 p/q。yaw rate=0 不承诺航向保持；
30 秒零速度不承诺位置定点。固定体只用于推进器诊断，所有正式速度病例使用自由运动
原始 BlueROV2。姿态初态只通过新场景进程设定，没有运行中写刚体位姿/速度。

末端中和计时起点为注入操作前的单调墙钟；观测到原生已应用零设定值的物理步时刻为终点，
门槛冻结为 0.50 秒。反馈约 10 ms 分辨率，保守使用第一条观察到零值的实际应用时刻。
同时保存接收缓存归零、FAULT、RPM/推力衰减与后续运动；不要求机器人瞬间静止。
时钟 fixture 操作唯一原发布者，物理继续推进；暂停/回跳即原生撤权，暂停后恢复
时钟仍保持锁存。无第二个 `/clock` 发布者。

M1 debug 两轮包含 60 秒非零闭环、左右图像、RViz 和完整 bag，观测 probe 沿用 M0
阈值，独立写 observation-metrics，不改原 probe 的 unverified。M0 两轮使用原配置、
原 60 秒窗口和完整 debug 录制。其余病例只录控制 profile，传感器继续发布。

## 证据阅读与边界

- [全部正式病例、三次重复与 run 索引](m1-formal-results.md)。
- [两轮图形负载及两轮 M0 原配置回归](m1-load-regression.md)。
- [八通道理论/实测、附加控制及故障运动补充表](m1-control-evidence.md)。
- [实际文件修改清单](m1-file-changes.md)；上游补丁单列于本报告。
- [运行指南](runbook-m1.md)：默认 DISARMED，有限 ARM、停止、故障恢复及回退 M0。
- 数据根 `reports/m1-v4-summary.json` 为机器可读汇总，`m1-v4-evidence-audit.json`
  核对各 run 的冻结运行代码，`m1-v4-runtime-baseline.diff` 是相对实施前归档的真实代码差异。

每轮 `figures/velocity-attitude.png`、`native-actuators.png`、`trajectory.png` 来自该轮实际
控制样本；故障轮另有 `fault-timeline.png`。图形负载轮的窗口截图与左右 RGB 样本
来自真实窗口和 MCAP，不合成海底或地标。所有大图留在 run，不复制进 Vault。
偏航图采用 [-180°,180°] 角度表达，穿越边界的曲线跳变不是物理姿态瞬移。
冻结前 CLI 会话 `manual_cli_preflight--20260921T161927Z--31be25b3e8d1` 实际验证
status→显式 ARM（0.10 m/s、3 秒）→DISARM，正常退出；默认启动未自行 ARM。

以下限制继续成立：

1. 状态为仿真真值 PRIVILEGED_DEBUG，没有估计器、导航、RL、建图、ArduSub、实机、
   多机器人或多 worker。没有承诺相机同步、IMU 实机等价性或真实双目标定。
2. 推力逆映射为静水近似。原生来流、电机 PI 和机体水动力仍实际运行；成功不代表
   实机标定或其他环境/载荷下的性能。只验证当前八推进器固定模型。
3. Guard/token 是私有 IPC 下的协作授权，不是恶意客户端身份隔离；管理服务和 session
   数据没有做通用安全平台。末端保护覆盖外部进程死亡，不承诺 OS/GPU/模拟器自身失效。
4. 中和是已验证零设定值并撤权锁存；不是刚体瞬间静止或水下真实物理安全。
   原生电机积分造成零输入后的残余 RPM，实际曲线完整保留。
5. 只承诺冷进程重启；不承诺热重置、随机场景泛化或数值逐位确定性。
   probe 模式不启动 Controller，因此积分清零检查只在 body_velocity 模式有物理含义。
6. APT 依赖按构建时仓库解析，记录清单但没有全仓快照锁；GPU 驱动由宿主提供。
   上游 Bullet 编译警告仍存在。本轮支持可追溯构建，不声称消除了所有上游问题。

未由本任务修改 Obsidian workspace 状态；它的编辑器自动变化不计入代码修改清单。
历史 M0 报告、配置、DDS XML、补丁 0001/0002 和原始蓝图哈希均与实施前一致。

正式故障轮另加只读原生 Odometry 观察器，脚本留在各轮 `inspection-tools/`。
它直接订阅原 wrapper 的 `sim/raw/odometry_ned`，记录 NED/FRD 原值及数值转换后的
ENU/FLU，写入 `native-motion.jsonl` / `native-motion-inspection.json`。这使公共状态
适配进程被 SIGKILL 后仍有实际运动记录，不用冻结的公共状态冒充机器人真实运动。
该诊断观察器不发布控制/状态/TF/clock，不替换控制状态源，不更改冻结实现或参数。

## v1 正式失败与 v2 修复边界

旧正式批次实际完成 45 次：44 PASS、1 FAIL，剩余 9 次 NOT_RUN；最后在途
`formal_fault_adapter--20260921T164619Z--cdb1efdedf3f` 在批次协调器停止后自行完成，
因此原批次 JSON 只有前 44 条，完整补充清单为 `reports/m1-v1-closed.json`。
没有改写该轮 manifest 或原批次结果。v1 的 PASS 只保留为历史，不充当 v2 的正式结果。

唯一正式失败为 `formal_load_1--20260921T164225Z--489d1d617099`：控制与 60 秒观测
均 PASS，RViz 在退出时 -11，因此整轮 FAIL。第二轮 v1 图形负载通过也不能覆盖它。
后续 GUI 预检保留了直接 Qt 关闭 -6 和分阶段关闭 -11 两次失败；调试器下未复现，
不把调试器下正常退出当作修复证明。

v2 当时的处理是在数值上把状态文字放到 ENU 固定坐标系的机器人上方，避免它需要动态 TF；
结束时先停止本轮数据进程，再保存本轮生成的布局并关闭 Qt 窗口，保留关闭前布局
`inspect.before-close.rviz` 和 `gui-close.json`。RViz 的保存交互依据
[上游 prepareToExit 实现](https://github.com/ros2/rviz/blob/jazzy/rviz_common/src/rviz_common/visualization_frame.cpp)
核对。v2 当时没有修改上游 RViz 或掩盖退出码，也未证明其崩溃的完整底层根因。
未开启调试器的 30 秒预检和一次完整 60 秒闭环图形负载复测均正常退出；后者是
`diagnostic_load_1--20260921T170224Z--07ed2c60e2a4`。

新增 M0 非零退出断言，使 probe 已 PASS 后的进程失败同样使整轮失败。M1 debug
仅改为 MCAP zstd_fast 无损存储，原话题、图像发布、RViz、DDS 和安全门槛不变；
M0 的原 debug 录制方式不变。此项节省重复评价的磁盘空间，未关闭图像降低负载。
v2 镜像重建日志 `.cache/m1/build-v2.log`，控制数值增益/分配/水动力/失效期限保持原值。
冻结归档见 `test/frozen/m1-v1.json`、`test/frozen/m1-v2.json`；最终冻结见文末 v4 节。

## v2 退出故障与后续诊断

v2 批次 `m1-formal-fbfc4162be` 原始记录 47 次：45 个病例判定 PASS、2 FAIL，
剩余 7 次 NOT_RUN。两轮负载 `formal_load_1--20260921T172610Z--5e1a29e64e1f`、
`formal_load_2--20260921T172739Z--e88d1932e42d` 均是控制/60 秒观测通过、
RViz `free(): corrupted unsorted chunks` / -6，因此整轮 FAIL。

暂停时先向 CLI 外层 wrapper 发 SIGTERM，未同时停止其独立 campaign 子进程，
后续已核对命令行并显式终止该子进程，未操作其他项目。晚启动的
`formal_fault_state_frozen--20260921T173045Z--ba914d2d9ee9` 已包含诊断 launch 修改，
原始指标虽 PASS，但冻结哈希不一致，不能计入 v2 正式通过；冻结一致的 PASS 为 44。
完整勘误保存在 `reports/m1-v2-closed.json`，原始 manifest 和批次不改写。
下一版 campaign 在每个病例启动前重新核验冻结文件/镜像，避免批次跨越代码修改。

`diagnostic_load_1--20260921T173103Z--9ce8aa56a28f` 在 GDB 下正常退出，
不据此宣称修复。`diagnostic_load_1--20260921T173315Z--9fe575260e67` 的
AddressSanitizer 辅助诊断捕获 `SharedMemTransport::clean_up()` /
`DomainParticipantFactory` 静态销毁路径的崩溃。它是排查线索，不等于已证明完整根因。
独立 `underwater-stack:m1-rviz-debug` 只增加容器内 Valgrind/libc 调试符号，APT
日志显示没有升级现有包；不用于正式评价，不覆盖 M0/M1 标签。
第一次短时 Memcheck 诊断在 RViz 尚未初始化完时收到退出请求而 FAIL，
`v3_rviz_memcheck--20260921T173531Z--5525fb5351bc` 保留；后续延长的是该诊断的
观察/退出等待时间，没有修改控制或正式验收门槛。

## v3 同版本 RViz 修复与重新冻结

完整 Memcheck 诊断 `v3_rviz_memcheck_full--20260921T173657Z--ffc52f37d368`
记录了 ImageDisplay 在 dock 隐藏后析构时重复断开已释放回调的 UAF。
最小回归在旧镜像稳定失败、补丁镜像通过；源码、补丁和 ASan 日志见
[生命周期诊断](m1-rviz-lifecycle-fix.md)。新锁仅增加同版本 RViz 14.1.23，
Stonefish / wrapper / BlueROV 原提交保持不变，不改 DDS 配置或 Fast DDS 二进制。

未开启调试器的两轮完整 60 秒负载预检：
`diagnostic_load_1--20260921T174752Z--2430891426b8`、
`diagnostic_load_2--20260921T174920Z--6b80dc6990de`，
控制与观测 PASS，所有正常进程退出 0。它们是预检，不充当正式两轮。

v3 于 UTC 2026-09-21 17:50:54 冻结 105 个运行文件、配置、补丁及测试文件，
镜像构建日志 `.cache/m1/build-v3.log`。控制增益、动力学、DDS、超时和验收门槛
与 v2 相同；campaign 现在每个病例前重新核验冻结哈希及镜像。
正式批次 `m1-formal-7b87e5044d` 从头执行全部 54 次。

## v3 失败及后续资源所有权诊断

`formal_load_1--20260921T181231Z--5391c336bea1` 与
`formal_load_2--20260921T181400Z--76bd0ca03403` 的控制、60 秒观测均 PASS，
但 RViz 退出 -6；两轮均 FAIL。进程 maps 已证明确实加载了修补版 ImageDisplay，
没有误加载旧插件。完整闭合清单 `reports/m1-v3-closed.json` 为 41 轮，
原批次 JSON 只有暂停前的 40 轮；在途第二轮单独补入闭合清单，未改写原始记录。
41 轮运行代码均与 v3 的 105 文件冻结一致，故障注入和 M0 回归尚未执行。

`v4_rviz_memcheck_patched--20260921T181707Z--5ba6127f198d` 确认图像取消订阅
UAF 已消失，但还存在 Fast DDS 静态销毁时的端口资源访问错误。读取 RViz 同版本源码
发现 VisualizationManager 创建 ViewManager 后没有释放，而 ViewController 持有 ROS
reset_time 服务。随后用实际 RViz 对象所有权回归验证最小修复，结果见下一节。
DDS XML 和二进制未修改。

镜像保留核查：未执行 prune/rmi，但 v1/v2/v3 在更新 M1 标签后已不能通过旧 ID
直接检索；它们的源码归档、构建/依赖日志和运行证据仍保留，不承诺旧镜像可直接启动。
最终 v4 另加独立本地标签 `underwater-stack:m1-v4`；M0 原标签/ID 始终未变。

## v4 冻结与完整重跑

补丁 0006 的实际 QPointer 回归在未修补版报告未销毁对象并退出 139，修补后
对象销毁且退出 0。最终正式镜像内再次执行 `python3 test/rviz_lifecycle/run.py
underwater-stack:m1-v4`，退出 0；ASan 图像取消订阅用例也在构建中通过。
57 项容器 Python 测试再次通过。构建日志 `.cache/m1/build-v4.log`。

v4 于 UTC 2026-09-21 18:34:56 冻结 110 个文件，镜像独立保留为
`underwater-stack:m1-v4`。正式批次 `m1-formal-0f6d569e49` 先执行图形与 M0，
再重跑其他全部病例。控制增益、物理参数、DDS 二进制/XML 与所有门槛未变。
实际命令：

```bash
./scripts/uw acceptance --phase formal --cases load_1 load_2 m0 m0 mapping authority velocity yaw90_body_vx tilted_level combined zero30 saturation_recovery fault
```

仓库无 HEAD，因此每轮额外保存 `runtime-vs-pre-m1.diff` 与来源元数据，
它是对实施前归档的真实差异，不冒充 Git HEAD dirty diff；完整文档快照仍在
该轮 source.tar.gz。最终逐病例全段/稳态/超调/饱和/周期/延迟/位移已另汇总为
`reports/m1-v4-performance.csv`。报告日期按上海时区，run_id 和记录时间使用 UTC。
