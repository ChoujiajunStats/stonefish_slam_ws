# 新工作区部署验证：2026-09-29

结论：源码部署、容器契约、M0 观察与 ORB-SLAM3 在线短程回归通过。
这是仓库整合验证；没有重新执行 M1/M2/M3 全清单或 571 m 全洞路线。
原验收报告的 PASS/FAIL 与限制保持原结论。

## 源码与结构

新工作区 `stonefish_slam_ws`，原工作区 `StoneFish_Nav` 保留。
核对原始 319 个源码文件，0 个被修改。蓝图、DDS、vendor 来源锁/全部补丁、
机器人参数等保护范围 23 文件与原工程逐字节一致。没有新增上游补丁。

- `runtime/`：第 13 个实际 ROS 包，证据生命周期/源码快照/地图只读检查。
- `app/` 与 `benchmark/`：使用共用 runtime，解除反向 Python 依赖；保留兼容导入。
- `tools/uw_workspace/`：按环境、构建、配置、资产拆分宿主部署；`scripts/uw` 是薄入口。
- `docker/Dockerfile` 与 `profiles.json`：core→vio→navigation→rtabmap→survey→orbslam3
  多阶段源构建，不再依赖历史本机镜像 ID。独立镜像/overlay，不覆盖旧标签。
- `scripts/container-command`：显式 13 包路径，记录镜像 ID，镜像变更时重建专用缓存。
- `resources/porth-bundle.lock.json`：17 个外部资产/路线文件的大小与 SHA；拒绝损坏、
  越界、链接、重复文件和覆盖冲突。真实 384,318,323 字节资产导出/导入复核 PASS。
- `benchmark/uw_benchmark/orb_report.py`：复用原评估与 Atlas 检查，新增 `uw orb-report`。
  修复新数据根首次生成 ORB 报告时尚无 reports 目录的问题，没有改变评价公式。
- README、部署/结构/协作指南、工作区文件、CI、PR/Issue 模板、忽略规则。
  旧 Docker 配方和 freeze 归档于 `docs/history/`，不作为新代码验收凭证。

实际仿真源码提交 `ffc24c4af469d15377000cfc30a08c2d6ca7bc18`，dirty=false。
此后只增加报告入口/首次 reports 目录创建、验证文档与证据；控制/仿真/SLAM
实现及参数与上述运行版本一致。所有提交在新仓库历史中保留。

## 构建与契约

宿主 Ubuntu 24.04、RTX 5090、驱动 580.178.04；Docker 29.8.1、Compose v5.5.1。
未安装宿主 ROS 或算法库，未改驱动、全局 Python、shell 或 Docker 权限。
Git/SSH 登录仅为用户授权的新仓库发布配置；凭据不进入 Git。

完整 `stonefish-slam:orbslam3` 本地 image ID：
`sha256:8161bfea609ec51516cc32d95c4876a743378ba6e685a76bee4e4ee903039522`。
镜像约 12.61 GB，未推送到镜像 registry。完整父阶段实际编译，13 个自有 ROS 包
构建完成；后续增量构建也成功。Bullet/Eigen/上游编译警告保留，没有改成 latest。

| 实际检查 | 结果 |
|---|---|
| `docker build --target orbslam3 -t stonefish-slam:orbslam3 --build-arg UW_BUILD_JOBS=8 -f docker/Dockerfile .` | PASS |
| `./scripts/uw build --profile orbslam3` | PASS，13 包，首次 overlay 18.1 s |
| `./scripts/uw test --local` | 80 PASS，8 SKIP（宿主无 NumPy/OpenCV） |
| `docker build -f docker/Dockerfile.test -t stonefish-slam-contracts .` 后按 CI 命令运行 | 88 PASS，0 SKIP |
| `./scripts/uw test --profile orbslam3` | 88 PASS，0 SKIP |
| 换目录克隆后本地测试 | 80 PASS，8 SKIP |
| `python3 -S scripts/uw compose-config` 与 `assets verify` | PASS，无宿主第三方 Python 依赖 |
| 原 83 项契约语义 + 5 项部署/依赖边界测试 | 保留并通过；未删减旧断言 |

各 profile 的父层均已构建；本次只在最终 orbslam3 profile 实跑，并非逐个 profile
重新完成阶段验收。旧正式 campaign 因未建立新 freeze 明确拒绝启动。

## 实际仿真

共同数据根：`$HOME/.local/share/stonefish-slam/runs/`。
原始日志、manifest、metrics、源码快照/dirty 状态、锁/参数、DDS、bag 和退出记录在各 run。

