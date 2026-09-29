# M0 本机运行验收：2026-09-21

结论：M0 观察模式已通过本机验收。Docker 权限恢复后完成实际构建、
容器内测试、NVIDIA 渲染，以及两轮各 60 秒连续观测。控制器和估计器未实现。
早期权限阻塞保留在 [首次验证记录](validation-2026-09-21.md)。

## 环境与构建

- 宿主 Ubuntu 24.04，RTX 5090，NVIDIA 驱动 580.178.04。
- 容器 `glxinfo -B`：direct rendering Yes，NVIDIA RTX 5090，OpenGL 4.6。
- 项目镜像 `underwater-stack:m0`：
  `sha256:2a925f1bd1ff5d6eb1067e6f50f7160e232c98c6f66a6e6c3622a060de737ab6`。
- 编译 Stonefish 库、两个上游 ROS 包和五个项目包均成功。
- `./scripts/uw test`：41 项契约测试通过。
- ROS/C++/Python 依赖安装在镜像中；未安装宿主 ROS，也未修改宿主驱动和 shell 配置。

## 实际遇到的问题与修复

1. Stonefish 固定版本在当前 GCC 下缺少 `uint64_t` 声明。
   添加 `0002-stonefish-fixed-width-integers.patch` 显式包含 `<cstdint>`，
   补丁 SHA-256 写入源锁；随后完整 C++/ROS 构建成功。
2. 首次真实仿真在就绪后失败：小消息持续到达，左相机图像却落后时钟超过 1 秒。
   失败轮次 `bluerov_empty_water--20260921T144440Z--eede37495953` 保留了
   FAILED manifest、指标和 bag。没有放宽验收门限。
3. 按 [Fast DDS SHM 说明](https://fast-dds.docs.eprosima.com/en/v2.14.7/fastdds/transport/shared_memory/shared_memory.html)
   检查大消息传输配置，新增显式 32 MiB/participant SHM、4 MiB 最大消息、
   1024 槽队列；使用单容器私有 IPC，关闭内建传输，ROS discovery 设为
   SYSTEM_DEFAULT。之后两轮均通过，日志未再报告 rosbag 消息丢失。
   这是本机运行证据，不构成对所有负载下零丢包的保证。
4. 调整 RViz 停靠布局和字体 DPI，使左右图像预览同时可见；正常退出时
   observation adapter 不再打印 KeyboardInterrupt 堆栈。

## 两轮验收结果

所有目录均位于 `$HOME/.local/share/underwater-stack/runs/`。
配置为 `config/run.empty_water.example.yaml`，包含 RViz 和 debug bag。

| 项目 | 第一次成功运行 | 重启后的第二次成功运行 |
|---|---|---|
| 目录 | `bluerov_empty_water--20260921T145013Z--bf7e98fbfcbf` | `bluerov_empty_water--20260921T145316Z--fd25784eb909` |
| manifest / probe | SUCCEEDED / PASS | SUCCEEDED / PASS |
| 连续就绪观测 | 60 秒 | 60 秒 |
| 含启动/退出的墙钟耗时 | 65.19 秒 | 64.99 秒 |
| Probe 首个 /clock | 0.01 秒 | 0.01 秒 |
| Probe 结束时钟 | 61.04 秒 | 60.82 秒 |
| 左图像接收数 | 1748 | 1725 |
| 右图像接收数 | 1813 | 1806 |
| IMU / 里程计接收数 | 1220 / 6104 | 1216 / 6082 |
| Bag 总消息数 | 33130 | 32976 |
| Bag 大小 | 约 3.30 GB | 约 3.27 GB |

Probe 验证六个观测话题、正确 frame、有效数据、时间单调、实时新鲜度、
唯一推进中的 `/clock` 和 odom 到机器人/IMU/左右相机的 TF 连通性。
每轮指标中的 `unverified` 指自动 Probe 本身不覆盖的检查，以下人工及
集成检查独立补充，不回写或篡改原始 Probe 结果。

第二轮额外保存 `graph-inspection.json`：只有 1 个 `/clock` 发布者，
无名称包含 thruster、pwm、actuator 或 ardusub 的话题。场景生成测试同时
确认移除了全部上游推进器 ROS 订阅入口。

两轮必要进程退出码均为 0，bag metadata 正常落盘。运行后没有残留的
`uw-run-*` 容器或网络；未停止其他项目容器。新轮次首个时钟回到 0.01 秒，
bag 首个机器人位置均约为 ENU `(0, 0, -2)`，未沿用上一轮最终状态。
这证明当前进程重启路径；未承诺热重置或数值逐位确定性。

## 可视证据与数据

每轮 `figures/stonefish.png`、`figures/rviz.png` 是实际项目窗口截图。
已目视确认水面、BlueROV2 模型、RViz Global Status OK、机器人示意体、TF
以及左右 RGB 预览。`figures/left-rgb.png`、`figures/right-rgb.png` 由该轮
MCAP 的真实 Image 消息无损导出，640×480 RGB8；空水域呈蓝绿色渐变，
没有虚构海底或地标。导出样本、首末时钟和初始位置见 `bag-inspection.json`。

每轮同时保留 manifest、metrics、源码归档/哈希、依赖清单、资产锁、生成场景、
URDF、DDS XML/哈希和进程退出记录。目录内 `inspection-tools/` 保留本次
人工验证使用的导出/截图/ROS graph 检查脚本。
本地构建日志为仓库 `.cache/m0-build.log`，测试日志为
`.cache/m0-container-tests-final.log`；`.cache` 不纳入版本管理。

## 验收边界

M0 使用仿真真值 `PRIVILEGED_DEBUG`，没有控制指令入口。
左右相机采样数和时刻存在差异；本轮不宣称硬件式同步、双目标定精度、
IMU 实机等价性、闭环控制或状态估计通过。RViz 机器人是几何示意体，
真实水动力模型由 Stonefish 提供。后续工作按 [路线图](roadmap.md) 进入 M1。

固定版本附带的 Bullet 编译有警告，APT 仍按构建时仓库解析版本；当前
证据支持可追溯构建，不代表消除了全部上游问题或实现逐位可重现构建。
