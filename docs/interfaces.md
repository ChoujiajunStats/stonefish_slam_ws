# 公共接口：M0 观察、M1 控制与 M2 估计

所有下表名称为相对 topic，launch 注入 namespace；`/clock`、`/tf`、`/tf_static`
是 ROS 通用全局话题，跨独立世界由容器 DDS 网络隔离。frame 字符串显式带 namespace。

| 接口 | 类型 | 发布者 / 语义 / QoS |
|---|---|---|
| `sensors/stereo/{left,right}/image_raw` | sensor_msgs/Image | adapter；rgb8、640×480、optical；Best Effort / Volatile / depth 5 |
| `sensors/stereo/{left,right}/camera_info` | sensor_msgs/CameraInfo | adapter；共享外参、右 P[3] = -fx × 0.145 m；同图像 QoS |
| `sensors/imu` | sensor_msgs/Imu | adapter；FLU、m/s² 和 rad/s；同图像 QoS |
| `sim/ground_truth/odometry` | nav_msgs/Odometry | adapter；ENU pose、FLU twist；Reliable / Volatile / depth 5 |
| `state/odometry` | nav_msgs/Odometry | M0 显式复制上述真值；不是估计器；同上 |
| `diagnostics` | diagnostic_msgs/DiagnosticArray | probe；就绪与禁用控制；Reliable / depth 5 |
| `robot_description` | std_msgs/String | robot_state_publisher；Transient Local |
| `/clock` | rosgraph_msgs/Clock | 已打补丁 Stonefish，每物理步一个时间值；Reliable / depth 1 |

`sim/raw/*` 为后端私有观测，不允许未来算法直接订阅。原生 odometry 为
NED/FRD，适配器转换位置、姿态、速度、角速度和协方差。原生 sensor frame 名
在边界映射为明确的 `imu_link` / camera optical frame，不复用原生动态 TF。

原生 IMU 源码输出运动学线加速度，并未模拟完整的实机加速度计比力。
本阶段保留其语义并转换坐标，不自行添加重力或宣称通过 VIO 验收；M2
必须重新验收重力、偏置、采样与噪声模型。

时钟补丁的调度使用 steady clock；消息时间使用当前完成物理步时间，单位 ns。
图像渲染回调取最近物理步时间，尚未承诺双目曝光精确同步。
M0 停止/重启整个进程作为 reset，不提供原地 `/reset` 或步进服务。
probe 的启动时限、失联和总时限使用进程单调时钟，仿真暂停也能检测超时。

`odom → base_link` 仅由观察适配器在 `PRIVILEGED_DEBUG` 模式发布。
`base_link → imu_link/camera_*` 由 robot_state_publisher 静态发布。
RViz 机器人为尺寸示意盒，不是 BlueROV2 渲染模型或水动力模型。

M0 无任何 `actuators/thrusters`、`setpoint/pwm` 发布者或订阅者。
无 `control/body_velocity`、任务 action、depth、DVL、灯光控制接口；
这些属于后续阶段，不能将原蓝图的计划表视为当前能力。

公共图像/IMU 的无效数据会由诊断/探测报告，未定义为可供估计器使用的完整
失效模型。算法级新鲜度预算、协方差可靠性和图像同步门限由 M2 补全。

## M1 新增契约（仅 schema 2）

M0 上述禁用约束继续适用。M1 `state/odometry` 仍是 PRIVILEGED_DEBUG 真值。
pose 是原模型 O/base_link 原点在 ENU 中的位姿；twist 是该原点处的机体 FLU
线/角速度（包括旋转造成的点速度），不是世界系速度或 CG 点速度。
实际 CG 与 O 不重合；wrench 与分配力矩关于实际 CG、用机体 FLU 表达。
详见 [几何、CG 与推进器符号](m1-thruster-audit.md)。动态 TF 权威仍只有观察适配器。

