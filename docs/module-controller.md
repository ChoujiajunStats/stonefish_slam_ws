# M1 机体速度与水平姿态控制

实现：`controller/uw_controller/core.py`、`node.py`，默认参数在
`controller/config/defaults.yaml`。组装和运行配置分别属于 `app/`、`config/`。
状态仍是 **PRIVILEGED_DEBUG**，没有估计器。

目标为 base_link 原点 O 的 FLU `[vx,vy,vz,yaw_rate]`，单位 m/s、rad/s。
四维速度 PI 加独立的滚转/俯仰角反馈和角速度阻尼，使姿态趋向 ENU 水平。
`yaw_rate=0` 只控制偏航角速度，不保持航向；零速度不保持位置，也不代表断推力。
50 Hz 墙钟调度，积分采用有效且推进中的仿真 dt（0 < dt ≤ 0.1 s）。
重复时间戳不积分；授权失效、DISARM、FAULT、代际改变或异常 dt 清除积分和历史输出。

实际推进器位置、方向、旋向、反扭矩来自锁定模型，详见
[推进器审计](m1-thruster-audit.md)。分配矩阵按实际 CG 计算 `r×F`，
包含螺旋桨反扭矩；6×8 矩阵满秩，实测条件数约 8.34。
运行时从原生模型导出质心和几何，再核对 robot profile，不能拿 RViz 示意盒代替动力学。

分配采用带力矩权重的有界最小二乘（投影迭代），限幅后用静水二次推力关系逆映射到
原生设定值。实际水中来流和电机动态会使实际推力偏离预测；这是初始工程近似，
不是实机推进器标定。记录 requested wrench、predicted wrench、原生实际 RPM/推力，
预测值不标记成测量值。没有额外重浮力补偿，PI 处理当前静态偏置。

速度请求限幅由 Guard 显式拒绝；控制器另有 wrench、积分、设定值幅度及变化率限制。
anti-windup 用分配/变化率限制后的预测 wrench 与请求 wrench 之差回算。
默认设定值限幅 ±0.6、变化率 1.5/s。输入或分配无效时停止输出，由独立末端期限中和。

调参与正式评价使用不同 run；冻结清单为 `test/m1-freeze.json`，病例为
`test/m1-acceptance.yaml`。实际结果见 [M1 验收](validation-2026-09-22-m1.md)。
M2 的诊断控制保留真值反馈；M3 显式 schema 4 接入估计反馈与上层航点任务。

当前正式冻结为 m1-v4；增益文件的内部版本仍是 m1-v2，因为该组数值未改动。
冻结版本覆盖完整系统及镜像，不把仅修复 RViz 的版本变化误称为重新调参。


## M3 接线

M3 复用相同的 BodyController、分配、增益和执行适配；Controller 的
`state/odometry` 指向 OpenVINS，且 frame 为公共 odom/base_link。
Guard 自行检查估计健康，Controller 仍独立检查状态和原请求期限。
高层导航的航点偏航误差生成 yaw_rate 请求；原速度契约中 yaw_rate=0
依旧只表示零偏航角速度。水平姿态稳定仍在控制器内完成。
