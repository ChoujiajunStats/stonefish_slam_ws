# stonefish_slam_ws

基于锁定版本 Stonefish 的 BlueROV2 水下仿真工作区，包含速度/姿态控制、
OpenVINS、RTAB-Map 和在线双目 ORB-SLAM3。ROS 与算法依赖全部放在容器内。

Porth 规定路线的 ORB-SLAM3 输出稀疏地图，路径控制使用明确标记的
`PRIVILEGED_DEBUG` 真值反馈；没有自主洞穴探索、避障或实机接入。
普通启动默认 DISARMED，只有显式授权才执行运动。

## 1. 宿主环境

需要 Linux x86_64、Docker Engine + Compose v2、NVIDIA Container Toolkit、
兼容的 NVIDIA GPU/驱动、X11/XWayland、`xauth`、Python 3.11+ 和 Git。
不需要在宿主安装 ROS、colcon 或算法库，也不要修改全局 Python 环境。

先确认 Docker 可由当前用户访问，且当前会话可以显示图形窗口：

```bash
docker info
docker compose version
nvidia-smi
xauth info
```

完整源码编译需要较多时间、内存和磁盘。M0 的完整 debug 录制约 3.3 GB/分钟；
运行前检查 `df -h`、GPU 和其他项目容器，不要通过结束其他项目进程释放资源。

## 2. 获取与构建

```bash
git clone https://github.com/ChoujiajunStats/stonefish_slam_ws.git
cd stonefish_slam_ws
./scripts/uw doctor
./scripts/uw build --profile orbslam3
./scripts/uw test --profile orbslam3
```

构建从锁定的 ROS 基础镜像获取和编译上游源码，不依赖历史本机镜像。
自有包通过显式路径 colcon 构建；镜像、构建缓存和运行数据按工作区隔离。
镜像变化时自动重建本工作区对应的 overlay，避免复用不兼容二进制。

| Profile | 能力 |
|---|---|
| `core` | M0 观察与 M1 控制 |
| `vio` | 加入 OpenVINS 双目/IMU |
| `navigation` | 加入局部航点与有限任务 |
| `rtabmap` | 加入 RTAB-Map |
| `survey` | 加入随车灯与洞穴规定路线采集 |
| `orbslam3` | 包含上述能力及 ORB-SLAM3 在线双目，默认 profile |

可对各入口使用 `--profile`；当前映射见 [profiles.json](docker/profiles.json)。
APT 版本按实际构建时解析，保存安装清单；不承诺逐位可重现构建。

## 3. 数据与资产

默认数据根为 `$HOME/.local/share/stonefish-slam`，包含 `assets/`、`plans/`、
`runs/` 和 `reports/`。可以在运行命令前设置专用路径：

```bash
export UW_DATA_ROOT=/path/to/stonefish-slam-data
```

不要设为 HOME、根目录或仓库内部。每轮创建唯一 run 目录，保留源码快照、
配置、来源锁、镜像 ID、日志、退出记录、指标和录制；不覆盖历史数据。

Porth 资产不随 Git 分发。从有权提供资产的协作者取得 bundle 后导入：

```bash
./scripts/uw assets import --bundle /path/to/porth-bundle.tar.gz
./scripts/uw assets verify
```

资产持有人可在已有数据的机器上导出：

```bash
./scripts/uw assets export --source-data-root /path/to/existing-data --bundle /path/to/porth-bundle.tar.gz
```

导入按 [资产锁](resources/porth-bundle.lock.json) 校验大小与 SHA，拒绝损坏、
路径穿越、重复成员和覆盖冲突，不导入历史 runs。资产缺失时先运行下面的 M0 观察。

## 4. 启动、运动与停止

先执行 60 秒观察回归，显示 Stonefish 与 RViz、保存 debug bag，无推进器输入：

```bash
./scripts/uw run config/run.empty_water.example.yaml --profile orbslam3
```

资产校验通过后运行 ORB 在线双目。先短程约 6 m，再运行约 571 m 的完整规定路线：

