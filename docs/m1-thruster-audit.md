# M1 推进器与参考系审计

本页依据锁定提交和本轮实际接收反馈，区别于产品宣传参数。
源：Stonefish `6d285a955d19c9ecef3defd3f0605907f4594dbb` 的
`Library/src/actuators/Thruster.cpp`、`ScenarioParser.cpp`、`Odometry.cpp`；
BlueROV 场景 `6448383af6b7ef6083b0eac2c08102660591e318/scenarios/bluerov2.scn`。
可机读清单为 `robot/config/thrusters_m1.yaml`，生成场景时与固定 XML 逐字段比较。

## 通道与物理定义

共 8 个推进器，顺序与实际 `Robot::getActuator()` 一致。下表位置和轴均为
原始 base_link FRD；公开控制接口转换为 FLU。轴是推进器局部 +X。

| 索引 | 名称 | 安装位置 FRD / m | 推进轴 FRD | inverted | right-handed | 正原生设定值对应轴向推力符号 |
|---|---|---|---|---|---|---|
| 0 | FrontRight | (0.1355, 0.100, 0.0725) | (0.7071, -0.7071, 0) | true | true | - |
| 1 | FrontLeft | (0.1355, -0.100, 0.0725) | (0.7071, 0.7071, 0) | true | true | - |
| 2 | BackRight | (-0.1475, 0.100, 0.0725) | (-0.7071, -0.7071, 0) | false | false | - |
| 3 | BackLeft | (-0.1475, -0.100, 0.0725) | (-0.7071, 0.7071, 0) | false | false | - |
| 4 | DiveFrontRight | (0.120, 0.218, 0) | (0, 0, 1) | false | true | + |
| 5 | DiveFrontLeft | (0.120, -0.218, 0) | (0, 0, 1) | true | false | + |
| 6 | DiveBackRight | (-0.120, 0.218, 0) | (0, 0, 1) | true | false | + |
| 7 | DiveBackLeft | (-0.120, -0.218, 0) | (0, 0, 1) | false | true | + |

共同参数：直径 0.076 m，max_rpm=3600，kT_forward=0.167，kT_reverse=0.167，
kQ=0.016，水密度 1031 kg/m³。固定 XML 未指定 `thrust_coeff_backward`，
v1.3 parser 因而令反向系数等于正向系数。模型正反静态推力大小对称，
不代表实物标定对称；反向水动力、来流和转动瞬态仍来自实际原生模型。

原生 `s∈[-1,1]` 是转速目标的归一化值。`inverted` 首先翻转转速目标；
内置电机 PI 推进角速度，不能把设定值当牛顿。螺旋桨 handedness 再决定
轴向推力与角速度的关系。原生 setpoint feedback 返回外部符号，RPM 返回
实际有符号角速度。模型旋向由 `right` 决定，不从 cw/ccw 网格文件名反推。
3600 RPM 是 `omegaLim` 的目标标度；`Update()` 积分实际转速，没有把反馈 RPM
硬截断到该值。原生 `setSetpoint()` 截断到 ±1，本项目正常控制更严格地限制到 ±0.6。

## 静态近似与分配

令 n 为按 handedness 转换的有符号转速（转/秒），u 为原生代码定义的来流：

`T = ρ D³ |n| (D kT n − kT_forward u)`

静水固定体近似 u=0，RPM≈s×3600（另计 inverted），所以
`T ≈ native_sign × sign(s) × ρ D⁴ kT (3600/60)² s²`。
当前系数约为 20.68 N / s²；诊断 ±0.12 的理论推力约 ±0.298 N。
这仅用于 M1 初始逆映射。反馈中的 RPM/推力取自引擎 getter，预测 wrench
单独标为 predicted，不冒充测量。受载电机和内置 PI 的残余积分导致零设定值后
RPM/推力逐渐衰减，不能把中和等同刚体静止。

分配使用 6×8 矩阵。每列为 `[axis; r×axis + q_ratio×axis]`，
`q_ratio = handedness_sign × D × kQ/kT`；包含原生反扭矩。
r 为推进器安装位置相对**实际质心**的位移，全部转换到 FLU。
受限加权最小二乘和原生设定值变化率共同限制输出；静态来流近似的误差由反馈环补偿，
不宣称完整动态逆模型。

## 实际质心与状态参考点

本轮引擎报告质量 11.1888061061 kg、模型体积 0.01092 m³，
base_link 原点到质心的 FRD 位移为
`(-0.0054789746, -0.0000924473, 0.0769923863) m`。
数值在每轮 `allocation-model.json` 留档，由 `getCG2OTransform().inverse()` 获得；
不从 RViz 盒子估计。矩阵实测秩 6，奇异值约
`[2.0000, 1.4142, 1.4142, 0.4361, 0.3421, 0.2398]`，条件数约 8.34。

原 odometry 安装点位于 base_link 原点，pose 描述该点，线速度是该点的速度，
已通过 `getLinearVelocityInLocalPoint` 包含旋转偏置项，twist 用机体系表达。
M1 速度目标也定义在 base_link 原点；推力矩则统一在实际 CG 分配，两者不混用。
pose 转换 NED→ENU，twist 转换 FRD→FLU；动态 TF 仍由观察适配器唯一发布。
M0 原始 NED yaw=0 对应公开 ENU yaw=90°。
固定 `SimulationManager.cpp` 默认 g=9.81，动态世界重力为 NED `(0,0,+9.81)`；
对应公开 ENU `(0,0,-9.81)` m/s²。本轮不改重力、质量、浮力或阻尼。
控制器读取真值速度/姿态，不把 IMU 加速度直接当世界加速度，也不新增重力补偿估计器。

## 最后一跳审计

固定 wrapper 的 `thrusterSetpoints_` 无限保存最后一条数组，并在每步重新
`setSetpoint`；固定版本 `Thruster` 没有能约束这一 ROS 缓存的原生 watchdog。
原路径因此不能满足外部 Adapter SIGKILL 后可靠中和。
新 `uw_terminal` XML 入口与原 `ros_subscriber` 互斥，M0 不生成该入口。
补丁 0003 提供物理步前 hook，0004 在 simulator 进程内独立接收线程维护
原请求截止时间、Guard lease、输出超时和锁存故障。缓存过期不能由每步应用刷新。
