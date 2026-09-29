> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# M1 本机运行

在仓库根目录执行。需要已有 Docker/NVIDIA/X11 环境；依赖只安装在镜像中。
`./scripts/uw build` 从已验收且 ID 匹配的 `underwater-stack:m0` 派生 M1，
重放固定补丁并编译，不覆盖 M0 标签。完整源码配方仍在 `docker/Dockerfile`。

```bash
./scripts/uw doctor
./scripts/uw build
./scripts/uw test
python3 test/rviz_lifecycle/run.py underwater-stack:m1-v4
./scripts/uw m1
```

最后一条启动普通 M1 会话，默认 DISARMED，RViz 观察左右图像、TF、轨迹和控制状态。
在另一个终端执行：

```bash
./scripts/uw status
./scripts/uw arm --velocity 0.10 0 0 0 --seconds 3
./scripts/uw disarm
```

`arm` 显式解锁、作为 cli 源发送有限时长请求，结束后显式 DISARM；不附速度参数时
发送零速度闭环目标。最多 30 秒。`command --velocity ... --seconds ...` 仅在当前已由
cli 解锁时有效，适合已有持续源期间的调用；单独 ARM 后等待手工下一条命令会因
0.25 秒原请求期限失效，因此一般使用上面的有限 ARM 命令。退出或失联会触发末端保护。
`status` 返回状态/原因/源/代际；出现 FAULT 后先排除报告的健康问题，再：

```bash
./scripts/uw clear-fault
./scripts/uw arm --velocity 0 0 0 0 --seconds 2
```

清除故障本身不解锁。Ctrl+C 停止本会话；重启生成新 run，旧授权无效。
程序只操作 active-session 记录并核对仓库挂载的本项目容器，不连接真实设备。

单推进器诊断必须显式选择诊断配置或病例组：

```bash
./scripts/uw run config/run.actuator_probe.yaml
./scripts/uw acceptance --phase diagnostic --cases mapping
```

这里是固定机体、小幅 ±0.12、有限时长的原生反馈检查，仍通过 Guard 与末端。
普通 body_velocity 配置拒绝电机数组，不能用诊断 fixture 证明动态控制性能。

正式评价检查冻结文件的代码哈希和镜像 ID；任一变化都拒绝沿用旧冻结版本：

```bash
./scripts/uw acceptance --phase formal --cases load_1 load_2 m0 m0 mapping authority velocity yaw90_body_vx tilted_level combined zero30 saturation_recovery fault
```

全部病例串行执行，完整图形负载只用于 load_1/2 和 M0，两轮 M0 每轮 60 秒。
其余 control profile 仍发布图像，只录控制/状态/反馈，减少数据。
报告在 `$HOME/.local/share/underwater-stack/reports/`，run 在同级 `runs/`；
支持已有 `UW_DATA_ROOT`。新增数据预算 25 GB；不要删除历史证据来绕过预算。

回退 M0（schema 1，无可驱动推进器入口）：

```bash
./scripts/uw run config/run.empty_water.example.yaml
```

末端失效保护不是物理停车保证；零速度闭环不是位置保持。状态为 PRIVILEGED_DEBUG，
不宣称估计器、导航、ArduSub 或实机验证。完整结论见 [验收报告](validation-2026-09-22-m1.md)。

M1 debug 使用 MCAP zstd_fast 无损压缩并记录 recording-storage.json，完整话题仍在；
M0 保留原录制方式。正常退出先结束数据进程，再关闭本轮 RViz；关闭前布局另存，
所有非零退出仍会使正常病例失败。
