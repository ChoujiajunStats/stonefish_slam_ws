---
title: Underwater Stack
status: m3-accepted
---

# Underwater Stack

新协作仓库 **stonefish_slam_ws**：
[部署指南](deployment.md) / [模块边界](repository-structure.md) /
[2026-09-29 整合验证](validation-2026-09-29-workspace.md)。
以下阶段结论保留为原研究工作区的历史证据。


新增可选 **ORB-SLAM3 在线双目** profile：约 571 m 规定路线在线采集通过，
原始在线位置 RMSE 0.458 m、p99 延迟 80 ms、零跟踪丢失。Atlas 加载成功，
严格数值一致性检查 FAIL（最大平移分量差 0.061 mm），具体边界见报告。
控制仍为 `PRIVILEGED_DEBUG`，ORB 只接收双目图像，输出稀疏地图。
- [ORB 本轮报告](validation-2026-09-24-orbslam3.md) / [启动与使用](runbook-orbslam3.md)

Porth 全洞规定路线 SLAM 采集 v4 已跑通，约 571 m、主通道与三条支路。
采用显式 `PRIVILEGED_DEBUG` 路径反馈，SLAM 仍只接收传感器/估计状态。
新增随车灯、可调青色水体和启动时双窗口显示。原在线地图全局导出后，
完整视觉表面在 0.30 m 范围内覆盖 40.1%；重建有漂移和空缺，未通过完整表面重建。
- [全洞运行指南](runbook-porth-survey.md) / [光学与纹理审计](porth-optics.md)
- [采集计划](porth-survey-plan.md) / [逐次运行索引](porth-survey-run-index.md)
- [本轮验证与失败诊断](validation-2026-09-24-porth-survey.md) / [文件范围](porth-survey-file-changes.md)
- [2026-09-24 历史录制清理与 20 倍在线回放](storage-cleanup-2026-09-24.md)

新增可选演示：**Porth 洞穴中的 OpenVINS + RTAB-Map 双目 SLAM 已实际运行**，
支持真实 BlueROV2 外观、预设路径、地图/轨迹显示和数据库保存/重读。
没有自主探索或避障；不改变下列历史 M0–M3 验收范围。
- [Porth SLAM 本机报告](validation-2026-09-24-porth-slam.md) / [启动与使用](runbook-porth-slam.md)

当前阶段：**M3-v4 局部导航与任务已通过限定仿真场景本机验收**。
最终同版 M3 22 项与旧阶段回归 17 项全部 PASS，另完成同版 CLI 实测。
M3 使用 OpenVINS 估计反馈；真值仅供独立评价。尚无避障或全局地图。
M2-v3 双目/IMU 与 OpenVINS 已通过历史本机验收。13/13 正式病例 PASS，
包含三次轨迹重复、五项真实故障和两轮图形负载；M0/M1 回归另行记录。
M1-v4 的 54/54 次正式运行 PASS 是保留的历史基线。
M0/M1 的状态源仍是 PRIVILEGED_DEBUG；M2 估计状态与真值评价独立。

- [M3 验收报告](validation-2026-09-23-m3.md) / [运行指南](runbook-m3.md)
- [M3 全部运行](m3-run-index.md) / [文件范围](m3-file-changes.md) / [实施计划](m3-implementation-plan.md)
- [Navigation](module-navigation.md) / [Tasks](module-tasks.md) / [M3 决策](adr-0004-estimated-navigation-and-missions.md)

- [M2 验收报告](validation-2026-09-23-m2.md) / [运行指南](runbook-m2.md)
- [全部运行索引](m2-run-index.md) / [文件范围](m2-file-changes.md)
- [M2 审计与实施计划](m2-implementation-plan.md)
- [Perception](module-perception.md) / [Localization](module-localization.md)
- [传感器采样时间与估计发布权](adr-0003-sensor-time-and-estimator-authority.md)

- [首次审计](audit-2026-09-21.md)
- [首次实现验证](validation-2026-09-21.md)
- [实际运行验收](runtime-validation-2026-09-21.md)
- [M1 实现与本轮验收](validation-2026-09-22-m1.md)
- [M1 运行指南](runbook-m1.md)
- [M1 推进器/参考点审计](m1-thruster-audit.md)
- [控制器](module-controller.md) / [Guard](module-guard.md)
- [唯一控制权与末端保护决策](adr-0002-control-authority-and-watchdog.md)
- [架构与实施映射](architecture.md)
- [接口契约](interfaces.md)
- [阶段与验收](roadmap.md)
- [运行指南](runbook.md)
- [扁平仓库决策](adr-0001-flat-monorepo.md)
- [来源与许可证](sources.md)

以本目录作为 Obsidian Vault；运行输出保存在外部 `UW_DATA_ROOT`。