```bash
./scripts/uw porth config/run.porth-orbslam3-short.yaml --profile orbslam3 --arm
./scripts/uw porth config/run.porth-orbslam3.yaml --profile orbslam3 --arm
```

去掉 `--arm` 会保持未解锁。全程采集不代表已完整重建洞穴表面。
测试 RTAB-Map 的预设路径：

```bash
./scripts/uw porth config/run.porth.yaml --profile orbslam3 --arm
```

另开终端查询或中和当前工作区的仿真实例：

```bash
./scripts/uw status
./scripts/uw disarm
```

`Ctrl+C` 触发有界退出，末端 watchdog 独立处理外部进程失联。
只操作本轮 manifest 记录的容器/PID；不要使用全局 `pkill` 或 `docker prune`。

## 5. 结果与验证

使用运行输出中的实际 run_id，生成独立报告并重读地图：

```bash
./scripts/uw orb-report ORB_RUN_ID --profile orbslam3
./scripts/uw slam-export RTABMAP_RUN_ID --profile orbslam3
```

第一条评价在线轨迹并重读原生 Atlas；第二条在数据库副本上导出 RTAB 地图。
原始运行保持不变。ORB 稀疏地图、RTAB 视觉地图与已知洞穴资产是不同的数据产品，
不能把导入资产或评价真值当作 SLAM 输出。

`./scripts/uw test` 在容器中执行契约与数值测试；`--local` 只使用宿主已有依赖，
缺少 NumPy/OpenCV 时部分测试会跳过。单元测试和构建成功不等于仿真验收。
图形、控制、时钟、观测或 SLAM 变更需要真实运行，保留失败证据与原始退出码。
正式评价需要为当前源码、参数和镜像建立 `test/*-freeze.json`；历史结果不能代替。

## 6. 结构与协作

自有 ROS 包位于根目录，按职责组织：

| 职责 | 目录 |
|---|---|
| 配置、组装、进程生命周期 | `app/` |
| 消息契约、机器人几何与映射 | `interfaces/`、`robot/` |
| 场景、光学、执行适配与末端保护 | `simulations/` |
| 控制授权与速度/姿态闭环 | `guard/`、`controller/` |
| 观测整理与估计/SLAM | `perception/`、`localization/` |
| 局部路径与有限任务 | `navigation/`、`tasks/` |
| 显示、评价、测试与运行证据 | `ui/`、`benchmark/`、`test/`、`runtime/` |
| 部署、依赖锁、跨模块运行配置 | `tools/`、`scripts/`、`docker/`、`vendor/`、`config/` |

模块默认参数留在各包 `config/`，跨模块请求在根 `config/`。
[依赖边界测试](test/test_module_boundaries.py) 检查跨包导入、声明和分层；
算法包不能反向依赖 app，评价不能依赖控制器实现，UI 不拥有控制权。

从 main 创建任务分支，通过 PR 协作，不重写共享历史。PR 写明实际验证命令、
镜像、run_id 与限制。上游改动必须是针对锁定提交的补丁，并更新哈希和回归。
公共坐标使用 FLU/ENU，变换数值和协方差，不能仅替换 frame 名称。

远端只发布本 README；其他 Markdown 与 `docs/` 研究 Vault 保留在本地，
不参与 Git 跟踪或 Docker 构建上下文。构建、测试不依赖这些本地文档。

## 来源与许可

仓库所有者：Jiajun Zhou <ChoujiajunStats@126.com>。
项目自有代码尚未统一指定发行许可证，保留 `LicenseRef-Not-Yet-Licensed` 元数据；
已有许可证声明继续有效，没有将所有文件重新授权为 MIT、Apache 或 GPL。
公开可见不代表全部内容已获得无限制复用许可。

第三方项目、固定提交与补丁记录在 `vendor/source-lock*.yaml` 和各包元数据中。
构建获取完整上游源码并保留原许可证。Porth 模型、纹理、路线资产、bag 和 Atlas
不随仓库发布；其权利人决定获取与再分发范围，公开校验值不授予资产使用权。