| 相对接口 | 类型 | 唯一职责与 QoS |
|---|---|---|
| `control/request` | uw_interfaces/ControlRequest | 候选源；TwistStamped 加 run/source/token/generation/sequence/issued_steady_ns；Reliable/Volatile/depth 1 |
| `control/authority` | uw_interfaces/srv/Control | Guard；STATUS/ARM/DISARM/SELECT_SOURCE/CLEAR_FAULT/FAULT；标准 ROS service QoS |
| `control/approved` | uw_interfaces/AuthorizedCommand | Guard；原请求及绝对墙钟 deadline；Reliable/Volatile/1 |
| `control/output` | uw_interfaces/ActuatorOutput | body 模式 Controller；probe 模式 Guard；互斥；请求/预测 wrench、设定值、原授权；Reliable/Volatile/1 |
| `control/status` | std_msgs/String (JSON) | Guard 状态/原因/源/代际/ready/拒绝计数；Reliable/Volatile/1 |
| `control/controller_status` | std_msgs/String (JSON) | Controller dt、周期、积分、请求年龄；Reliable/Volatile/1 |
| `control/adapter_status` | std_msgs/String (JSON) | Adapter 转发/拒绝；Reliable/Volatile/1 |
| `sim/terminal/gate` | std_msgs/String (JSON) | Guard→原生末端：run、secret、gate_seq、sent_ns、op、generation、token；Reliable/Volatile/1 |
| `sim/terminal/input` | std_msgs/String (JSON) | Adapter→原生末端；run/token/代际、原始签发/截止、计算时刻、序号、名称、设定值；Reliable/Volatile/1 |
| `sim/terminal/status` | std_msgs/String (JSON) | Stonefish 末端实际状态、缓存/应用设定值、RPM、推力 N、反扭矩 N·m、运行时模型；Reliable/Volatile/1 |
| `sim/actuators/native_feedback` | stonefish_ros2/ThrusterState | 原生推进器状态，保留原模型轴/符号 |
| `control/trajectory` | nav_msgs/Path | Benchmark 由真实状态生成 ENU 轨迹；Reliable/Volatile/1 |
| `control/status_marker` | visualization_msgs/Marker | Benchmark RViz 状态文字；Reliable/Volatile/1 |

原生通道顺序仅封装在 robot profile 和执行边界。高层 body 命令不接触电机数组；
仅显式 actuator_probe 模式使用 ControlRequest 的 JointState，名称必须完整、唯一且按
原生顺序，position 字段在此契约专指无量纲设定值，不是关节角度。

高层目标 `[vx,vy,vz,yaw_rate]`，frame 必须是 `<namespace>/base_link`，m/s、rad/s。
angular.x/y 非零拒绝。合法有限但超出 `[0.4,0.4,0.2,0.4]` 绝对上限的请求拒绝，
不会静默裁剪。probe 上限 ±0.15；普通控制下游 ±0.6，原生末端另有 ±0.7 硬上限。
原始请求单调墙钟有效期 0.25 s；末端输出时效 0.20 s；ROS stamp 允许落后 0.25 s、
超前 0.05 s。所有缓存保留原截止时刻，控制器新计算时间不赋予旧请求新的寿命。

安全时钟为同容器主机 monotonic/steady，积分时间来自验证后的 `/clock`/状态 stamp。
跨机器单调时间不可直接比较，本轮不支持多容器/多主机控制链路。
零目标属于闭环；DISARM/FAULT 撤权并写零设定值，两者不能混用。
原生 RPM/推力有衰减过程，不能把预测 wrench 当作实际执行反馈。

只有显式诊断场景启用会话鉴权 fixture；时钟异常在唯一原发布者内产生。
权限边界与故障恢复见 [Guard 模块](module-guard.md) 和 [ADR](adr-0002-control-authority-and-watchdog.md)。

## M2 显式接口（仅 schema 3，运行验收中）

M0/M1 上述语义继续保持。M2 使用独立镜像/overlay 和场景属性：

