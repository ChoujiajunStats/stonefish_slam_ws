# M3 审计与实施计划（2026-09-23）

用户明确授权进入 M3。本轮先核对实际源码与本机证据，再实现、构建和运行。

## 已核查的基线

M2-v3 冻结的 151 个运行文件全部吻合；13 个历史正式目录的 manifest 和
metrics 均为 PASS，镜像与记录一致。这是历史证据复核，不是本轮重跑。
M0、M1-v4、M2-v3 镜像 ID 保留。当前没有 Git HEAD，文件均未跟踪，不能依靠
commit 表示版本；修改前已保存完整源码和哈希：
`$HOME/.local/share/underwater-stack/reports/m3-baseline-20260923T074903Z/`。
数据基线 45,988,793,977 bytes，M3 新增预算 25 GB。未操作其他项目运行中的容器。

实际有 10 个项目包；navigation/tasks 尚不存在。M2 的 Guard 与 Controller
仍读诊断真值；OpenVINS 静止初始化与完成首次视觉更新是两个状态。
M3 必须明确处理这两个边界，不得用真值替代估计。

## 实施范围与顺序

1. 建立显式 schema 4、独立 M3 镜像与 overlay，沿用私有 IPC、DDS 文件、锁定
   上游与原始机器人动力学。M0/M1/M2 配置保持原行为。
2. M3 显式允许传感器静止初始化状态 `READY_STATIC`，与视觉 `TRACKING` 区分。
   Guard/Controller 仅订阅估计里程计；Guard 独立检查估计健康、新鲜度与局部包络。
   真值只给 Benchmark 作误差/安全评价，不给任务、导航或控制作反馈。
3. 根目录新增实际 `navigation/`、`tasks/` 包。实现已知空闲小范围内的直线航点
   跟踪（位置与相对偏航），通过现有四维速度契约驱动；不实现避障、地图或全局航向。
   `ExecuteMission` action 提供显式执行授权、反馈、取消、超时和明确终态。
   任务心跳/绝对期限向下传递，进程死亡后不可刷新旧意图。
4. Benchmark 实施冷启动重复、局部机体/世界系、取消/超时/互斥、估计和任务链故障、
   最后一跳 SIGKILL、图形负载及旧阶段回归。先有限调试，再冻结运行代码与病例门槛。
   保留失败结果；冻结后的变更建立新版本并重跑受影响评价。
5. 更新唯一 docs Vault 的接口、模块、ADR、运行指南及实际验收报告，交付真实命令、
   原始数据、图表与逐病例结论。不自动 commit/push，不进入 M4。

## 预计修改文件范围

新增 navigation/tasks 包、interfaces/action/ExecuteMission.action 与最小导航授权消息；
扩展 localization 的显式静止启动选项、guard 的估计健康门；app 组装/配置/证据，
benchmark 病例/指标，scripts 薄入口与显式包列表，docker/Dockerfile.m3、vendor M3
父镜像锁、config/run.m3.yaml、test/m3-* 及有意义的契约测试。历史报告、原始蓝图、
旧镜像/运行目录不修改；如需上游补丁，必须另记来源、原因和哈希。
