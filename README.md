# stonefish_slam_ws

Containerized BlueROV2 simulation, safeguarded body-velocity control, OpenVINS,
RTAB-Map and online stereo ORB-SLAM3, using locked Stonefish sources.
面向水下 SLAM 研究的工作区，分别管理源码、实验配置、外部资产和运行证据。

**能力边界：** Porth 规定路线的 ORB-SLAM3 是在线双目稀疏建图；路径控制使用
`PRIVILEGED_DEBUG` 真值反馈。没有自主洞穴探索/避障，不是稠密全洞重建，不连接实机。
普通启动保持 DISARMED，只有显式 `--arm` 才执行规定路径。

## 快速开始

宿主：Linux x86_64、Docker Engine + Compose v2、NVIDIA Container Toolkit、
兼容的 NVIDIA GPU/驱动、X11/XWayland、`xauth`、Python 3.11+、Git。
ROS、colcon 和算法依赖在镜像内。完整源码编译需要较多时间、内存和磁盘；
本机验证环境与结果见 [部署验证](docs/validation-2026-09-29-workspace.md)。

```bash
git clone https://github.com/ChoujiajunStats/stonefish_slam_ws.git
cd stonefish_slam_ws
./scripts/uw doctor
./scripts/uw build --profile orbslam3
./scripts/uw test --profile orbslam3
./scripts/uw run config/run.empty_water.example.yaml --profile orbslam3
```

最后一条启动 60 秒 M0 观察，显示 Stonefish 与 RViz、录制 debug bag，不启用推进器输入。
默认数据根为 `$HOME/.local/share/stonefish-slam`；可用 `UW_DATA_ROOT` 指定专用目录。

Porth 资产不随 Git 分发。从有权提供资产的协作者取得锁定的 bundle 后：

```bash
./scripts/uw assets import --bundle /path/to/porth-bundle.tar.gz
./scripts/uw assets verify
./scripts/uw porth config/run.porth-orbslam3-short.yaml --profile orbslam3 --arm
```

短程约 6 m；全程配置与资产导出方式见 [部署指南](docs/deployment.md)。
每次产生新 run 目录，保存源码快照、配置、锁、镜像 ID、日志、指标、地图与录制。

## 结构与协作

根目录 ROS 包并列，显式 colcon 构建，不递归扫描 vendor、docs 或实验输出。

| 职责 | 目录 |
|---|---|
| 组装和运行生命周期 | `app/` |
| 消息契约、机器人几何/映射 | `interfaces/`, `robot/` |
| Stonefish 场景、执行适配、末端保护 | `simulations/` |
| 唯一控制权、速度控制与分配 | `guard/`, `controller/` |
| 观测转换、OpenVINS/ORB 接入 | `perception/`, `localization/` |
| 局部航点与有限任务 | `navigation/`, `tasks/` |
| RViz、评价和故障注入 | `ui/`, `benchmark/`, `test/` |
| 共用证据与地图存储检查 | `runtime/` |
| 部署、容器、来源锁、运行配置 | `tools/`, `scripts/`, `docker/`, `vendor/`, `config/` |
| 唯一 Obsidian Vault | `docs/` |

[部署与故障处理](docs/deployment.md) · [依赖边界](docs/repository-structure.md) ·
[参与协作](CONTRIBUTING.md) · [Obsidian 入口](docs/00-home.md) · [历史结果](docs/roadmap.md)

本仓库从原研究工作区独立整理。历史验收报告保留原结论，不代表新构建重新完成了
所有阶段验收；历史 freeze 与旧 Docker 配方位于 `docs/history/`。
许可证状态与第三方来源见 [NOTICE](NOTICE.md)。
