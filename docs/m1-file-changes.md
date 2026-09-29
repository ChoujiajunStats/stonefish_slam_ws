# M1 实际文件修改清单

相对实施前完整归档逐文件比较。原始蓝图、历史 M0 验收文档、原 M0 配置、DDS XML
及补丁 0001/0002 未改写；所有文件原本未跟踪，没有 commit/push。
运行生成配置另存各 run，不混入下表。

| 文件                                                            | 操作     | 用途                         |
| ------------------------------------------------------------- | ------ | -------------------------- |
| `README.md`                                                   | MODIFY | 工程说明                       |
| `app/README.md`                                               | MODIFY | schema/launch/证据组装         |
| `app/launch/control.launch.py`                                | ADD    | schema/launch/证据组装         |
| `app/launch/inspect.launch.py`                                | MODIFY | schema/launch/证据组装         |
| `app/package.xml`                                             | MODIFY | schema/launch/证据组装         |
| `app/setup.py`                                                | MODIFY | schema/launch/证据组装         |
| `app/uw_app/m1_config.py`                                     | ADD    | schema/launch/证据组装         |
| `app/uw_app/runner.py`                                        | MODIFY | schema/launch/证据组装         |
| `app/uw_app/window.py`                                        | ADD    | schema/launch/证据组装         |
| `benchmark/README.md`                                         | MODIFY | 真实病例、故障/指标/绘图              |
| `benchmark/package.xml`                                       | MODIFY | 真实病例、故障/指标/绘图              |
| `benchmark/setup.py`                                          | MODIFY | 真实病例、故障/指标/绘图              |
| `benchmark/uw_benchmark/artifacts.py`                         | MODIFY | 真实病例、故障/指标/绘图              |
| `benchmark/uw_benchmark/campaign.py`                          | ADD    | 真实病例、故障/指标/绘图              |
| `benchmark/uw_benchmark/m1_case.py`                           | ADD    | 真实病例、故障/指标/绘图              |
| `benchmark/uw_benchmark/m1_observation.py`                    | ADD    | 真实病例、故障/指标/绘图              |
| `benchmark/uw_benchmark/plots.py`                             | ADD    | 真实病例、故障/指标/绘图              |
| `benchmark/uw_benchmark/probe.py`                             | MODIFY | 真实病例、故障/指标/绘图              |
| `config/run.actuator_probe.yaml`                              | ADD    | 显式 M1/诊断配置                 |
| `config/run.m1.yaml`                                          | ADD    | 显式 M1/诊断配置                 |
| `controller/README.md`                                        | ADD    | 四维速度及水平姿态闭环                |
| `controller/config/defaults.yaml`                             | ADD    | 四维速度及水平姿态闭环                |
| `controller/package.xml`                                      | ADD    | 四维速度及水平姿态闭环                |
| `controller/resource/uw_controller`                           | ADD    | 四维速度及水平姿态闭环                |
| `controller/setup.cfg`                                        | ADD    | 四维速度及水平姿态闭环                |
| `controller/setup.py`                                         | ADD    | 四维速度及水平姿态闭环                |
| `controller/uw_controller/__init__.py`                        | ADD    | 四维速度及水平姿态闭环                |
| `controller/uw_controller/core.py`                            | ADD    | 四维速度及水平姿态闭环                |
| `controller/uw_controller/node.py`                            | ADD    | 四维速度及水平姿态闭环                |
| `docker/Dockerfile`                                           | MODIFY | 独立 M1 镜像，保持 DDS/IPC        |
| `docker/Dockerfile.m1`                                        | ADD    | 独立 M1 镜像，保持 DDS/IPC        |
| `docker/compose.yaml`                                         | MODIFY | 独立 M1 镜像，保持 DDS/IPC        |
| `docs/00-home.md`                                             | MODIFY | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/adr-0002-control-authority-and-watchdog.md`             | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/architecture.md`                                        | MODIFY | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/interfaces.md`                                          | MODIFY | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-control-evidence.md`                                 | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-file-changes.md`                                     | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-formal-results.md`                                   | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-implementation-plan.md`                              | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-load-regression.md`                                  | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-rviz-lifecycle-fix.md`                               | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/m1-thruster-audit.md`                                   | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/module-controller.md`                                   | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/module-guard.md`                                        | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/roadmap.md`                                             | MODIFY | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/runbook-m1.md`                                          | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/sources.md`                                             | MODIFY | 同一 Obsidian Vault 的实施/验收文档 |
| `docs/validation-2026-09-22-m1.md`                            | ADD    | 同一 Obsidian Vault 的实施/验收文档 |
| `guard/README.md`                                             | ADD    | 控制权与健康/时效检查                |
| `guard/config/defaults.yaml`                                  | ADD    | 控制权与健康/时效检查                |
| `guard/package.xml`                                           | ADD    | 控制权与健康/时效检查                |
| `guard/resource/uw_guard`                                     | ADD    | 控制权与健康/时效检查                |
| `guard/setup.cfg`                                             | ADD    | 控制权与健康/时效检查                |
| `guard/setup.py`                                              | ADD    | 控制权与健康/时效检查                |
| `guard/uw_guard/__init__.py`                                  | ADD    | 控制权与健康/时效检查                |
| `guard/uw_guard/cli.py`                                       | ADD    | 控制权与健康/时效检查                |
| `guard/uw_guard/contracts.py`                                 | ADD    | 控制权与健康/时效检查                |
| `guard/uw_guard/node.py`                                      | ADD    | 控制权与健康/时效检查                |
| `interfaces/CMakeLists.txt`                                   | ADD    | 授权消息与服务                    |
| `interfaces/COLCON_IGNORE`                                    | REMOVE | 授权消息与服务                    |
| `interfaces/README.md`                                        | MODIFY | 授权消息与服务                    |
| `interfaces/msg/ActuatorOutput.msg`                           | ADD    | 授权消息与服务                    |
| `interfaces/msg/AuthorizedCommand.msg`                        | ADD    | 授权消息与服务                    |
| `interfaces/msg/ControlRequest.msg`                           | ADD    | 授权消息与服务                    |
| `interfaces/package.xml`                                      | ADD    | 授权消息与服务                    |
| `interfaces/srv/Control.srv`                                  | ADD    | 授权消息与服务                    |
| `robot/README.md`                                             | MODIFY | 真实推进器映射/有界分配               |
| `robot/config/thrusters_m1.yaml`                              | ADD    | 真实推进器映射/有界分配               |
| `robot/package.xml`                                           | MODIFY | 真实推进器映射/有界分配               |
| `robot/uw_robot/thrusters.py`                                 | ADD    | 真实推进器映射/有界分配               |
| `scripts/container-command`                                   | MODIFY | 薄 CLI 与固定源码重放              |
| `scripts/record_build.py`                                     | MODIFY | 薄 CLI 与固定源码重放              |
| `scripts/repatch_upstream.py`                                 | ADD    | 薄 CLI 与固定源码重放              |
| `scripts/uw`                                                  | MODIFY | 薄 CLI 与固定源码重放              |
| `simulations/README.md`                                       | MODIFY | 受保护执行适配、M1 场景、退出处理         |
| `simulations/package.xml`                                     | MODIFY | 受保护执行适配、M1 场景、退出处理         |
| `simulations/setup.py`                                        | MODIFY | 受保护执行适配、M1 场景、退出处理         |
| `simulations/uw_simulations/actuator_node.py`                 | ADD    | 受保护执行适配、M1 场景、退出处理         |
| `simulations/uw_simulations/m1_scene.py`                      | ADD    | 受保护执行适配、M1 场景、退出处理         |
| `simulations/uw_simulations/observation_node.py`              | MODIFY | 受保护执行适配、M1 场景、退出处理         |
| `test/README.md`                                              | MODIFY | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/frozen/m1-v1.json`                                      | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/frozen/m1-v2.json`                                      | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/frozen/m1-v3.json`                                      | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/m1-acceptance.yaml`                                     | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/m1-freeze.json`                                         | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/rviz_lifecycle/CMakeLists.txt`                          | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/rviz_lifecycle/image_unsubscribe.cpp`                   | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/rviz_lifecycle/minimal.rviz`                            | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/rviz_lifecycle/run.py`                                  | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/rviz_lifecycle/view_manager_ownership.cpp`              | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/test_m1.py`                                             | ADD    | 保留 M0 语义并扩展 M1 测试/冻结       |
| `test/test_repository.py`                                     | MODIFY | 保留 M0 语义并扩展 M1 测试/冻结       |
| `ui/README.md`                                                | MODIFY | 复用观察布局说明                   |
| `vendor/README.md`                                            | MODIFY | 固定源码锁与四个独立补丁               |
| `vendor/patches/0003-pre-actuator-safety-hook.patch`          | ADD    | 固定源码锁与四个独立补丁               |
| `vendor/patches/0004-terminal-command-lease.patch`            | ADD    | 固定源码锁与四个独立补丁               |
| `vendor/patches/0005-rviz-idempotent-image-unsubscribe.patch` | ADD    | 固定源码锁与四个独立补丁               |
| `vendor/patches/0006-rviz-release-view-manager.patch`         | ADD    | 固定源码锁与四个独立补丁               |
| `vendor/source-lock.yaml`                                     | MODIFY | 固定源码锁与四个独立补丁               |
