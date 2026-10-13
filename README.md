# stonefish_slam_ws

用 Stonefish 和 BlueROV2 运行水下视觉 SLAM。工作区集成 OpenVINS、RTAB-Map 和在线双目 ORB-SLAM3，启动后可在 Stonefish 看仿真画面，在 RViz 看机器人、轨迹与地图。

Porth 洞穴演示沿规定路线采集，路线与速度控制使用仿真真值反馈 `PRIVILEGED_DEBUG`。ORB-SLAM3 读取实时双目图像，独立输出位姿和稀疏地图。当前重点是验证在线 SLAM；自主探索、避障和 SLAM 位姿反馈控制留待后续接入。

## 环境

Linux x86_64、Docker Engine、Compose v2、NVIDIA Container Toolkit，以及可用的 NVIDIA GPU 和 X11/XWayland 桌面。宿主还需 Git、Python 3.11+、`xauth`；ROS、colcon 和算法库由镜像提供。

建议预留至少 50 GB 可用空间用于源码构建、镜像和录制；完整 debug bag 的参考量约为 **3.3 GB/分钟**。

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
| `actuators` | 完整 SLAM 工作区，加入可选 disaware 六推进器模型 |

构建使用 [固定源码与补丁](vendor/)；[profile 配置](docker/profiles.json) 给出镜像名。首次构建会下载并编译依赖。

## 六推进器配置

六推进器使用四个水平桨和两个垂直桨，配置键为 `bluerov2_six_disaware`。船体和相机沿用当前模型；控制器主动控制平移、横滚和偏航，俯仰依赖船体被动稳定。几何、推力参数与一阶转速响应见 [六推进器映射](robot/config/thrusters_six_disaware.yaml)。八推进器仍是现有配置的默认选择。

```bash
./scripts/uw build --profile actuators
./scripts/uw test --profile actuators
./scripts/uw run config/run.m1.six.yaml --profile actuators
```

该入口启动后保持 DISARMED。在另一个终端显式启动有限运动：

```bash
./scripts/uw arm --profile actuators
./scripts/uw command --velocity 0.10 0 0 0 --seconds 5 --profile actuators
./scripts/uw disarm --profile actuators
```

命令停止后按失联规则撤权；若故障锁存，下次运动前先 `clear-fault` 再 `arm`。M1/M2/M3 和在线 SLAM 配置均可通过 `robot_profile` 选择六推进器，并用 `--profile actuators` 启动。M0 观察模式仍使用八推进器。

已有 Porth 资产时，可运行六推进器在线双目 SLAM 短程；`--arm` 授权本次规定路线运动：

```bash
./scripts/uw porth config/run.porth-orbslam3-six-short.yaml --profile actuators --arm
```

六通道有限诊断命令：

```bash
./scripts/uw acceptance --profile actuators --robot-profile bluerov2_six_disaware \
  --phase diagnostic --cases probe_0 probe_1 probe_2 probe_3 probe_4 probe_5
```

原生补丁及哈希保存在 [六推进器源码锁](vendor/source-lock.actuators.yaml)。2026-09-29 验收的原始源码冻结记录保存在 `test/frozen/six-thruster-20260929.json`；它记录当时的版本。当前版本的 formal 验收需要重新冻结，不能直接使用这份历史记录。

2026-10-13 同步前复核：容器契约测试 104/104 通过，六个原生推进器通道的正向、反向及归零诊断 6/6 通过。该复核验证六通道接入，不包含自主避障导航。

## 仿真

```bash
./scripts/uw run config/run.empty_water.example.yaml
```

运行 60 秒空水域观察，打开 Stonefish 和 RViz，并保存双目、IMU、状态及 debug bag。这一步不需要 Porth 资产。

## JEPA-MPPI 控制器

JEPA-MPPI 与现有 PI/PID 共用 `uw_controller/body_velocity` 节点、授权和推进器分配链。在 [controller 默认参数](controller/config/defaults.yaml) 中将 `backend: body_pi` 改为 `backend: jepa_mppi` 即可切换，启动命令沿用现有配置；切回 `body_pi` 恢复原控制器。

Checkpoint 随 [controller/checkpoints](controller/checkpoints/) 提交并安装；复用的参考算法源码放在 Git 忽略的 `thirdparty/`：

```bash
mkdir -p thirdparty
touch thirdparty/COLCON_IGNORE
git clone --single-branch --branch experiment/control-sufficient-latent-v8 \
  https://github.com/Xiaoyang-Yu-CS/dev-jepa-water.git thirdparty/dev-jepa-water
git -C thirdparty/dev-jepa-water checkout 40aa6353d12a01084ff65977047987d80e10239c
```

[模型参数](controller/config/jepa_mppi.yaml) 默认使用 CUDA，加载 `stage2_zhat_response_potential_full4096_four_modal_e5.pt` 并校验 SHA-256。运行 ROS 控制节点的 Python 环境需安装支持当前 GPU 的 CUDA PyTorch；RTX 5060 需支持 `sm_120` 的版本，本机测试使用 PyTorch 2.9.1 / CUDA 12.8。原 `body_pi` 不依赖 PyTorch。

水平位置、姿态和速度使用 OpenVINS，控制器深度使用压力计；外层导航与 Guard 沿用原 OpenVINS 状态。支持六/八推进器。模型采样为 10 Hz，输出环为 50 Hz；启动后需收集 26 个真实历史样本。

有 Porth 资产时，切换 backend 后直接使用现有估计反馈洞穴入口：

```bash
./scripts/uw porth config/run.porth.yaml --arm
```

无洞穴资产时可使用 `./scripts/uw m3 config/run.m3.yaml`。M1/M2 诊断和 `run.porth-orbslam3*.yaml` 的真值反馈 survey 不满足此控制器的状态契约，会拒绝启动。当前接入仍属实验性控制器，checkpoint 的训练动力学与仿真模型尚未完成闭环验收。

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

## 结构

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

