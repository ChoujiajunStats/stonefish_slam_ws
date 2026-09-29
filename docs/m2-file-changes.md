# M2 文件修改范围

与本轮修改前源码归档比较；仓库没有 Git HEAD，不能把空的 git diff 当作没有修改。
逐文件前后哈希保存在数据根目录 `reports/m2-files-changed.json`。
用户/Obsidian 自动维护的 `.obsidian/workspace.json` 不计入本次实现改动，也没有回滚。
原始架构蓝图、M0 配置/场景/适配器、机器人模型、M1 增益/分配参数及来源锁保持原样。

| 范围 | 用途 |
|---|---|
| perception | 真实采样戳的双目严格配对、输入契约及 FLU 比力 IMU |
| localization | 固定 OpenVINS 库的 ROS2 接入、协方差/TF、健康及故障锁存 |
| simulations | 独立 M2 光学 fixture、采样语义选择、仅供评价的真值发布 |
| app/config | schema 3、M2 组装/运行记录、状态读取；原配置路由保留 |
| guard/controller | 可配置的状态 frame；控制 CLI 加入本轮 DDS 域 |
| benchmark/test | 真实病例、冻结清单、指标/图表、故障注入与契约测试 |
| docker/scripts | 独立 M2 镜像、固定补丁应用、显式包路径与薄 CLI |
| vendor | M2 父锁与 OpenVINS/Ceres 固定提交；0007/0008 补丁 |
| docs/README | 实施、接口、边界、运行指南、验收与证据索引 |

## 逐文件清单