| 项目 | M0 | ORB 在线短程 |
|---|---|---|
| run_id | `bluerov_empty_water--20260929T014711Z--5de309c453ab` | `porth_orbslam3_short_v2--20260929T014925Z--e5315934bba8` |
| 命令 | `./scripts/uw run config/run.empty_water.example.yaml --profile orbslam3` | `./scripts/uw porth config/run.porth-orbslam3-short.yaml --profile orbslam3 --arm` |
| 过程状态 / 判定 | SUCCEEDED / PASS | COMPLETED / PASS |
| 范围 | 60 秒连续观察 | 6 m 请求，实际沿线 6.0761 m |
| 墙钟（含启动/退出） | 66.66 s | 57.17 s |
| 必要进程退出码 | 6/6 为 0 | 12/12 为 0 |
| UI / 录制 | RViz + Stonefish / debug | RViz + Stonefish / state |

M0：首时钟 0.01 s，末时钟 61.07 s；左/右图像
1744 / 1813，
IMU 1221、里程计 6107。
原新鲜度/TF 断言通过；现场图检查 `/clock` 发布者=1、推进器相关 topic=0。
bag 正常收尾，目录约 3.31 GB。原 probe 的 unverified 原样保留。

ORB：本轮原生最终反馈 745/745 帧跟踪成功，lost=0、dropped=0、1 个 Atlas，
65 关键帧、3227 稀疏地图点、0 个接受的 loop edge。处理约 19.64 Hz，在线验收
p99 延迟 0.05 s。全程表面覆盖没有验证。

原始在线位姿独立评价：RMSE 0.030889 m，
最大误差 0.063171 m，末端 0.053611 m。
只做初始 yaw+translation 对齐，不拟合尺度或全轨迹。
在线 SLAM 输入仍只有双目；控制是 `PRIVILEGED_DEBUG`，不是 ORB 驱动控制。
结束时 Guard=DISARMED，原生执行设定值中和；没有本项目残留运行容器/网络。

两次均记录显示双窗口。M0 保存真实窗口截图；ORB 短程结束较快，手动窗口截图
未及时抓取，保留实际 RGB、轨迹、SLAM 数据图和 gui-show.json；没有补造 GUI 截图。

## 地图复用与可视证据

实际执行：

```bash
./scripts/uw orb-report porth_orbslam3_short_v2--20260929T014925Z--e5315934bba8
```

输出位于 `$HOME/.local/share/stonefish-slam/reports/orb-evaluation-porth_orbslam3_short_v2--20260929T014925Z--e5315934bba8/`。
Atlas 原生重读成功，65/65 关键帧，严格比较 PASS；最大 pose 分量差
5.000e-08，原 Atlas 哈希不变。
该短程结果不能覆盖历史全程 Atlas 严格一致性 FAIL。

- [M0 RViz](assets/workspace-2026-09-29/m0-rviz.png) / [Stonefish](assets/workspace-2026-09-29/m0-stonefish.png)
- [ORB 实际左图](assets/workspace-2026-09-29/orb-left-rgb.png)
- [在线/优化轨迹、误差、延迟与跟踪状态](assets/workspace-2026-09-29/orb-online-tracking.png)
- [原生稀疏地图](assets/workspace-2026-09-29/orb-sparse-map.png)
- [机器可读检查与哈希](assets/workspace-2026-09-29/integration-checks.json)
- [M0 指标](assets/workspace-2026-09-29/m0-metrics.json) / [ORB 在线指标](assets/workspace-2026-09-29/orb-slam-metrics.json)
- [独立位姿评价](assets/workspace-2026-09-29/orb-evaluation.json) / [Atlas 重读](assets/workspace-2026-09-29/atlas-reload.json)

本机构建/测试日志：仓库 `.cache/integration/`，不进入 Git。
历史 runs 未移动/覆盖/删除；本轮 runs 合计约 3.34 GB。

## 交付边界

公开仓库：<https://github.com/ChoujiajunStats/stonefish_slam_ws>。
远端 CI 状态以 Actions 为准；本机已实际执行 CI 同等容器命令。

Porth 大资产通过外部锁定 bundle 分发，不在 Git。原创代码许可仍待所有者决定，
见 [NOTICE](../NOTICE.md)。APT 传递依赖未全部快照锁定，不承诺逐位复现。
没有重调控制器、改物理参数或新增自主避障/探索；没有新实机验证。
M0/M1/M2/M3 历史验收与本次部署短程的范围严格区分。
