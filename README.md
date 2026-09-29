# stonefish_slam_ws（codex）

基于 Stonefish 的 BlueROV2 水下仿真工作区，包含速度/姿态控制、
OpenVINS、RTAB-Map 和online双目 ORB-SLAM3。ROS 与算法依赖全部放在容器内。

**能力：** 没有close loop，controller用的是真值反馈，自主导航还没写，目前在这个repo通了slam的pipeline。

Porth 规定路线的 ORB-SLAM3 输出的是稀疏点云地图，路径控制用标记过的
`PRIVILEGED_DEBUG` 真值反馈（supervised）；并不是自主洞穴探索、避障或实机接入！！！！！！
启动默认 DISARMED，只有解锁才执行运动，就和真机那套差不多，这个地方codex写他纯无聊。。。。。你可以改一下

## 1. 环境

Linux x86_64、Docker Engine + Compose v2、NVIDIA Container Toolkit、
兼容的 NVIDIA GPU/驱动、X11/XWayland、`xauth`、Python 3.11+ 和 Git。

先确认 Docker 权限表和保证会话可以显示图形窗口：

```bash
docker info
docker compose version
nvidia-smi
xauth info
```

写了一个smoke test的，3.3g/s，起码要空间腾50g给他。

## 2. 获取与构建

```bash
git clone https://github.com/ChoujiajunStats/stonefish_slam_ws.git
cd stonefish_slam_ws
./scripts/uw doctor
./scripts/uw build --profile orbslam3
./scripts/uw test --profile orbslam3
```

有ros和colcon的，很方便。

| Profile | 能力 |
|---|---|
| `core` | M0 观察与 M1 控制 |
| `vio` | 加入 OpenVINS 双目/IMU |
| `navigation` | 加入局部航点与任务 |
| `rtabmap` | 加入 RTAB-Map |
| `survey` | 加入随车灯与洞穴规定路线采集 |
| `orbslam3` | 包含上述能力及 ORB-SLAM3 在线双目，默认 profile |


## 3. 数据与资产

默认数据根为 `$HOME/.local/share/stonefish-slam`，包含 `assets/`、`plans/`、
`runs/` 和 `reports/`。可以在运行命令前设置专用路径：

```bash
export UW_DATA_ROOT=/path/to/stonefish-slam-data
```

```bash
./scripts/uw assets import --bundle /path/to/porth-bundle.tar.gz
./scripts/uw assets verify
```

```bash
./scripts/uw assets export --source-data-root /path/to/existing-data --bundle /path/to/porth-bundle.tar.gz
```

...codex一堆废话

## 4. 启动、运动与停止（codex的防御性编程...）

先执行 60 秒观察回归，显示 Stonefish 与 RViz、保存 debug bag，无推进器输入：

```bash
./scripts/uw run config/run.empty_water.example.yaml --profile orbslam3
```

资产校验通过后运行 ORB 在线双目。先短程约 6 m，再运行约 571 m 的完整规定路线：

```bash
./scripts/uw porth config/run.porth-orbslam3-short.yaml --profile orbslam3 --arm
./scripts/uw porth config/run.porth-orbslam3.yaml --profile orbslam3 --arm
```

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

## 5. 结果与验证（看看就好了能用就行，跑通后再整理）

使用运行输出中的实际 run_id，生成独立报告并重读地图：

```bash
./scripts/uw orb-report ORB_RUN_ID --profile orbslam3
./scripts/uw slam-export RTABMAP_RUN_ID --profile orbslam3
```

第一条评价在线轨迹并重读原生 Atlas；第二条在数据库副本上导出 RTAB 地图。
原始运行保持不变。ORB 稀疏地图、RTAB 视觉地图与已知洞穴资产是不同的数据产品，

`./scripts/uw test` 在容器中执行契约与数值测试；`--local` 只使用宿主已有依赖，
缺少 NumPy/OpenCV 时部分测试会跳过。单元测试和构建成功不等于仿真验收。
图形、控制、时钟、观测或 SLAM 变更需要真实运行，保留失败证据与原始退出码。
正式评价需要为当前源码、参数和镜像建立 `test/*-freeze.json`。

## 6. 结构

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

