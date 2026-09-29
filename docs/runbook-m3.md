> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# M3 运行指南

依赖留在容器中。首次构建：

```bash
UW_IMAGE=underwater-stack:m3 UW_DOCKERFILE=docker/Dockerfile.m3 ./scripts/uw build
UW_IMAGE=underwater-stack:m3 ./scripts/uw test
./scripts/uw test --local
```

启动有限时长的仿真（默认 120 秒，DISARMED，不自动运动）：

```bash
./scripts/uw m3
```

另一个终端查看就绪、任务和估计状态：

```bash
./scripts/uw status
./scripts/uw m3-status
```

Guard 就绪后执行相对接单时位置/朝向的两点任务。x/y/z 单位 m，yaw 单位 rad；
这里先向前 0.4 m，再回起点。`--arm` 是本任务显式解锁授权，结束后自动 DISARM：

```bash
./scripts/uw mission --arm --waypoint 0.4 0 0 0 --waypoint 0 0 0 0 --timeout 30
```

取消任务并确认 Action 终态：

```bash
./scripts/uw mission-cancel
```

也可以在任务客户端 Ctrl+C 请求取消，或立即撤权：

```bash
./scripts/uw disarm
```

收到 FAULT 时先读 run 内 `mission-events.jsonl`、`m3-events.jsonl`、
`localization-health.json` 和原生日志；估计器故障后停止当前仿真并重新启动。
普通 Ctrl+C 只停止当前 `uw m3` 进程组/容器。没有自动恢复 ARM，也没有 `uw down` 命令。
客户端进程直接死亡不会自动取消已接收的任务；任务绝对期限仍然有效。

验收入口按固定清单依次启动独立进程：

```bash
./scripts/uw m3-acceptance --phase formal --cases contracts missions lifecycle faults ui load
./scripts/uw m3-acceptance --phase formal --cases regression
```

formal 会逐个检查源码与镜像是否匹配 `test/m3-freeze.json`。有意修改后应先用
`--phase diagnostic` 或 `--phase tuning`，建立新冻结版本再正式评价。

回退旧观察模式：

```bash
UW_IMAGE=underwater-stack:m0 ./scripts/uw run config/run.empty_water.example.yaml
```

运行目录在 `$HOME/.local/share/underwater-stack/runs/`（可通过 `UW_DATA_ROOT`
显式覆盖）。不删除旧证据。当前只在带纹理的空闲诊断场景评估局部航点跟踪，
没有避障、全局地图或实机能力。


M3 的 `status` 查询使用 Guard 的原子状态快照，不新建 DDS 参与者。运动/取消
CLI 在创建节点前检查私有 /dev/shm 余量，最多等待 3 秒；资源不足时明确失败，
且尚未发送控制命令。该检查保留 32 MiB/participant 和 512 MiB 容器布局。
