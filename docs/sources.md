# 来源与版本核查

2026-09-21 按原蓝图的完整提交读取源码。锁定值见 `vendor/source-lock.yaml`。

| 来源 | 固定引用 / 本次核查内容 |
|---|---|
| BlueROV2 | [README](https://github.com/bvibhav/stonefish_bluerov2/blob/6448383af6b7ef6083b0eac2c08102660591e318/README.md)：作者声称 Ubuntu 24.04 / Jazzy 测试；不是本机验证 |
| BlueROV2 launch | [启动文件](https://github.com/bvibhav/stonefish_bluerov2/blob/6448383af6b7ef6083b0eac2c08102660591e318/launch/bluerov2_sim.py)：tank 和 ArduSub 桥 |
| BlueROV2 模型 | [机器人场景](https://github.com/bvibhav/stonefish_bluerov2/blob/6448383af6b7ef6083b0eac2c08102660591e318/scenarios/bluerov2.scn)：8 推进器、传感器、模型引用 |
| Stonefish ROS2 | [manager](https://github.com/patrykcieslak/stonefish_ros2/blob/3fc1fc7e9f959f988cd3e9c71fcf7944163abd0d/src/stonefish_ros2/ROS2SimulationManager.cpp)、[interface](https://github.com/patrykcieslak/stonefish_ros2/blob/3fc1fc7e9f959f988cd3e9c71fcf7944163abd0d/src/stonefish_ros2/ROS2Interface.cpp)：时钟、打戳、CameraInfo |
| Stonefish IMU | [IMU.cpp](https://github.com/patrykcieslak/stonefish/blob/6d285a955d19c9ecef3defd3f0605907f4594dbb/Library/src/sensors/scalar/IMU.cpp)：运动学加速度 |
| Stonefish odometry | [Odometry.cpp](https://github.com/patrykcieslak/stonefish/blob/6d285a955d19c9ecef3defd3f0605907f4594dbb/Library/src/sensors/scalar/Odometry.cpp)：世界 pose、局部 twist |
| ROS 坐标 | [REP-103](https://www.ros.org/reps/rep-0103.html)、[REP-105](https://www.ros.org/reps/rep-0105.html) |
| 基础镜像 | Docker 官方 `library/ros:jazzy-ros-base` registry manifest；解析 digest 固定于锁文件 |
| Fast DDS SHM | [传输说明](https://fast-dds.docs.eprosima.com/en/v2.14.7/fastdds/transport/shared_memory/shared_memory.html)、[XML 配置](https://fast-dds.docs.eprosima.com/en/v2.14.7/fastdds/xml_configuration/transports.html)：大消息需要足够大的共享内存段；可使用纯 SHM 发现/传输 |
| Jazzy RMW 发现设置 | [participant.cpp](https://github.com/ros2/rmw_fastrtps/blob/jazzy/rmw_fastrtps_shared_cpp/src/participant.cpp)：LOCALHOST 自动追加默认 SHM，SYSTEM_DEFAULT 保留用户传输配置 |

Stonefish 及 ROS wrapper 的上游许可为 GPL-3.0 系列；本项目对两者的
补丁遵循原文件许可。BlueROV2 package.xml 声明 Apache-2.0，具体网格/纹理的
独立来源与许可仍待核查，不将包级声明当成所有资产的完整许可证证明。

本项目原创代码尚未指定发行许可证；包里的 `LicenseRef-Not-Yet-Licensed`
是保留的许可状态。当前维护人元数据已按用户授权填写；发行许可仍由所有者决定，见 [NOTICE](../NOTICE.md)。
构建将完整上游仓库保留在镜像中，原有 LICENSE/COPYING 文件随源码保留。

APT 软件包版本会随首次构建解析并被记录，尚未使用发行版快照仓库锁定。
因此当前锁是固定源码/基础镜像与可追溯构建，不是逐位可重现证明。

M1 additionally pins RViz 14.1.23 (the already installed version) at
`feb01669f1297df2af755ce9cd2ed18083e7a8b2`. The patched
[ImageTransportDisplay source](https://github.com/ros2/rviz/blob/feb01669f1297df2af755ce9cd2ed18083e7a8b2/rviz_default_plugins/include/rviz_default_plugins/displays/image/image_transport_display.hpp)
is BSD-3-Clause; original headers and full source remain in the image.
The lifecycle failure and regression are documented in
[the M1 diagnosis](m1-rviz-lifecycle-fix.md). This is a same-version fix, not an upstream upgrade.


## M2 新增依赖与补丁（2026-09-23）

M1 来源锁保持原样。新增 [M2 来源锁](../vendor/source-lock.m2.yaml) 记录父锁哈希、
父镜像 ID、OpenVINS v2.7（GPL-3.0-or-later）和隔离的 Ceres 2.1.0（BSD-3-Clause）
固定提交。OpenVINS 算法源码未修改；参数文件由该提交的 Euroc stereo 配置改编。
自有 C++ 链接适配器标记 GPL-3.0-or-later；上游许可证保留在镜像的源代码目录。

- [0007 传感器语义](../vendor/patches/0007-m2-sensor-semantics.patch)：显式选择的
  IMU 比力、随绘制/PBO 缓冲传递的真实采样时间。默认路径保留 M0/M1 语义。
- [0008 ROS 采样戳](../vendor/patches/0008-m2-acquisition-stamps.patch)：仅显式启用
  时使用采样戳和无姿态 IMU；连续相机负频率的队列深度改为有限 5，防止无符号
  溢出。M0/M1 的正频率队列计算保持不变。
- [M2 补丁应用脚本](../scripts/prepare_m2_upstream.py)：核验父来源锁、每份补丁
  SHA-256、固定提交，再执行 `git apply --check`；镜像记录实际应用证据。

补丁不改质量、浮力、阻尼、推进器或原生末端 watchdog。设计理由与公式见
[ADR-0003](adr-0003-sensor-time-and-estimator-authority.md)，实际运行边界见 M2 验收报告。

## 可选 ORB-SLAM3

- [官方 ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3)：提交
  `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`，上游 GPLv3，保留原 LICENSE。
  原生双目跟踪、局部 BA、回环、Atlas；未使用来历不明的 ROS wrapper。
- [Pangolin](https://github.com/stevenlovegrove/Pangolin)：v0.8 提交
  `aff6883c83f3fd7e8268a9715e84266c42e2efe3`，上游 MIT。
- ORB 自带 DBoW2/g2o/Sophus 随同该固定提交构建；具体第三方许可保留在
  上游源码，不能用 ORB 顶层许可代替所有子库的许可声明。
- 源锁、补丁原因与 SHA 见 `vendor/source-lock.orbslam3.yaml`；独立镜像和
  本机证据见 [ORB 本轮报告](validation-2026-09-24-orbslam3.md)。