| 接口 | M2 发布权与语义 |
|---|---|
| `sensors/imu` | perception；100 Hz FLU 比力（静止水平 z≈+9.81 m/s²）与 rad/s 角速度；姿态无效 -1，Best Effort/Volatile/5 |
| `sensors/stereo/{left,right}/image_raw` | perception；真实采样时间严格配对，最高 20 对/s，Best Effort/Volatile/5 |
| `sensors/stereo/{left,right}/camera_info` | 明确像素中心投影，理想畸变为零，右 P[3]=-fx×0.145 m；图像同 stamp/QoS |
| `state/odometry` | 仅 OpenVINS；局部 ENU pose、base_link/IMU 共点 FLU twist，最多 50 Hz，Reliable/Volatile/5 |
| `localization/status` | run/epoch、INITIALIZING/TRACKING/DEGRADED/FAULT、采样时间、特征与处理耗时，Reliable/Volatile/1 |
| `localization/trajectory` | 实际估计局部轨迹，Reliable/Volatile/2 |
| `perception/status` | 配对、丢弃、校验统计、比力语义和时钟锁存，Reliable/Volatile/1 |
| `sim/ground_truth/odometry` | 独立真值，frames 为 `<ns>/truth/odom`、`<ns>/truth/base_link`；仅评价/显式诊断激励，Reliable/Volatile/5 |

`<ns>/odom -> <ns>/base_link` 的唯一动态发布者是 OpenVINS。
真值通道不发布 TF、不送入估计器；估计未初始化时不发占位状态。
局部平移与 yaw 由传感器初始化决定，不等同地理绝对位置/航向。

GPU 采样时间来自共同绘制队列快照，并与 PBO 缓冲绑定。IMU/图像时间戳不
在处理中刷新。安全健康用 steady clock，积分仍用真实采样 dt。
消息恢复不解除估计故障锁存；本阶段以进程重启恢复。

当前 M2 运动诊断仍由 M1 控制器使用独立 PRIVILEGED_DEBUG 真值驱动，
Guard/Controller 的 `state_frame_prefix` 显式设为 `<ns>/truth`，状态订阅重映射
到真值接口。默认值仍是原 namespace，所以原 M1 行为不变。M2 不宣称已完成
估计状态驱动控制、导航或定点保持。详见 [ADR-0003](adr-0003-sensor-time-and-estimator-authority.md)。

M2 低速研究 profile 另设估计机体速度范数 1 m/s 的合理性上限，越界锁存
IMPLAUSIBLE_BODY_SPEED 并停止 odometry/TF。它不使用真值，也不保证识别所有
小于该上限的错误估计。传感器 fixture 若产生估计，独立评价仍检查其误差。


## M3：估计反馈与任务接口（显式 schema 4）

Guard、Controller、Navigation、Tasks 只读估计 `state/odometry`；真值仅供
Benchmark 评价。动态 odom→base_link TF 仍由 OpenVINS 唯一发布。
M3 可发布 READY_STATIC（完成传感器静止初始化，但尚未完成首次视觉更新）；
TRACKING 含义不变。新鲜的静止初始化允许显式任务 ARM，不等于启动自动 ARM。
Guard 独立检查状态、估计健康和原始传感器戳，任何一路超过 0.25 秒即撤权。

| 相对接口 | 类型 | 语义与权威 |
|---|---|---|
| mission/execute | uw_interfaces/ExecuteMission Action | Tasks 唯一服务端；显式授权、反馈、取消及结果 |
| mission/status | std_msgs/String JSON | 任务进度、单调时钟、终止原因；Tasks 发布 |
| navigation/goal | uw_interfaces/NavigationGoal | Tasks 心跳；run/任务/epoch/授权代际/序列/绝对期限 |
| navigation/path | nav_msgs/Path | 转换后的局部 odom 几何航点；Tasks 发布 |
| navigation/status | std_msgs/String JSON | 当前误差、目标速度、到点状态；Navigation 发布 |
| mission/status_marker | visualization_msgs/Marker | 仅供 RViz 显示，不参与控制 |
| control/request | 原 ControlRequest | source=navigation；唯一选择仍由 Guard 管理 |

