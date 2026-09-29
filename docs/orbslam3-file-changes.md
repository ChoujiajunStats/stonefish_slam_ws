# ORB-SLAM3 本轮文件范围

本轮工作前的文件 SHA 保存在外部接入报告 `source-before.json`；仓库没有
提交基线，因此用文件哈希区分本轮修改，未 reset、commit 或 push。
原始架构蓝图、历史 M0–M3 报告和配置均未回填或覆盖。

| 文件 | 用途 |
|---|---|
| `localization/src/orbslam3_node.cpp` | 原生双目 SLAM 接收、预处理、在线位姿/地图/状态、保存 |
| `localization/src/orbslam3_atlas_check.cpp` | 原生 Atlas 只读加载与关键帧导出验证 |
| `localization/config/orbslam3_stereo.yaml` | 可追溯特征、预处理与接收队列参数 |
| `localization/CMakeLists.txt`、`package.xml` | 独立镜像条件构建，保留旧 OpenVINS |
| `app/uw_app/orbslam3.py` | 实际相机外参/标定生成、输出检查 |
| `app/uw_app/m3_config.py` | 显式 ORB profile 范围约束 |
| `app/launch/estimate.launch.py` | 组装 ORB、录制、独立坐标 RobotModel/RViz |
| `app/uw_app/m2_runner.py` | ORB 预算、实际二进制/锁/源码证据、进程退出与输出判定 |
| `benchmark/uw_benchmark/survey_case.py` | 实时 ORB 健康/时效、输入隔离、同地图与采集判定 |
| `benchmark/uw_benchmark/orb_evaluate.py` | 原始在线轨迹、最终优化关键帧的独立真值评价与图表 |
| `benchmark/uw_benchmark/orb_reload.py` | 外部只读 Atlas 重读与原始关键帧核对 |
| `config/run.porth-orbslam3*.yaml` | 新的短程/全洞显式入口 |
| `scripts/uw` | 选择独立 ORB 镜像/overlay 的薄入口 |
| `docker/Dockerfile.orbslam3` | 固定父镜像上构建全部 ORB/Pangolin 依赖 |
| `test/test_orbslam3.py` | 新增 3 项配置隔离、标定/杆臂与来源补丁契约 |
| `test/orbslam3-acceptance.yaml`、`orbslam3-freeze.json` | 判据及全程前冻结 SHA |
| `docs/orbslam3-plan.md`、`runbook-orbslam3.md`、`validation-2026-09-24-orbslam3.md` | 实施计划、可运行命令、全部成功与失败记录 |
| `docs/00-home.md`、`roadmap.md`、`interfaces.md`、`module-localization.md`、`sources.md`、根 `README.md` | 实際新增能力入口与边界 |

上游改动单列（均针对固定提交，不追踪 latest）：

- `vendor/source-lock.orbslam3.yaml`：提交、父镜像、补丁 SHA。
- `vendor/patches/0010-orbslam3-build-export-shutdown.patch`：编译、GBA 代际计数、
  只读地图快照、等待后台工作完成及空 Atlas 关闭。
- `vendor/patches/0011-pangolin-fixed-width-integers.patch`：GCC 13 标准整数头。

DDS、Stonefish 物理/光学、robot/ 推进器 profile、controller/、guard/ 算法未改。
辅助取景只操作本轮已识别的 Stonefish 观察相机，不改变机器人或传感器。
`.cache/orbslam3/` 保存构建/测试与诊断工具；大型输出位于既有外部 runs/reports。
任务开始时本地旧回放链接缺失，已从保留归档复制回 `.cache/replay-online/`，
没有重建或改写历史视频内容。

[本轮报告](validation-2026-09-24-orbslam3.md) · [运行指南](runbook-orbslam3.md)
