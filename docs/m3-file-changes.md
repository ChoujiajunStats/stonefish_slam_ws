# M3 实际文件范围

相对于修改前归档，共 76 个文件新增或修改；不把自动生成配置、构建缓存
或 Obsidian 工作区布局变化算作实现文件。大型运行数据在仓库外。

M2 历史报告仅存在保留的工作区表格排版变化，不属于 M3 功能修改。

上游补丁：**本轮没有新增或改写**。M3 仅新增父镜像/来源锁；0001–0008 保留原哈希。

主要用途：

- `navigation/`：估计坐标下的局部航点跟踪，输出既有四维速度请求。
- `tasks/`：有界任务 Action、显式授权、反馈、取消、超时与终态。
- `interfaces/`：任务/航点消息和独立的请求绝对有效期。
- `guard/`、`localization/`：估计健康门及 M3 显式静止初始化发布。
- `app/`、`config/`：schema 4 组装、参数、运行证据与状态查询。
- `benchmark/`、`test/`：真实故障与导航评价、冻结病例、契约测试。
- `scripts/`、`docker/`、`vendor/`：薄 CLI、容器编译入口、M3 父镜像锁。
- `docs/`：接口、模块、ADR、运行指南、实际验收与真实图表。

| 文件 | 类型 |
|---|---|
| `README.md` | 修改 |
| `app/launch/estimate.launch.py` | 修改 |
| `app/launch/navigate.launch.py` | 新增 |
| `app/package.xml` | 修改 |
| `app/setup.py` | 修改 |
| `app/uw_app/m2_config.py` | 修改 |
| `app/uw_app/m2_runner.py` | 修改 |
| `app/uw_app/m3_config.py` | 新增 |
| `app/uw_app/m3_runner.py` | 新增 |
| `app/uw_app/m3_status.py` | 新增 |
| `app/uw_app/run_config.py` | 修改 |
| `app/uw_app/runner.py` | 修改 |
| `benchmark/package.xml` | 修改 |
| `benchmark/setup.py` | 修改 |
| `benchmark/uw_benchmark/m2_case.py` | 修改 |
| `benchmark/uw_benchmark/m3_campaign.py` | 新增 |
| `benchmark/uw_benchmark/m3_case.py` | 新增 |
| `benchmark/uw_benchmark/m3_metrics.py` | 新增 |
| `config/run.m3.yaml` | 新增 |
| `docker/Dockerfile.m3` | 新增 |
| `docs/00-home.md` | 修改 |
| `docs/adr-0004-estimated-navigation-and-missions.md` | 新增 |
| `docs/architecture.md` | 修改 |
| `docs/assets/m3-v4/fault-timeline.png` | 新增 |
| `docs/assets/m3-v4/four-axis-velocity.png` | 新增 |
| `docs/assets/m3-v4/provenance.json` | 新增 |
| `docs/assets/m3-v4/rviz.png` | 新增 |
| `docs/assets/m3-v4/stonefish.png` | 新增 |
| `docs/assets/m3-v4/velocity-attitude.png` | 新增 |
| `docs/assets/m3-v4/waypoints-trajectory.png` | 新增 |
| `docs/interfaces.md` | 修改 |
| `docs/m3-file-changes.md` | 新增 |
| `docs/m3-implementation-plan.md` | 新增 |
| `docs/m3-run-index.md` | 新增 |
| `docs/module-controller.md` | 修改 |
| `docs/module-guard.md` | 修改 |
| `docs/module-localization.md` | 修改 |
| `docs/module-navigation.md` | 新增 |
| `docs/module-tasks.md` | 新增 |
| `docs/roadmap.md` | 修改 |
| `docs/runbook-m3.md` | 新增 |
| `docs/runbook.md` | 修改 |
| `docs/validation-2026-09-23-m2.md` | 修改 |
| `docs/validation-2026-09-23-m3.md` | 新增 |
| `guard/uw_guard/contracts.py` | 修改 |
| `guard/uw_guard/node.py` | 修改 |
| `interfaces/CMakeLists.txt` | 修改 |
| `interfaces/action/ExecuteMission.action` | 新增 |
| `interfaces/msg/ControlRequest.msg` | 修改 |
| `interfaces/msg/NavigationGoal.msg` | 新增 |
| `interfaces/package.xml` | 修改 |
| `localization/src/openvins_node.cpp` | 修改 |
| `navigation/config/defaults.yaml` | 新增 |
| `navigation/package.xml` | 新增 |
| `navigation/resource/uw_navigation` | 新增 |
| `navigation/setup.cfg` | 新增 |
| `navigation/setup.py` | 新增 |
| `navigation/uw_navigation/__init__.py` | 新增 |
| `navigation/uw_navigation/core.py` | 新增 |
| `navigation/uw_navigation/node.py` | 新增 |
| `scripts/container-cli` | 新增 |
| `scripts/container-command` | 修改 |
| `scripts/uw` | 修改 |
| `tasks/config/defaults.yaml` | 新增 |
| `tasks/package.xml` | 新增 |
| `tasks/resource/uw_tasks` | 新增 |
| `tasks/setup.cfg` | 新增 |
| `tasks/setup.py` | 新增 |
| `tasks/uw_tasks/__init__.py` | 新增 |
| `tasks/uw_tasks/cli.py` | 新增 |
| `tasks/uw_tasks/node.py` | 新增 |
| `test/m3-acceptance.yaml` | 新增 |
| `test/m3-freeze.json` | 新增 |
| `test/test_m3.py` | 新增 |
| `test/test_repository.py` | 修改 |
| `vendor/source-lock.m3.yaml` | 新增 |