消息使用 Reliable / Volatile / KeepLast(1)，包括任务心跳和控制输出；Action
使用 ROS 2 标准服务可靠性及状态 QoS。任务期限与安全时效用同一容器的 Linux
单调时钟，控制积分继续使用校验过的仿真 dt。目标 PoseStamped 是静态几何
而非反复打戳的速度命令；其有效性来自 action 生命周期、epoch 和绝对期限。

任务坐标可为 `<namespace>/odom` 或 `<namespace>/mission_start`。后者在接单
瞬间由估计位置/偏航定义，一次数值转换为 odom；CLI 使用后者。单位 m、rad，
水平目标 roll/pitch=0。局部 odom 不能解释为已知全球 ENU 北向或真实水深。
`authorize_arm=true` 是显式执行授权；同一 run 的 mission_id 不可重用。
取消后返回 CANCELED；任务墙钟超时返回 ABORTED / mission_timeout；正常完成
返回 SUCCEEDED，并分别记录末端中和是否有实际反馈。新消息不自动恢复 FAULT。

能力与边界见 [M3 ADR](adr-0004-estimated-navigation-and-missions.md) 和
[运行指南](runbook-m3.md)。

`mission_start` 只在该 Action 请求内定义，不向全局 TF 树发布一个会被不同任务
反复重置的 frame；实际发布的 `navigation/path` 和导航目标均为 odom。

M3-v4：`ControlRequest.valid_until_steady_ns` 可选绝对意图期限，0 保持旧 M1/M2
行为。Guard 的有效期限是 `min(issued+0.25s, valid_until)`；已过期的意图拒绝。
`issued_steady_ns` 不为表达短期限而前移或刷新，控制周期记录的 request age
保持真实含义。原生接收器继续使用既有 JSON deadline 字段，无需上游补丁。

新增消息字段需重建同一轮所有项目包。旧配置的运行语义保留，但不承诺旧版
二进制 CDR 与新消息定义可直接混读；历史 bag 应使用其自身消息定义/源码归档。

## 可选 Porth SLAM（2026-09-24）

仅在 schema 4 + `scene_profile: porth_sump9` + `slam_profile: rtabmap_stereo`
显式启用。普通启动 `execute_path: false`，`uw porth --arm` 生成带明确路径授权
的新配置。独立镜像、overlay 和数据预算，不改变旧配置语义。

| 相对接口 | 类型 | 权威和含义 |
|---|---|---|
| slam/info | rtabmap_msgs/Info | RTAB-Map，关键帧/回环/邻近匹配统计，标称 2 Hz |
| slam/map_graph | rtabmap_msgs/MapGraph | RTAB-Map，局部 map frame 中优化位姿与约束 |
| slam/cloud_map | sensor_msgs/PointCloud2 | RTAB-Map，来自双目数据的彩色三维点云 |
| slam/trajectory | nav_msgs/Path | 观察 probe 从实际 MapGraph 逐项转换，用于显示 |
| slam/known_cave | visualization_msgs/Marker | 观察显示，仅导入网格参考，默认隐藏 |

RTAB-Map 读取既有双目图像/CameraInfo 与 OpenVINS `state/odometry`，不读取
真值。相机订阅 Best Effort，里程计 Reliable，ApproximateTime 最大跨度 0.03 s；
相机本身仍为严格同采样时间的双目配对。地图/图状态订阅 Reliable/Volatile。
RTAB-Map 唯一发布 `<ns>/map → <ns>/odom`，不发布 base_link TF。
OpenVINS、任务与控制契约不变，map 的回环修正不回灌低层控制状态。

已知网格仅用配置出生点和首次 VIO gauge 进行显示配准，未送入 SLAM。
`m3-metrics.json` 中原 `unverified: mapping` 保留，新增 `slam-metrics.json`
和数据库重读记录提供独立建图证据。详见 [Porth 指南](runbook-porth-slam.md)。


