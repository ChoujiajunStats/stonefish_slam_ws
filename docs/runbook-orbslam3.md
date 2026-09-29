> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# ORB-SLAM3 在线洞穴采集

本入口使用实时双目图像运行官方 ORB-SLAM3 的 **STEREO** 模式。
尚未接入 ORB 双目惯性模式。IMU/OpenVINS 保留为独立比较，
不输入 ORB。ORB 前端显式使用灰度＋CLAHE(3.0, 8×8)；仿真水体、灯光、
原始传感器话题和 RViz 图像不改变。控制和规定路线仍使用 `PRIVILEGED_DEBUG`。

```bash
UW_IMAGE=underwater-stack:orbslam3-porth-v2 \
UW_DOCKERFILE=docker/Dockerfile.orbslam3 ./scripts/uw build
UW_IMAGE=underwater-stack:orbslam3-porth-v2 ./scripts/uw test
./scripts/uw porth config/run.porth-orbslam3-short.yaml --arm
./scripts/uw porth config/run.porth-orbslam3.yaml --arm
```

以上构建、测试、短程及全程入口均已实测，在线采集通过；Atlas 严格数值
重读存在已记录的微小差异，结果见
[本轮报告](validation-2026-09-24-orbslam3.md)。首次执行应先跑短程，
再跑全程。不带 `--arm` 时默认 DISARMED，不自动运动。需要人工停止时：
`./scripts/uw disarm`。`./scripts/uw status` 可查询当前 Guard 状态与
实际控制状态源（本轮已实测）。不要向原生推进器直接发布数组。

配置保留 0.22 水体、两盏随车灯、1.8 资产实验尺度和约 571 m 保留朝向路线。
RViz/Stonefish 会自动显示。RViz 蓝色为 ORB 稀疏地标，红色为在线优化关键帧；
BlueROV2 RobotModel 直接使用 ORB 的 `map -> orb_body` 显示位姿。
OpenVINS 仍独立记录，但其 odom 树不与 ORB map 树人为连接，避免不同初始
朝向和漂移造成机器人/地图错位。显示用单 link URDF 只引用原有真实网格，
不增加物理机器人或推进器入口。

ORB 的相机位姿和地标在接收器内按真实相机安装外参转换到初始机体 FLU
坐标系。纯双目不测量重力或绝对方位，不能将该坐标约定声称为测得的 ENU。
对真值的初始 yaw/平移配准仅发生在独立评价中，不反馈算法或控制。

每次输出新 run：`orb-frames.jsonl` 是原始在线位姿/延迟/跟踪状态；
`orb-keyframes-body.jsonl`、`orb-optimized-camera-tum.txt` 和 `orb-sparse-map.ply`
是关闭后台处理后保存的结果；`orb-atlas.osa` 是原生 Atlas。
`orb-camera-samples/` 保留约 1 Hz 双目 JPEG 诊断样本，不冒充全部 20 Hz 输入。
MCAP 记录在线状态、轨迹和有上限的显示点云。完整地图不混入已知洞穴模型。

这是稀疏 SLAM 地图，不是稠密纹理网格。在线轨迹与最终优化轨迹分别评价。
地图重建多个独立 Atlas 子图会中止这版规定路线采集；跟踪丢失期间闭环零速度，
超过 5 秒退出并锁存故障。恢复图像不会自动 ARM。

旧入口 `./scripts/uw porth config/run.porth-survey.yaml --arm` 仍使用
OpenVINS + RTAB-Map；M0 观察配置及所有历史标签保持原义。

[接入计划](orbslam3-plan.md) · [主页](00-home.md)
