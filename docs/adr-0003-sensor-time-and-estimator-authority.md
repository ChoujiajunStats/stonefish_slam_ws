# ADR-0003：传感器采样时间与估计状态发布权

日期：2026-09-23。状态：已实现；本机证据见 [M2 验收报告](validation-2026-09-23-m2.md)。

M2 使用固定 OpenVINS v2.7 的独立 C++ 库，通过自有 ROS2 适配器接收双目
图像与 IMU。适配器不订阅真值、不调用 `initialize_with_gt`、不使用模拟特征
接口。库接口和初始化行为以锁定源码为准，参考
[OpenVINS 安装说明](https://docs.openvins.com/gs-installing.html) 和
[v2.7 源码](https://github.com/rpng/open_vins/tree/93adc241390d13e99232652cf05cbe18a93c7bea)。

容器实际构建发现 Ceres 2.2 删除了该版本使用的 LocalParameterization 接口；
[Ceres 版本记录](https://ceres-solver.readthedocs.io/latest/version_history.html)
说明了这次 API 迁移。选择在 `/opt/uw_ceres` 固定 Ceres 2.1，保留估计器算法
原实现。APT 的 Ceres 2.2 仍可存在，但 OpenVINS 显式链接隔离的 2.1。
这不是自动升级到未验证的 OpenVINS 分支。

## 传感器边界

M0/M1 默认语义不变；只有 M2 场景带 `uw_specific_force` 和
`uw_capture_time`。前者在仿真传感器内计算
`R_world_to_imu (a_CG + alpha × r + omega × (omega × r) - g)`，随后使用
原噪声链路。IMU 位于原机器人 base_link 原点；r 相对物理 CG。输出去掉
真值姿态（orientation covariance 首项 -1），公开角速度/比力转为 FLU。

后者把绘制队列快照时间随 GPU PBO 缓冲保存到图像回读，禁止用回调当前时间
冒充采样时间。M2 双相机使用连续渲染，处理层仅配对完全相同采样时间的图像，
整对降采样至最高 20 Hz，保留原时间戳。实际频率和丢弃数必须在运行中报告。
这只描述理想同步全局快门仿真，不代表真实硬件同步/曝光/折射标定。

针孔投影遵循像素中心坐标：fx=fy=width/(2 tan(hfov/2))，
cx=(width-1)/2、cy=(height-1)/2。原始 camera_info 的半像素中心约定不直接
复制到 M2。基线 0.145 m、外参从原场景配置派生，并用真实图像检查。

## 发布权与健康

`state/odometry` 和 `odom -> base_link` 动态 TF 只由估计器发布；URDF 只负责
固定传感器 TF。真值位于 `sim/ground_truth/odometry`，使用独立的
`truth/odom` 和 `truth/base_link`，不发布动态 TF。

估计器输出为重力对齐的局部 ENU 约定坐标；全局偏航、平移不可观。
没有 GPS/磁罗盘时不声明地理东/北已对准。评价仅用首个共同姿态的偏航和平移
对齐，禁止用真值拟合尺度或全程轨迹。公开速度在机体 FLU、参考点为 IMU/base_link
共点；四元数从 JPL G→I 转为同数值 Hamilton I→G，协方差转换其表达坐标和次序。

启动 INITIALIZING，无有效估计时不发布占位里程计。缺纹理标为 DEGRADED；
传感器失联、时钟回跳/停滞或无效估计锁存 FAULT，停止状态和 TF 输出。
恢复消息不自动解除锁存，本阶段用新进程恢复，产生新 run 身份。

M2 的真实运动诊断复用 M1 Guard/控制器/原生推进器，控制器输入显式标为
PRIVILEGED_DEBUG 并重映射到独立真值话题。它只负责生成受控测试运动；
**不作为估计状态闭环控制通过的证据**。普通启动不 ARM，测试运行器才在
就绪后显式 ARM。M3 导航与真实硬件不在范围内。
