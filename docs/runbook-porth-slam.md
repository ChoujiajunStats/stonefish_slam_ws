> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# Porth 双目 SLAM 演示

本入口使用现有 Stonefish/BlueROV2、OpenVINS 双目/IMU 前端和 RTAB-Map
建图后端。预设短路径仅用于采集数据；没有自主探索或避障。
实际结果与失败记录见 [本机验证报告](validation-2026-09-24-porth-slam.md)。

## 启动

在仓库根目录执行；所有 ROS/算法依赖仍在容器内。

```bash
# 已构建；需要重建时使用独立标签
UW_IMAGE=underwater-stack:m3-porth-v1 UW_DOCKERFILE=docker/Dockerfile.porth ./scripts/uw build

# 只启动和观察，保持 DISARMED，最长 140 秒
./scripts/uw porth

# 显式授权：启动新实例，等待就绪，沿预设路径运动并建图
./scripts/uw porth --arm
```

运动路径为任务初始机体系下的五个目标 `(x,y,z,yaw)`：
`(0.8,0,0,0) → (1.6,0.12,0,0.06) → (2.4,0.25,0,0.10)
→ (1.2,0.12,0,0.04) → (0,0,0,0)`，单位 m/rad。
速度上限沿用 0.12 m/s。通过既有 Tasks → Navigation → Guard → Controller →
原生推进器执行，使用 OpenVINS 反馈。完成后 DISARM，再观察 5 秒退出；
任务绝对超时 130 秒，整体观察上限 140 秒。没有直接设置刚体运动状态。

另一终端可执行：

```bash
./scripts/uw m3-status
./scripts/uw mission-cancel
./scripts/uw disarm
```

正常未解锁运行中的自由机器人会受浮力影响移动；这不表示自动 ARM。
出现 FAULT 后用新进程重启。Ctrl+C 结束本项目实例；末端失联保护保持原实现。

## RViz 中查看什么

- `BlueROV2 Heavy - actual asset`：锁定上游模型的真实外观，尺寸不变。
- `SLAM map - stereo measurements`：双目测量重建的彩色点云。
- `SLAM optimized trajectory`：RTAB-Map 位姿图；另有 OpenVINS 轨迹和任务航点。
- 左右 RGB：Stonefish 实际渲染的 Porth 岩壁图像。
- `Known Porth cutaway - NOT SLAM output`：默认关闭，勾选显示导入网格的局部
  去顶视图。它仅是已知环境参考，不能当作 SLAM 地图。完整物理场景没有去顶。

Grid/地图为局部估计坐标。地图坐标的绝对北向、绝对平移不可观测；地图后端
发布 map→odom，OpenVINS 独占 odom→base_link。导航仍使用局部 odom，
不依赖回环后的地图规划。

## 数据和重新读取

每次新目录：`$UW_DATA_ROOT/runs/<run_id>/`；默认数据根为
`$HOME/.local/share/underwater-stack`。目录包含 `rtabmap.db`、`slam-map.ply`、
`slam-graph.json`、`slam-metrics.json`、原控制/估计指标、MCAP、真实图像与图表。
默认录制 state；RTAB-Map 数据库另存关键帧双目数据，不保存全部图像流。
完整图像录制可复制 `config/run.porth.yaml`，将 `recording_profile` 设为 `debug`，
再执行 `./scripts/uw porth <仓库内配置路径> --arm`。

```bash
./scripts/uw slam-export <完整run_id>
```

此命令在新的 `reports/slam-export-*/` 目录复制数据库，使用真正的
`rtabmap-info` 与 `rtabmap-export` 重新加载、导出优化位姿和彩色 PLY；原运行
不修改。`reload-metrics.json` 记录返回码、文件哈希和独立真值轨迹评价。
这验证保存与重读，不等于新会话传感器重定位。

## 资产与边界

导入位置：`$UW_DATA_ROOT/assets/porth_sump9_v1/`。本机源目录是
`/mnt/data8t/Cave Adventurer/cave_turning_stonefish/assets/`，原始来源信息和哈希
保存在 `asset.json` 及 `source-metadata.yaml`。尺度 1.5 是实验选择，未证明原
洞穴模型的测量比例已标定。出生位置 ENU `(0,0,-8)`、yaw=90°；机器人质量、
浮力、阻尼、推进器映射与控制增益不变。洞穴采用固定诊断照明，非实机灯光标定。

若在新数据根导入资产，可在项目镜像内运行 `python3 -m
uw_simulations.porth_assets --source <只读挂载的源assets> --output
/data/assets/porth_sump9_v1`。导入器拒绝覆盖已存在目录。

单容器私有 IPC、原 Fast DDS XML 未修改；保持原末端单调时钟 watchdog。
洞穴模式显式采用估计位置水平 4 m/垂直 1 m 包络；旧 M3 仍为 1.5 m/0.6 m。
独立真值评价包络为 ENU z∈(-12,-4)、|x/y|<4 m、roll/pitch<25°。
新数据预算独立记录在 `porth-budget.json`（25 GB）；不删除旧证据。

回退原观察入口：`UW_IMAGE=underwater-stack:m3-porth-v1 ./scripts/uw run
config/run.empty_water.example.yaml`；原 `underwater-stack:m0` 与 M3-v4 标签未覆盖。
