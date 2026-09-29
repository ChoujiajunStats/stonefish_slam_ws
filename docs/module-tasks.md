# Tasks：有界任务执行

`tasks/`（`uw_tasks`）提供 `mission/execute` 的 `ExecuteMission` ROS Action。
请求必须携带当前 run、未用过的 mission_id、显式 `authorize_arm=true`、1–12
个水平姿态航点以及 1–90 秒单调墙钟期限。普通启动不自动 ARM。

状态为 IDLE → ARMING → RUNNING → STOPPING → SUCCEEDED/CANCELED/ABORTED。
任务服务器仅在 Guard 就绪、DISARMED、估计新鲜时接单；ARM 仍由 Guard 再次
独立验证。并发任务、同轮次重复 mission_id、非法坐标/姿态和缺少授权都拒绝。
没有排队，也不隐式抢占正在执行的任务。

Action 反馈包含当前航点、距离和已用墙钟时间。导航到点后逐个推进目标。
完成、取消和任务超时会显式撤权；估计/控制故障会锁存 FAULT。终态结果还
单独报告 `terminal_neutral_verified`：只依据 Stonefish 末端实际接收状态，
不能将“服务请求已发送”当成执行反馈。超时和取消不承诺机器人立刻静止。

任务进程每 50 ms 发一次有绝对期限的目标心跳；它自己死亡后 Navigation、
Guard 和原生末端仍各自检查时效。Action 客户端退出不等于取消已经提交的
有界任务；CLI 的 Ctrl+C 会主动发取消请求，也可使用独立取消命令。
故障不自动恢复；估计器锁存故障需要进程冷启动，其他故障也必须显式复位。

相关：[Navigation](module-navigation.md)、[M3 运行指南](runbook-m3.md)。
