# M1 实施范围（2026-09-21，实施前）

## 本轮核查与冻结边界

已读取当前代码及历史 M0 两轮 manifest、metrics、bag metadata、生成场景、
URDF、源锁、DDS XML。历史目录与报告相符；本轮尚未复跑，不能算本轮 PASS。
DDS XML SHA-256 为 `ca6961088346410f2e4770396caecb17ade8848974bfa6b427a31d7d307f53f7`。
仓库无提交，全部工作文件为未跟踪状态；修改前归档和哈希保存在
`.cache/m1/baseline.tar.gz`、`.cache/m1/baseline-hashes.json`，不重置文件。
初始 runs 共 6601063543 字节，本轮新增数据预算 25 GB。
磁盘可用约 789 GiB，GPU 初始占用约 1731 MiB；另一个项目容器保持运行。

## 顺序与文件范围

1. M1-A：核查锁定 Thruster/ROS 缓存/实际质心；在 `robot/` 保存可核验映射。
   `vendor/` 增加最小物理步前 hook 与 wrapper 末端保护补丁；保留原补丁。
   `interfaces/` 增加最小授权消息/服务，`guard/` 实现显式解锁与故障锁存；
   `simulations/` 增加受保护执行适配和诊断场景。先通过逐通道及失联门。
2. M1-B：在 `controller/` 实现经典机体系速度 PI、水平姿态反馈和有界推力分配；
   使用实际质心作为 wrench 参考点，显式标记静态推力近似。有限调参后冻结。
3. M1-C：`benchmark/` 执行真实病例、SIGKILL/时钟 fixture 注入、统计及绘图；
   `test/m1-acceptance.yaml` 预先规定病例与门槛。M0 原配置再运行两轮 60 秒，
   M1 完整图形负载两轮 60 秒；普通病例只录制控制数据。
4. `app/` 仅负责新 schema、组装和运行证据；`scripts/uw` 增加薄 CLI。
   `docker/` 使用独立 `underwater-stack:m1` 标签，保持 DDS/IPC/GPU 布局。
   `ui/` 复用观察配置；`docs/` 更新模块、契约、ADR、运行指南及本轮报告。

原 schema 1、M0 场景生成、观测 probe 的判定语义保持；M1 采用显式 schema 2。
物理步长、传感器参数、质量/浮力/阻尼不变。只有专用执行诊断 fixture 可固定机体。
安全初始门槛固定：上游 0.25 s，末端 0.20 s，中和延迟 0.50 s；使用单调墙钟。
正式控制验收沿用任务给定低速目标、三次冷启动及误差门槛；冻结前调参与正式结果分开。
不上实机、不启用 ArduSub、不修改宿主、不覆盖旧证据/旧镜像、不自动提交。
