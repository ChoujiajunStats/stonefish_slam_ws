# M1 唯一控制权与故障锁存

`guard/uw_guard/node.py` 实现 DISARMED / ARMED / FAULT，默认 DISARMED。
`contracts.py` 验证输入；`config/defaults.yaml` 定义包默认参数。
普通 launch 不自动 ARM；有限测试运行器在就绪后显式请求 ARM 并记录事件。

ARM 核查 simulation_research、当前 run、状态与时钟推进、映射、末端状态、
唯一 `/clock` 及各控制链路发布者、无锁存故障，并要求就绪稳定 1 秒。
选择源仅允许 benchmark 或 cli，一次只签发一个 run / generation / token 授权。
切换源撤销旧授权并回到未解锁状态；恢复输入不自动解锁。

Guard 接受原始 ROS 时间戳和单调墙钟签发时间：ROS 消息最多落后 0.25 s、
最多超前 0.05 s，上游墙钟有效期 0.25 s。下游继承原请求的绝对截止时刻，
不重新延长缓存请求期限。非零 angular.x/y、错误 frame、非有限数、错误授权、
重放序号、非法通道均拒绝；有限但超过速度/诊断幅度上限的请求显式拒绝。

最终 watchdog 在 Stonefish 进程内，详见 [ADR](adr-0002-control-authority-and-watchdog.md)。
杀死 Python Guard 或 Adapter 不会杀死 watchdog。Guard 心跳、原请求、外部输出
三个期限分别约束执行，不用重复缓存写入刷新 watchdog。

安全包络：ENU z 在 (-4.5,-0.3) m，水平坐标绝对值 <8 m，滚转/俯仰 <25°，
线/角速度各分量绝对值 <1.2。超出包络锁存 FAULT；这些只是仿真研究终止条件，
不是实机安全认证。水下断推力仍可能漂移、旋转、上浮或下沉。

控制权是单容器私有 IPC 下的协作式授权。随机 token 防误用/旧代际重放，
并非 DDS Security，也不能抵御同容器内读取 token 或调用管理服务的恶意进程。
不得把普通 topic 名称或发布者计数当作身份安全隔离。

故障清除是显式 CLEAR_FAULT；健康恢复后回到 DISARMED，还需新 ARM。
使用步骤见 [M1 运行指南](runbook-m1.md)，实际证据见 [验收报告](validation-2026-09-22-m1.md)。

## M3 显式估计反馈模式

schema 4 增加 `navigation` 候选源，Guard 自己订阅 OpenVINS 健康状态，独立核对
run、epoch、发布权威、原始图像/IMU 戳及接收墙钟时效。状态或健康过期、估计
退化/故障会锁存，不能靠 Navigation 重发旧目标维持 ARM。

M3 位置包络相对首个有效估计：水平各轴 ±1.5 m，竖直 ±0.6 m；roll/pitch
峰值 25°，线/角速度各分量 0.6（SI）。位置协方差对角必须有限且在 [0,0.25]。
这些是局部仿真中止条件，不能称为真实深度或完整定位可靠性检验。Benchmark
另行核验真实 ENU 深度、行程。M0/M1/M2 的原有配置和边界保持原行为。

`control-status.json` 是每 0.1 秒更新的原子快照，M3 CLI 查询需验证本 run 和
0.5 秒新鲜度；停止后不再把历史 ARMED/TRACKING 显示成当前状态。
