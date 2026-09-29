# Porth 全洞采集：本轮文件范围

以本轮开始时的源码快照为差异基准；仓库原先没有 Git HEAD，已有文件均为
未跟踪状态，不能用 `git status` 的 NEW 直接判断本轮新增。快照位于
`$HOME/.local/share/underwater-stack/reports/porth-survey-baseline-20260923T200450Z/`。
逐文件哈希清单保存在本轮交付报告目录；用户的 Obsidian 工作区状态不列为
本轮实现。原始设计文档与历史运行目录不改写。

| 文件范围 | 用途 |
|---|---|
| `navigation/uw_navigation/survey.py` | 明确真值反馈的低速规定路线跟随，保持朝向往返、端点切换、三维限速 |
| `simulations/uw_simulations/survey_plan.py`、`survey_branches.py`、`survey_revision.py`、`surface.py` | 已知网格的离线路线筛查、开放网格朝向启发式、历史推导记录 |
| `simulations/uw_simulations/optics.py` | 原生 Jerlov 水体与两盏无推力随车灯 |
| `app/uw_app/survey.py`、`m2_config.py`、`m3_config.py`、`m2_runner.py`、`m3_status.py`、`porth.py`，`app/launch/estimate.launch.py` | 显式采集配置、镜像/路线校验、独立数据预算、运行组装、SLAM 状态展示 |
| `app/uw_app/runner.py` | 新 survey 镜像的 M0 回归计入本任务已有预算；不重置预算或改变 M0 观察配置 |
| `guard/uw_guard/node.py` | 仅显式 Porth 采集配置允许 PRIVILEGED_DEBUG 控制；时效、授权与末端保护语义保持 |
| `localization/src/openvins_node.cpp` | 可选健康检查图像归一化，与 OpenVINS 实际跟踪器的 CLAHE 设置一致；保留原始特征计数，默认关闭 |
| `app/uw_app/window.py`，`app/launch/{inspect,control,estimate}.launch.py` | 根据本次新窗口和进程显示 RViz、Stonefish，不操作其他项目窗口 |
| `benchmark/uw_benchmark/survey_case.py`、`survey_safety_fixture.py`，`benchmark/setup.py` | 实际推进器采集、运行监控、精确 PID 的末级 Adapter SIGKILL 诊断 |
| `benchmark/uw_benchmark/slam_export.py`、`survey_coverage.py`、`survey_quality.py`、`cloud_viewer.py` | 关闭数据库后重读、导出真实点云、全表面/完整中心线评价及交互查看；不作为在线算法输入 |
| `scripts/uw`、`config/run.porth-survey.yaml` | 薄入口、显式 ARM、光学配置、导出与覆盖评价 |
| `test/test_survey.py`、`test/porth-survey-*` | 契约检查、冻结配置、阶段失败与新版本分离 |
| `docs/` 中 Porth 采集、光学、运行索引和本轮验证文档，以及首页/接口/路线图 | 实际命令、范围、证据和局限 |

## 上游补丁单列

`vendor/patches/0009-survey-optical-lights.patch` 允许末端接收器跳过无推力的
LIGHT 执行器，继续要求原八个推进器，其他意外类型仍拒绝。它不修改推进器、
水动力参数、授权或超时。SHA-256：
`ddfdcd4a7ca3de592096d9dd9d5572cf2a0b21a53b46d6a29c092ff9bdeabbdf`。

`vendor/source-lock.survey.yaml`、`docker/Dockerfile.survey` 与
`vendor/README.md` 记录锁定父镜像、补丁来源和单独镜像构建。
历史 M0/M1/M2/M3/Porth 镜像标签与其他源码锁保留。

[本轮验证](validation-2026-09-24-porth-survey.md) · [运行索引](porth-survey-run-index.md)
