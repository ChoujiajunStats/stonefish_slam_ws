# stonefish_slam_ws

用 Stonefish 和 BlueROV2 运行水下视觉 SLAM。工作区集成 OpenVINS、RTAB-Map 和在线双目 ORB-SLAM3，启动后可在 Stonefish 看仿真画面，在 RViz 看机器人、轨迹与地图。

Porth 洞穴演示沿规定路线采集，路线与速度控制使用仿真真值反馈 `PRIVILEGED_DEBUG`。ORB-SLAM3 读取实时双目图像，独立输出位姿和稀疏地图。当前重点是验证在线 SLAM；自主探索、避障和 SLAM 位姿反馈控制留待后续接入。

## 环境

Linux x86_64、Docker Engine、Compose v2、NVIDIA Container Toolkit，以及可用的 NVIDIA GPU 和 X11/XWayland 桌面。宿主还需 Git、Python 3.11+、`xauth`；ROS、colcon 和算法库由镜像提供。

已使用 Ubuntu 24.04、RTX 5090 验证。建议预留至少 50 GB 可用空间用于源码构建、镜像和录制；完整 debug bag 的参考量约为 **3.3 GB/分钟**。

## 构建

```bash
git clone https://github.com/ChoujiajunStats/stonefish_slam_ws.git
cd stonefish_slam_ws
./scripts/uw doctor
./scripts/uw build --profile orbslam3
./scripts/uw test --profile orbslam3
```

默认 `orbslam3` profile 包含完整工作区。只运行部分功能时可选：

| Profile | 内容 |
|---|---|
| `core` | 仿真观察、速度与姿态控制 |
| `vio` | 加入 OpenVINS 双目/IMU 估计 |
| `navigation` | 加入局部航点和任务执行 |
| `rtabmap` | 加入 RTAB-Map |
| `survey` | 加入洞穴灯光与规定路线采集 |
| `orbslam3` | 加入在线双目 ORB-SLAM3 |

构建使用 [固定源码与补丁](vendor/)；[profile 配置](docker/profiles.json) 给出镜像名。首次构建会下载并编译依赖。

## 先跑仿真

```bash
./scripts/uw run config/run.empty_water.example.yaml
```

运行 60 秒空水域观察，打开 Stonefish 和 RViz，并保存双目、IMU、状态及 debug bag。这一步不需要 Porth 资产。

## 导入洞穴

Porth 模型、纹理和路线通过独立 bundle 提供。取得 bundle 后执行：

```bash
./scripts/uw assets import --bundle /path/to/porth-bundle.tar.gz
./scripts/uw assets verify
```

已有资产的协作者可导出：

```bash
./scripts/uw assets export --source-data-root /path/to/existing-data --bundle /path/to/porth-bundle.tar.gz
```

导入会按 [资产清单](resources/porth-bundle.lock.json) 校验文件。默认数据目录为 `~/.local/share/stonefish-slam`；如需使用其他磁盘，在运行前设置 `UW_DATA_ROOT`：

```bash
export UW_DATA_ROOT=/path/to/stonefish-slam-data
```

## 在线 SLAM

先执行约 6 m 的短路线，再运行约 571 m 的全程路线：

```bash
./scripts/uw porth config/run.porth-orbslam3-short.yaml --arm
./scripts/uw porth config/run.porth-orbslam3.yaml --arm
```

`--arm` 启用本次规定路线运动；省略时只观察。全程路线包括主通道和三条支路，当前采用保留朝向、倒车返航。

RTAB-Map 路径演示：

```bash
./scripts/uw porth config/run.porth.yaml --arm
```

在另一个终端查询状态或停止推进：

```bash
./scripts/uw status
./scripts/uw disarm
```

在启动终端按 `Ctrl+C` 结束仿真。每次运行生成独立 `run_id`，配置、源码快照、镜像 ID、日志、指标和录制位于 `$UW_DATA_ROOT/runs/`，未设置变量时使用上述默认目录。

## 查看结果

用终端输出中的实际 `run_id` 替换下方占位符：

```bash
./scripts/uw orb-report <run_id>
./scripts/uw slam-export <run_id>
```

`orb-report` 评价 ORB 在线轨迹并重读 Atlas；`slam-export` 导出 RTAB-Map 数据库中的轨迹和点云。输出位于数据目录的 `reports/`。

历史全程 ORB 运行跟踪了 60,949 帧，在线位置 RMSE 为 0.458 m，输出 77,450 个稀疏点。Atlas 可加载，严格数值一致性检查未通过；地图重读与在线跟踪分别评价。

## 结构与协作

| 职责 | 目录 |
|---|---|
| 命令、状态与任务契约 | `interfaces/` |
| 机器人参数、推进器几何 | `robot/` |
| 仿真、传感器、执行适配 | `simulations/`、`perception/` |
| 授权、速度与姿态控制 | `guard/`、`controller/` |
| 状态估计与 SLAM | `localization/` |
| 航点和任务 | `navigation/`、`tasks/` |
| 运行组装、证据、显示 | `app/`、`runtime/`、`ui/` |
| 评价与测试 | `benchmark/`、`test/` |

模块默认参数放在各包 `config/`，跨模块运行配置放在根目录 `config/`。[依赖边界测试](test/test_module_boundaries.py) 检查分层：算法包向接口和基础模块依赖，app 负责组装。

提交前运行 `./scripts/uw test`。涉及仿真行为的修改，在 PR 中附配置、镜像 ID、run_id 和结果。正式验收入口需要当前源码对应的 `test/*-freeze.json`。

远端文档保留本 README；研究笔记与实验报告放在本地 `docs/`。第三方版本和许可见 `vendor/source-lock*.yaml` 及包元数据，自有代码的发行许可尚待指定。