## 可选全洞采集模式（独立于 M3 估计反馈导航）

`survey_profile: known_route_capture_v1` 与 `control_state_source: ground_truth_debug`
必须显式同时声明。场景限定 `porth_sump9`，路线文件有独立 SHA-256。
Guard 和 BodyVelocityController 订阅真值诊断话题，状态标记 PRIVILEGED_DEBUG；
OpenVINS 与 RTAB-Map 保持传感器/估计输入，不订阅真值或已知网格。

`./scripts/uw porth config/run.porth-survey.yaml --arm` 显式请求 ARM；先发零速度
目标稳定机体，最多 20 秒等待真实传感器初始化，随后执行规定路线。零速度
目标允许非零推进器，不能当成 DISARM。时效、授权代际和原生末端超时不变。
高层仍发四维 Twist 请求，不直接发送电机数组。

`survey_water_jerlov` / CLI `--water-jerlov` 只在此模式接受。其值写入解析配置与
场景光学证据，不改变传感器标定、物理步长或机器人水动力；相机和 SLAM 看到
实际渲染结果。两盏 native LIGHT 不属于八推进器命令通道，单独镜像补丁按
类型排除无推力光源。详见 [光学说明](porth-optics.md)。

运行进度保存 `survey-progress.json`，采集判定保存 `m3-metrics.json`，全表面
覆盖另用 `coverage.json`；它们互不冒充。SIGKILL 回归的预期负退出码和采集
FAIL 原样保留，保护动作结果单独保存 `safety-fixture-result.json`。

## 可选 ORB-SLAM3 在线双目（2026-09-24）

显式 `slam_profile: orbslam3_stereo` 仅限 Porth 真值控制采集配置；旧 RTAB-Map
profile 不变。ORB 节点订阅左右 RGB 与 ROS 时钟，**无 odometry / IMU / truth
输入**。标定由锁定机器人 profile 生成，20 Hz、640×480，按原始纳秒采样戳
严格配对；BestEffort / Volatile / KeepLast(3)，每侧应用层队列也最多 3 条。
输入最大年龄 0.30 s、显著未来阈值 -0.10 s，过旧/重复图像不重新打戳。

| 相对接口 | 类型 / QoS | 含义 |
|---|---|---|
| `slam/pose` | PoseStamped / Reliable, Volatile, depth 5 | ORB 原始在线 body pose，保留图像采样戳，只有 TRACKING 时发布 |
| `slam/status` | String JSON / Reliable, Volatile, depth 10 | 原生状态、特征/帧数、丢弃、延迟、map id/count；按新处理帧推进租约 |
| `slam/trajectory` | Path / Reliable, Volatile, depth 1 | 1 Hz 当前地图的优化关键帧，历史关键帧保留原戳 |
| `slam/cloud_map` | PointCloud2 XYZ / Reliable, Volatile, depth 1 | 1 Hz 稀疏地标，显示最多 20 万点；最终 PLY 保存全部点 |
| `map -> orb_body` | 动态 TF | ORB 唯一发布，采样戳与在线 pose 相同 |

map 是初始机体 FLU，单位 m/rad；左光学坐标转换包含相机安装旋转和杆臂。
纯双目没有全球 ENU 或重力测量。独立 OpenVINS 的 odom→base_link 保留，
但两套树不人为连接。RViz 机器人显示使用 orb_body 的原有网格外观。

图像预处理为 RGB2GRAY 后 CLAHE(3.0, 8×8)，不改变传感器话题或模拟水体。
`loop_edges` 是接受的无向回环边数；`map_count` 来自 Atlas，不能用文件数量
推断。原始在线轨迹与最终优化关键帧分别保存、分别评价。
本模式控制仍为 PRIVILEGED_DEBUG；详细输入隔离与运行证据见
[ORB 报告](validation-2026-09-24-orbslam3.md)。
