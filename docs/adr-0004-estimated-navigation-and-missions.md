# ADR 0004：估计反馈、局部目标与有界任务授权

日期：2026-09-23。状态：已实现，运行验收另见最终报告。

M2 保留了真值诊断控制；M3 显式 schema 4 将 Guard、Controller、Navigation、
Tasks 全部接到 OpenVINS 估计里程计。真值只给 Benchmark 作独立误差/包络评价。
没有真值回退路径；估计过期、退化或故障会撤销控制权。保持已有 Stonefish
原生末端 watchdog 和单容器私有 IPC/DDS 配置，不增加上游依赖或水动力修改。

锁定 OpenVINS v2.7 的 `initialized()` 还要求完成首次视觉更新，而
`initialized_time()` 在传感器静止初始化成功后已经有效。本项目只对 M3
启用静止估计发布，状态明确叫 READY_STATIC；完成视觉更新后才叫 TRACKING。
M2 默认选项仍关闭。该实现使用已核对的公开访问器，无需上游补丁，也不使用
`initialize_with_gt`。原始源码依据是父镜像内 commit
`93adc241390d13e99232652cf05cbe18a93c7bea` 的 VioManager.cpp / VioManagerHelper.cpp；
[OpenVINS 接口说明](https://docs.openvins.com/classov__msckf_1_1VioManager.html)
仅辅助解释，实际行为以锁定源码为准。

无全球定位时，odom 原点和偏航是估计器的局部规范。接口支持：

- `namespace/odom`：明确的局部绝对位置/偏航。
- `namespace/mission_start`：接单时估计位置和偏航建立的水平相对坐标，x 为
  起点前向、y 为起点左向、z 沿重力向上；目标转换后在 odom 固定，不随机器人移动。

Guard 的 M3 位置包络相对首个有效估计定义，不能将局部 z 直接当作海水绝对
深度；Benchmark 独立检查真实 ENU 深度和已知诊断场景行程。

ExecuteMission Action 是持续、有绝对期限的用户意图，任务服务器保持其
心跳。Navigation 不能给缓存意图延长寿命，输出沿用心跳签发时间且受任务
绝对期限约束。取消是 Action 协议的一部分；成功/取消/失败结果与进程退出码、
安全锁存状态分开记录。PID 故障注入限于本 run 的注册进程。

这仍是受信任仿真容器内的控制权协调，不是面对恶意 DDS 参与者的身份安全平台。

正式 v3 的短任务超时测试暴露了一项契约实现错误：为收紧截止时刻而前移
`issued_steady_ns`，使请求年龄被人工增加，P95 达 155 ms，超过 150 ms 门槛。
超时与中和本身成功，但该病例仍保留为 FAIL。v4 新增可选
`ControlRequest.valid_until_steady_ns`（0 表示旧契约），Guard 取原请求 0.25 秒
期限与意图绝对期限的最小值。签发时间原样保留；不通过改门槛或剔除最后窗口
把结果改成 PASS。重新冻结并重跑的结果见最终报告。
