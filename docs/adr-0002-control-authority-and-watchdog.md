# ADR 0002：控制授权与 Stonefish 末端期限

日期：2026-09-22。状态：已实现，运行结论见 [验收报告](validation-2026-09-22-m1.md)。

锁定的 ROS wrapper 会永久保存并反复应用最近的 thrusterSetpoints，没有约束该缓存的
原生墙钟 watchdog。仅在 Python 退出回调中发零不能覆盖 SIGKILL。

决定在 Stonefish SimulationManager 增加默认空的物理步前 hook（补丁 0003）；
在 wrapper 增加可选 `uw_terminal` 接入（补丁 0004）。它仅依赖上游、rclcpp、
std_msgs 和 Boost，不反向依赖本项目控制业务包。哈希记录于 `vendor/source-lock.yaml`。
原 M0 场景没有该元素，仍移除全部原生推进器订阅；旧 schema 不启用 M1。

末端独立 ROS executor/线程及 10 ms 墙钟检查，互斥保护接收缓存；物理步前再次检查并
写入 Thruster::setSetpoint。Guard lease 0.25 s，输出新鲜度 0.20 s，原请求总有效期
0.25 s，ARM 首条输出宽限 0.20 s。任何期限到达都置零、撤销 token、锁存 FAULT。
物理步前检查阻止过期设定值继续作用；观测到的 RPM/推力按原模型逐渐衰减。

门控消息必须具有当前 run、会话 secret、递增序号与有效墙钟；输出另检查代际、token、
通道顺序、幅度、原始期限与输出序号。旧 ARM 不能延长授权。RESET 不 ARM。
原生读反馈包括实际 setpoint、omega/RPM、推力、反扭矩和接收/故障/应用时刻。

专用 fixture 用当前会话 secret 控制唯一 `/clock` 发布者暂停/回跳，物理继续推进；
明确注入时钟故障即撤权。它不发布第二个时钟，不更改刚体位置、质量、浮力或阻尼。
固定机体 fixture 只用于单推进器准静态诊断；闭环验收使用自由运动的原动力学。

权衡：这是进程内保护，覆盖外部源、Guard、Controller、Adapter 失联，不承诺
OS 卡死、Stonefish 自身损坏或真实硬件安全。授权是协作协议，不是防恶意客户端的平台。
补丁编译、逐通道反馈、SIGKILL 和恢复后重放均需实际运行证据，单元测试不能替代。
