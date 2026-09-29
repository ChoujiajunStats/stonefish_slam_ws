# Localization：M2 OpenVINS

实现包 `localization/`；固定上游库 + 自有 C++ ROS2 适配。已完成 m2-v3 本机验收，
具体范围及全部结果见 [M2 验收报告](validation-2026-09-23-m2.md)。

输入只有验证后的双目 RGB 和 FLU IMU，比力含重力响应。使用 KLT 双目 MSCKF、
静态惯性初始化、开始阶段的零速检测；不在线标定理想仿真外参、不使用真值
初始化或模拟特征，不实现建图/回环/导航。OpenVINS 内部 SLAM 特征仅是局部
滤波状态，不作为独立地图产品交付。

`state/odometry` 是真实估计输出，局部 ENU 位姿 + body FLU twist。100 Hz IMU
驱动传播，发布最多 50 Hz；时间戳属于被传播的采样时刻。相机处理等待对应
IMU 已覆盖，拒绝积压的旧图像。积分时间不依赖接收墙钟。

`localization/status` 报告 run、epoch、INITIALIZING/TRACKING/DEGRADED/FAULT、
特征数、处理耗时和拒绝数。安全健康使用单调墙钟；失联/停钟/回跳锁存后
停止里程计和 TF，必须新进程启动。消费者必须同时检查状态健康及采样时效，
不能只看曾收到过一条里程计。

真值评价和运动激励的隔离、四元数及协方差约定见
[ADR-0003](adr-0003-sensor-time-and-estimator-authority.md)。

## 初始化与诊断边界

本轮自由运动序列先用 M1 真值控制维持约 8 秒零速度目标，再施加低速运动。
OpenVINS 从原始传感器自行估计初始姿态与偏置，未锁定物理姿态。
初始零速更新的相邻帧位移阈值为 0.05 像素；早期 0.5 像素会把缓慢前进
误判为静止，导致首次有效估计过晚。此调整发生在正式冻结前，15 秒初始化
验收门槛未放宽。普通 DISARMED 自由漂浮不保证满足静止初始化条件。

0.5 秒单调墙钟传感器/时钟超时锁存第一故障原因；FAULT 后停止估计与 TF。
动态图订阅使用真实 publisher GID 验证本节点的 `odom -> base_link` 来源。
SIGKILL 后 DDS discovery 条目可能等待租约到期才消失；验收另外检查实际 -9
进程退出、新消息停止以及没有替代发布端点，不把缓存图条目视为活着的估计器。
这不是 DDS 身份认证或网络攻击隔离机制。

当前健康判定涵盖缺纹理、失联、积压、时间异常和基本数值合法性；没有完成
所有视觉混淆/外点场景或协方差统计一致性验收。不输出全局地图或地理航向。

正式 v1 复核暴露：只依赖图像位移的零速判定在倾斜棋盘固定体上失效，滤波器
曾发散而仍报 TRACKING。原始传感器病例 PASS 不覆盖这个估计错误，该批次被
独立复核否决。v2 保留 0.05 像素判定，同时启用 OpenVINS 自带惯性卡方检验
（乘子 1）；补充固定体若发布估计则必须满足位置/速度/姿态门槛的断言。
还新增本研究低速模式的 1 m/s 估计速度合理性上限，超出即停止发布并锁存
IMPLAUSIBLE_BODY_SPEED。这个上限不是真值校正，也不等同于完整故障检测或
协方差一致性证明。细节及各版本原始结果见 M2 验收报告。

零速检验保留上游逻辑：惯性统计检验与视觉低位移覆盖判据共同使用，并非两者
必须同时满足；相应阈值和速度条件都在冻结配置中。没有修改上游滤波数学实现。


M3 通过显式 `allow_static_initialization=true` 增加 READY_STATIC 发布状态；
只有传感器初始化成功且数据/数值检查通过才发布。该状态与首次视觉更新后
的 TRACKING 区分，M2 默认关闭此选项。详见 [M3 ADR](adr-0004-estimated-navigation-and-missions.md)。

2026-09-24 新增显式 Porth 场景的 RTAB-Map 后端配置
`localization/config/rtabmap_stereo.yaml`；OpenVINS 源码/参数未修改。
该后端组合双目测量与既有估计里程计，发布 map→odom、三维点云和优化位姿图，
保存关键帧数据库。它没有向旧 M2/M3 默认场景注入建图节点，也不把导入洞穴
网格送入估计。真实运行和重读结果见 [Porth SLAM 报告](validation-2026-09-24-porth-slam.md)。

## 可选 ORB-SLAM3 在线后端

`orbslam3_stereo` profile 增加独立 C++ 节点 `orbslam3` 与原生
`orbslam3_atlas_check`。只在新独立镜像中构建，旧镜像/默认 OpenVINS 路径不变。
ORB 使用双目图像自行跟踪与建图，不消费 OpenVINS/IMU/真值；当前不是
stereo-inertial 模式。ORB 稀疏地图不包含已知 Porth 网格或密集表面补全。

输入配对、有限队列、坐标转换与输出契约见 [接口](interfaces.md)。
初始机体 FLU 地图与 OpenVINS odom 分开；RViz 的 RobotModel 采用 ORB 位姿。
官方原生局部 BA/回环与 Atlas 后台工作保留，补丁只为编译、只读导出和
可靠关闭；关闭后地图与原始在线位姿分别落盘。实际故障、短程和全程结果见
[ORB 本轮报告](validation-2026-09-24-orbslam3.md)，命令见
[运行指南](runbook-orbslam3.md)。本次规定路线仍由 PRIVILEGED_DEBUG 控制。