| 类型 | 文件 |
|---|---|
| 修改 | [README.md](../README.md) |
| 新增 | [app/launch/estimate.launch.py](../app/launch/estimate.launch.py) |
| 修改 | [app/package.xml](../app/package.xml) |
| 修改 | [app/setup.py](../app/setup.py) |
| 新增 | [app/uw_app/m2_config.py](../app/uw_app/m2_config.py) |
| 新增 | [app/uw_app/m2_runner.py](../app/uw_app/m2_runner.py) |
| 新增 | [app/uw_app/m2_status.py](../app/uw_app/m2_status.py) |
| 新增 | [app/uw_app/run_config.py](../app/uw_app/run_config.py) |
| 修改 | [app/uw_app/runner.py](../app/uw_app/runner.py) |
| 修改 | [benchmark/package.xml](../benchmark/package.xml) |
| 修改 | [benchmark/setup.py](../benchmark/setup.py) |
| 新增 | [benchmark/uw_benchmark/m2_campaign.py](../benchmark/uw_benchmark/m2_campaign.py) |
| 新增 | [benchmark/uw_benchmark/m2_case.py](../benchmark/uw_benchmark/m2_case.py) |
| 新增 | [benchmark/uw_benchmark/m2_metrics.py](../benchmark/uw_benchmark/m2_metrics.py) |
| 新增 | [config/run.m2.yaml](../config/run.m2.yaml) |
| 修改 | [controller/uw_controller/node.py](../controller/uw_controller/node.py) |
| 新增 | [docker/Dockerfile.m2](history/build-recipes/Dockerfile.m2) |
| 修改 | [docs/00-home.md](../docs/00-home.md) |
| 新增 | [docs/adr-0003-sensor-time-and-estimator-authority.md](../docs/adr-0003-sensor-time-and-estimator-authority.md) |
| 修改 | [docs/architecture.md](../docs/architecture.md) |
| 新增 | [docs/assets/m2-v3/fault-timeline.png](../docs/assets/m2-v3/fault-timeline.png) |
| 新增 | [docs/assets/m2-v3/provenance.json](../docs/assets/m2-v3/provenance.json) |
| 新增 | [docs/assets/m2-v3/rviz.png](../docs/assets/m2-v3/rviz.png) |
| 新增 | [docs/assets/m2-v3/stonefish.png](../docs/assets/m2-v3/stonefish.png) |
| 新增 | [docs/assets/m2-v3/trajectory.png](../docs/assets/m2-v3/trajectory.png) |
| 新增 | [docs/assets/m2-v3/velocity-attitude-unwrapped.png](../docs/assets/m2-v3/velocity-attitude-unwrapped.png) |
| 修改 | [docs/interfaces.md](../docs/interfaces.md) |
| 新增 | [docs/m2-file-changes.md](../docs/m2-file-changes.md) |
| 新增 | [docs/m2-implementation-plan.md](../docs/m2-implementation-plan.md) |
| 新增 | [docs/m2-run-index.md](../docs/m2-run-index.md) |
| 新增 | [docs/module-localization.md](../docs/module-localization.md) |
| 新增 | [docs/module-perception.md](../docs/module-perception.md) |
| 修改 | [docs/roadmap.md](../docs/roadmap.md) |
| 新增 | [docs/runbook-m1-m2-boundary.md](../docs/runbook-m1-m2-boundary.md) |
| 新增 | [docs/runbook-m2.md](../docs/runbook-m2.md) |
| 修改 | [docs/sources.md](../docs/sources.md) |
| 新增 | [docs/validation-2026-09-23-m2.md](../docs/validation-2026-09-23-m2.md) |
| 修改 | [guard/uw_guard/cli.py](../guard/uw_guard/cli.py) |
| 修改 | [guard/uw_guard/node.py](../guard/uw_guard/node.py) |
| 新增 | [localization/CMakeLists.txt](../localization/CMakeLists.txt) |
| 新增 | [localization/config/imu.yaml](../localization/config/imu.yaml) |
| 新增 | [localization/config/openvins.yaml](../localization/config/openvins.yaml) |
| 新增 | [localization/package.xml](../localization/package.xml) |
| 新增 | [localization/src/openvins_node.cpp](../localization/src/openvins_node.cpp) |
| 新增 | [perception/package.xml](../perception/package.xml) |
| 新增 | [perception/resource/uw_perception](../perception/resource/uw_perception) |
| 新增 | [perception/setup.cfg](../perception/setup.cfg) |
| 新增 | [perception/setup.py](../perception/setup.py) |
| 新增 | [perception/uw_perception/__init__.py](../perception/uw_perception/__init__.py) |
| 新增 | [perception/uw_perception/contracts.py](../perception/uw_perception/contracts.py) |
| 新增 | [perception/uw_perception/node.py](../perception/uw_perception/node.py) |
| 修改 | [scripts/container-command](../scripts/container-command) |
| 新增 | [scripts/prepare_m2_upstream.py](../scripts/prepare_m2_upstream.py) |
| 修改 | [scripts/uw](../scripts/uw) |
| 修改 | [simulations/package.xml](../simulations/package.xml) |
| 修改 | [simulations/setup.py](../simulations/setup.py) |
| 新增 | [simulations/uw_simulations/m2_scene.py](../simulations/uw_simulations/m2_scene.py) |
| 新增 | [simulations/uw_simulations/truth_node.py](../simulations/uw_simulations/truth_node.py) |
| 新增 | [test/m2-acceptance.yaml](../test/m2-acceptance.yaml) |
| 新增 | [test/m2-freeze.json](history/freezes/m2-freeze.json) |
| 新增 | [test/test_m2.py](../test/test_m2.py) |
| 修改 | [test/test_repository.py](../test/test_repository.py) |
| 新增 | [vendor/patches/0007-m2-sensor-semantics.patch](../vendor/patches/0007-m2-sensor-semantics.patch) |
| 新增 | [vendor/patches/0008-m2-acquisition-stamps.patch](../vendor/patches/0008-m2-acquisition-stamps.patch) |
| 新增 | [vendor/source-lock.m2.yaml](../vendor/source-lock.m2.yaml) |

上游补丁与 SHA-256 单独记录在 [来源说明](sources.md) 和 [M2 来源锁](../vendor/source-lock.m2.yaml)。
