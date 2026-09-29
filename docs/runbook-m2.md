> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# M2 运行指南

本阶段运行真实双目/IMU OpenVINS 估计；只适用于仿真研究。
估计状态尚未接入推进器闭环。诊断运动继续由标记为 PRIVILEGED_DEBUG 的
M1 控制器产生，不是导航或估计状态控制验收。

## 构建与检查

在仓库根目录执行，依赖全部留在容器：

```bash
UW_IMAGE=underwater-stack:m2 UW_DOCKERFILE=docker/Dockerfile.m2 ./scripts/uw build
./scripts/uw test --local
UW_IMAGE=underwater-stack:m2 ./scripts/uw test
```

本机已有已验收镜像时可直接进入启动步骤。重新导出镜像的构建证明可能改变
镜像 ID，即使所有层命中缓存；这时正式冻结检查会拒绝旧 ID，应保留旧标签并
为新构建重新冻结/评价。

M2 基于已经锁定的 `underwater-stack:m1-v4`；不会覆盖 M0/M1 标签。
构建时核验父镜像、来源锁、补丁和 OpenVINS/Ceres 固定提交。
新建宿主机还需要先恢复或按记录构建该父镜像，不能用任意同名镜像替代。

## 默认观察与显式运动

```bash
./scripts/uw m2 config/run.m2.yaml
```

默认 60 秒、自由机器人、视觉诊断场景、RViz、精简 state bag，保持 DISARMED。
OpenVINS 需要静止初始化及随后可观测的运动，可能先显示 INITIALIZING。
未解锁的自由机器人仍受浮力影响，不保证静止，也不保证总能初始化。

在另一个终端：

```bash
./scripts/uw m2-status
./scripts/uw status
./scripts/uw arm --velocity 0 0 0 0 --seconds 8
./scripts/uw arm --velocity 0.12 0 0 0 --seconds 5
./scripts/uw disarm
```

命令入口只发送经过 Guard 的机体速度请求；程序会明确提示运动使用真值调试
反馈。ARM 是显式操作；上述有限请求结束时会自动发送显式 DISARM。若命令源中断，原有 Guard/末端保护撤权并锁存，后续
命令不会自动重新 ARM。零速度目标与 DISARM 不同：前者可以产生推力。

`m2-status` 同时检查状态文件的新鲜度和当前 manifest；已经退出或过期时显示
STALE_OR_STOPPED，不把历史 TRACKING 当作当前有效状态。

## 诊断与正式验收

```bash
./scripts/uw m2-acceptance --phase diagnostic --cases sensors
./scripts/uw m2-acceptance --phase tuning --cases trajectory_1
./scripts/uw m2-acceptance --phase formal --cases sensors estimation degeneration faults load
```

正式入口逐病例检查 `test/m2-freeze.json` 的镜像 ID 和运行文件哈希。
修改实现或参数后须建立新的冻结版本并重跑受影响的评价。
三个 trajectory 病例是独立冷启动重复，使用同一确定纹理场景，不称随机种子泛化。

测试程序就绪后显式 ARM；只有诊断配置允许固定体、传感器丢弃或隔离时钟故障。
SIGKILL 只针对本轮 manifest 中记录且 start_ticks 匹配的估计器 PID。
输入恢复后 FAULT 保持锁存；重新启动命令创建新 run、新时钟和新滤波状态。

## 数据与恢复

数据沿用 `$UW_DATA_ROOT`，默认 `$HOME/.local/share/underwater-stack`。
每轮包含源代码归档、dirty 状态、镜像 ID、双来源锁、DDS 哈希、传感器外参、
参数、场景/纹理哈希、原始 JSONL、bag、图表、进程退出码和独立测试判定。
`sensors/debug` 录制包含图像，`state` 只录小消息；M2 新增 runs 预算 25 GB。
历史运行不会被覆盖或删除。

先在运行终端按 Ctrl+C，等待本轮容器和网络退出，然后回退：

```bash
UW_IMAGE=underwater-stack:m2 ./scripts/uw run config/run.empty_water.example.yaml
```

启动脚本的退出清理只作用于本轮实例。M0 配置继续为 observation-only，无推进器
ROS 控制输入。估计器锁存故障后，用新进程恢复；本阶段不承诺热重置。

空水域没有足够纹理时 DEGRADED 是预期行为。未实现深度图、主动灯光策略、
建图/回环、全局航向、位置保持、导航、SITL 或真实硬件。
