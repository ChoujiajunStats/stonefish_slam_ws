> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# M0 运行指南

## 环境检查

在仓库根目录执行 `./scripts/uw doctor`。脚本只检查 Docker、Compose、GPU、
显示和 X11 授权，不安装软件，不改变组、驱动或系统配置。
`./scripts/uw compose-config` 不需要 daemon，仅检查 Compose 配置。

2026-09-21 已恢复当前用户 Docker 访问，并完成镜像和两轮仿真验收。
正常使用直接进入下方“构建与验证”。以后若 `doctor` 报 Docker socket 权限不足，
且 Docker 服务、NVIDIA 容器工具已经安装，可在本机终端执行：

```bash
cd /home/hong/Desktop/StoneFish_Nav
./scripts/setup-docker-access
```

脚本会通过 `sudo` 要求你在终端输入管理员密码，请勿将密码发送到聊天中。
它将当前用户加入现有 docker 组，并通过 `setfacl` 给该用户添加当前 socket
的读写权限，因此本次无需退出 IDE，现有进程也可立即连接 Docker。
最终以当前普通用户执行 `docker info` 验证访问。

Docker 组配置参考 [官方步骤](https://docs.docker.com/engine/install/linux-postinstall/)，
该权限可通过 Docker 管理宿主。组成员身份在下次完整注销并登录后生效；
当前 socket ACL 是即时措施，Docker 重启后可能需要重新执行脚本，直到重新登录。
无需为此安装宿主 ROS、CMake、colcon 或 Python 算法依赖。

## 构建与验证

```bash
./scripts/uw build
./scripts/uw test
./scripts/uw run config/run.empty_water.example.yaml
```

`build` 构建固定基础镜像 digest、Stonefish 和上游 ROS underlay，然后在
命名卷中构建五个项目包。构建可能下载较大的 ROS/PCL 依赖。
`UW_BUILD_JOBS` 默认为 8。源码只读挂载，镜像不挂载 home 或 Docker socket。
依赖源码保存在镜像内部 `/opt/uw_src`，仓库 `vendor/` 只存锁和补丁。

`run` 先增量构建 overlay，再创建只属于本次运行的容器和输出目录。
脚本持有构建锁，目前明确仅支持一个 M0 worker；后续再实现并行分配器。
关闭 RViz 不影响主链路；关闭 Stonefish 窗口会终止该次运行。
Ctrl+C 会请求关闭该容器，超时才升级终止信号，不停止其他用户的容器。

脚本复制当前 `DISPLAY` 的 X11 cookie 至临时授权文件，按当前 UID 运行容器，
退出后删除授权文件，不使用 `xhost +`。NVIDIA Container Toolkit 和
本机 RTX 5090 已验证 OpenGL 4.6；迁移机器后仍需重新检查。如果
`nvidia-smi` 成功但容器不能访问 GPU，
应先处理宿主已有 Docker GPU runtime，而不是改算法代码。

M0 的全部 ROS 节点运行在一个容器中。`docker/fastdds.xml` 为每个 DDS
participant 配置 32 MiB 共享内存，只使用本容器的私有 IPC 进行发现和传输；
容器 `/dev/shm` 总容量为 512 MiB。`SYSTEM_DEFAULT` 让 ROS 使用该 XML，
避免 `LOCALHOST` 额外添加默认大小的 SHM transport。不要单独改回
`LOCALHOST`：本机首次运行曾出现图像严重丢失，显式增大 SHM 后两轮验收通过。
这个配置适用于当前单容器 M0；多容器/远程 ROS 接入需要单独设计传输配置。

默认 RViz 左侧显示配置，中间显示示意机器人和 TF，右侧上下显示左右 RGB。
空水域无海底和地标，相机呈蓝绿色水体是预期画面。

## 输出与判读

每轮位于 `$UW_DATA_ROOT/runs/<标签>--<UTC时间>--<随机后缀>/`。
默认 `$UW_DATA_ROOT` 为 `$HOME/.local/share/underwater-stack`。
包括 `manifest.json`、请求与解析配置、源码归档和文件哈希、Git SHA/dirty diff
（仓库有提交时）、镜像 ID、基础镜像 digest、上游补丁、apt/Python 清单、
生成场景与资产哈希、URDF、DDS 配置及哈希、显式录制话题、rosbag、日志和 `metrics.json`。
当前 debug 配置录制未压缩双目 RGB，一轮约 3.3 GB；不需 bag 时将
配置中的 `recording_profile` 改为 `none`。

`SUCCEEDED` 仅表示本次 M0 探测窗口完成。`NOT_STARTED`、`FAILED`、
`TIMED_OUT`、`CANCELLED` 分开记录。缺少 metrics 或必要进程提前退出不能成功。
`ready.json` 表示本轮曾达到就绪条件；最终结果仍以 manifest/metrics 为准。
日志位于 `logs/launch.log` 与 `logs/ros/`。

单次自动探测不能代替目视检查与重启检查。本机已补充这两项证据，见
[运行验收记录](runtime-validation-2026-09-21.md)。双目曝光同步、物理标定、
IMU 实机等价性和控制/估计仍不在 M0 验收范围。

## 无容器的开发检查

本机已有 Python 3.12 + PyYAML 时可执行：

```bash
./scripts/uw validate --local
./scripts/uw test --local
```

这些检查覆盖配置拒绝策略、几何变换、场景和资产校验、输出唯一性、包边界与锁完整性，
不会导入 ROS，也不构成 ROS 编译证据。宿主没有 PyYAML 时改用容器验证，
不用在宿主安装项目依赖。


M3 使用独立显式配置、估计反馈和任务 Action；启动/取消/回退步骤见
[M3 运行指南](runbook-m3.md)。原 M0/M1/M2 入口保留。
