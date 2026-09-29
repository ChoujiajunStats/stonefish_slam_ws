# Porth 全洞规定路线 SLAM：2026-09-24

保留朝向的 **v4 全程采集 PASS**。约 571 m 规定路线已完成，末端进入
DISARMED 并中和，12 个必要进程及宿主 CLI 均退出 0；数据库、MCAP 正常
关闭，无本次容器或网络残留。**这不等于整洞完整表面重建通过**。

上一版完整采集 v3 **FAIL**：在 555.797 / 570.883 m 处触发 `SLAM processing stale`，
余下 15.086 m 未完成。run：`porth_survey_full_v3--20260923T213639Z--e880633b9f71`。
三支路与主通道已访问，但不能把这些局部覆盖改写为完整运行通过。
本报告与历史 M0–M3、Porth 短路线验收分开；失败证据完整保留。

成功运行：`porth_survey_full_v4--20260923T224043Z--c68841acc630`，保持原路线、
保留朝向、速度、Jerlov 0.22 和所有安全门限。冻结文件为
`test/porth-survey-freeze-v4.json`，新增在线工作记忆最多 600 节点与 250 ms
内存管理时间目标；250 ms 不是硬实时完成保证。完整历史图离线再优化后导出。

v4 修复前先用 v3 的全部 2947 个传感器节点做离线验证：最慢处理 1.531 s、
字典最多 229968 词，2947 个 Node/Data 均保留，955 次历史节点取回。
这项离线性能证据与以下真实运行结果分开。

## v4 真实运行

UTC 2026-09-23 22:40:43 至 23:32:26（本地 2026-09-24），含启动/退出
3102.91 s。路线长度 570.883 m，完成时投影进度 570.738 m，余下 0.145 m
符合预先设定的 0.18 m 到点容差；实际真值轨迹累计 566.973 m。
这是一次完整冷启动运行，不声称三次重复。

左右图像各接收 60590，IMU 307936；在线报告 217 次回环、249 次邻近检测。
数据库保留 3039 个 Node/Data。工作记忆最多 600 节点、字典最多 229433 词，
真实运行单帧最长处理 1.623 s，未触发原 5 s 新鲜度保护。在线最终工作图
629 节点，不以此冒充数据库全部历史节点数。

89 个冻结文件逐项与实际运行源码快照一致，镜像和路线匹配。
检查 `/clock` 发布者唯一，OpenVINS/RTAB-Map 无真值订阅；控制器与 Guard
使用的真值反馈明确属于此采集模式。独立评价得到原 OpenVINS 全程位置
RMSE 9.172 m、最大 21.129 m；该数值不是优化后的 SLAM 轨迹精度。

审计：`reports/porth-survey-delivery-v4-20260923T223959Z/final-runtime-audit.json`。
`gui-show.json` 与 50/150/300/450/550 m 的 RViz 截图保留；机器人随车视角
的 Stonefish 与入口返程 RViz 截图位于本 run 的 `figures/`。

## v4 原在线地图导出与覆盖

完整图全局优化导出 4599456 点、3006 条位姿（2996 条与独立真值时间重叠）。
初始 yaw/平移对齐后，优化轨迹位置 RMSE 6.134 m、最大 15.950 m。
原 OpenVINS 的 9.172 m 与此数值分开报告；没有全轨迹最佳拟合或尺度修正。

完整原始视觉网格共 2219185 个三角面、约 7352.96 m²。按面积均匀采样
30 万点，距重建点云 0.15/0.30/0.50 m 内的表面比例为
**26.28% / 40.05% / 51.11%**。反向抽样 10 万个点云点，距原表面相应
范围内比例约 **14.52% / 25.95% / 36.91%**；该距离只在 24 个最近面心的
候选三角形内取最小值，是全局最近表面距离的近似。漂移、噪声和未观察
区域均影响指标，不能把缺失全部归因于返航朝向。

已规划主线 511 点、三条支路均在实际轨迹 1 m 内；对未截短的原始 527 点
主线，这一比例为 97.34%，最远未进入端部离轨迹 6.713 m。路线访问、
可见性和表面重建是不同指标，不以规划时排除端部来缩小表面评价分母。

报告：`reports/slam-export-20260923T233344Z-16cf3c0a/`，其中
`whole-cave-coverage.png`、`reconstruction-3d.png`、`reloaded-trajectory.png`
及 `reconstruction.html` 都来自本轮真实双目重建。原始资产未合入点云。
原始数据库 SHA-256 在导出前后均为
`fd860a6ffdbf77ccfeb4e77b153d683897663beb7dd46ee1d06a67fc179b1e06`。

## v4 单独的离线双目对照

在本次全程结果揭晓前，依据两种历史短程标定冻结 `porth-offline-processing-v2`，
采用 `rtabmap-reprocess -odom --Kp/Parallelized false`。输入为原数据库保存的
约 1 Hz 双目关键帧，重新估计双目里程计；不是实时 OpenVINS，也不是原始
20 Hz 全图像流重放。无真值/洞穴资产算法输入，处理容器无网络，原 run 只读。

3039/3039 帧处理完成，日志中 lost 为 0；三个处理/导出命令均退出 0，
原数据库哈希不变。导出 3682719 点、3023 条位姿，其中 3014 条与真值
时间重叠；用该估计器自身首个位姿作初始 yaw/平移对齐，未拟合整条轨迹。

| 同一次采集，不同处理方法 | 原 OpenVINS + RTAB-Map 全局导出 | 离线双目 VO + RTAB-Map |
|---|---:|---:|
| 优化后位置 RMSE / 最大误差 m | 6.134 / 15.950 | 1.584 / 3.965 |
| 完整表面覆盖，0.15 m | 26.28% | 36.99% |
| 完整表面覆盖，0.30 m | 40.05% | 52.14% |
| 完整表面覆盖，0.50 m | 51.11% | 61.82% |
| 点云点距原表面 0.30 m 内比例（近似） | 25.95% | 47.51% |

以上各自使用全部有效时间重叠样本，没有挑选最好窗口。关键帧保留数量不同，
不能把表格理解为严格相同时间采样的 ATE 排名，也没有三次重复统计结论。
离线对照改善了本轮误差，但仍有空缺和离群点；**完整表面重建仍为 PARTIAL**。
不能用离线结果替换原在线结果，也不能据此断言倒车导致了全部重建缺陷。

报告：`reports/slam-stereo-reprocess-20260923T233344Z-98024f7b/`。
冻结记录与实际处理脚本为交付目录的 `offline-processing-freeze-v2.json` 和
`survey_reprocess.py`，命令、退出码、丢帧核验在 `reload-metrics.json`。
独立交互预览为仓库 `.cache/porth-survey/full-v4-online.html` 与
`.cache/porth-survey/full-v4-offline-stereo.html`，标题明确区分两种处理。

## v3 长程失败诊断

持续约 50 分钟后，RTAB-Map 第 2934 帧处理耗时 6.520 s，其中等待视觉词典
更新 6.345 s、图优化 0.072 s。字典达到 870797 词；此前约 435633 词时也
出现过 3.256 s 的字典更新等待。原配置工作记忆无上限，增量 FLANN 索引
重建随字典规模增长产生长暂停。冻结的 5 s SLAM 新鲜度检查因此中止采集。
v4 已验证有界在线工作集，历史关键帧仍保存在数据库中；未放宽 5 s 门限。

实际推进器已中和、Guard/末端 FAULT 锁存。benchmark 退出 1，其余 11 个
容器内必要进程退出 0，bag 正常落盘、SQLite 重读成功，容器退出 1。
外层宿主启动命令另观测到返回 143，来源未确定；容器内采集继续至上述
明确故障。该外层异常与 SLAM 字典暂停分别记录，不能称全部进程正常退出。
本 run 的专属空网络已清理，其他项目容器保留。

失败期间保存 2908 个在线图节点、642489 个显示点、312 次接受的回环和
368 次邻近检测；独立真值评价的 OpenVINS 位置 RMSE 为 12.115 m。
这些数值不代表最终优化地图精度，后者通过数据库导出独立评价。

v3 原在线地图重读导出 4464765 点，最终优化轨迹 RMSE 4.392 m；完整视觉
表面在 0.15/0.30/0.50 m 距离标准下覆盖 30.01%/47.26%/60.34%。
所规划主通道与三条支路的中心线都被实际轨迹覆盖，但这不等于表面覆盖。
报告：`reports/slam-export-20260923T222813Z-a8b6b640/`。

另有预先冻结的离线双目 VO + RTAB-Map 对照，未给算法真值或资产输入：
导出 3596897 点，有效轨迹 RMSE 1.022 m，0.30 m 表面覆盖 54.62%。
2947 帧全部处理，最后 13 帧在原采集的长暂停后丢失跟踪，因此跟踪判定为
PARTIAL；不能以导出成功冒充端到端通过。原 OpenVINS 在线结果保留并单列。
对照报告：`reports/slam-stereo-reprocess-20260923T223015Z-9601796f/`。

## 本轮 M0 观察回归

原配置 `config/run.empty_water.example.yaml` 在新增 survey 镜像下完成一次
60 s 连续观察：`bluerov_empty_water--20260923T223214Z--a411af33f5e7`，
manifest/原 probe 为 SUCCEEDED/PASS，六个进程退出均为 0，DDS 哈希未变。
左/右图像接收 1726/1811，首个时钟 0.01 s，结束 61.08 s；debug bag 落盘。
实际生成场景无推进器 ROS 订阅入口。原 probe 的 unverified 原样保留；
额外 ROS graph 抽查及截图错过窗口关闭时刻，未作为本轮证据计入。
这不是两次冷启动 M0 复验，也不回填任何历史报告。

## 已验证部分

- 80 项容器契约测试 PASS；本机纯契约 80 项中 8 项按缺少容器依赖跳过。
- 三条支路末端的真实自由刚体、推进器驱动往返均 PASS。它们是三个不同
  支路病例，不是三次同路线重复。路线跟随使用明确的 PRIVILEGED_DEBUG；
  OpenVINS 与 RTAB-Map 不接收真值或已知洞穴网格。
- 两盏随车光源与青色水体（Jerlov 0.22）已在真实相机、RViz、Stonefish
  画面验证。原贴图与 UV 未丢失。来源和边界见 [光学审计](porth-optics.md)。
- 新镜像末端适配 SIGKILL 回归 PASS：接收设定值在 0.206758395 s 中和，
  物理继续推进，故障锁存，实际八通道反馈正常记录。该运行的采集检查为
  FAIL、适配进程退出 -9 原样保留，不能称“所有进程正常退出”。

| 支路 | 实际行程 m | OpenVINS 位置 RMSE m | 回环次数 |
|---|---:|---:|---:|
| 1 | 17.2819 | 0.0553 | 23 |
| 2 | 16.9248 | 0.0405 | 22 |
| 3 | 16.3964 | 0.0580 | 18 |

对应目录及此前失败见 [完整运行索引](porth-survey-run-index.md)。
早期完整路线在约 169 m 因视觉健康退化失败，另一次完整路线在新发现离线
跟随误差后主动 DISARM；未拼接这些片段冒充一次完整采集。

## 本次冻结

`test/porth-survey-freeze-v4.json`：89 个文件、配置和路线 SHA-256 已冻结。
当前实际 run 的源码快照逐项匹配，镜像与路线哈希匹配。
镜像 `underwater-stack:m3-porth-survey-v1`：
`sha256:6962e626a341a9141dce2e0e679d2dd472e5eaf022324599319efe002b5d1cf4`。
父 Porth 与历史 M0–M3 镜像标签未覆盖。

新增补丁 `0009-survey-optical-lights.patch` 仅允许无推力 LIGHT 与八个推进器
共存，不改变授权、超时或动力学。原 `<cstdint>`、传感器和末端保护补丁保留。
原 DDS XML、单容器私有 IPC、相机与 IMU 采样均未改变。

路线 v14 为实验尺度 1.8，约 570.883 m，包含主通道往返和三条支路。
碰撞网格距离筛查下界 0.861 m；完整视觉网格最小候选面距离约 0.751 m。
开放网格的朝向筛查只是启发式，不能证明封闭实体包含关系。机器人筛查半径
0.50 m、跟随偏差终止阈值 0.25 m 保持冻结；端部保留可视/通行余量。

## 证据与评价边界

数据根目录 `$HOME/.local/share/underwater-stack`：

- `reports/porth-optical-audit-20260923T213300Z/`：参考源码和来源哈希。
- `reports/porth-survey-delivery-v3-20260923T213700Z/terminal-watchdog.png`：
  原生接收设定值、实际 RPM 与推力衰减。
- `reports/porth-survey-delivery-v4-20260923T223959Z/dictionary-latency-final.png`：
  v3 真实失败、离线标定、v4 真实完成的处理延迟；三者分开标注。
- `runs/<run_id>/`：源码归档、解析配置、补丁锁、实际场景、DDS、
  MCAP、SLAM DB、传感器图像、授权事件、过程日志与退出记录。

已完成完整运行、数据库重读、真实双目点云导出及全视觉表面评价。
不把主通道走完、可视窗口中看见模型、SLAM 点数增加或短程 PASS 当成整洞
完整重建的证据。原始资产不混入输出，不使用真值矫正地图或补出未观测表面。

## 实际命令与结果

镜像由 `docker/Dockerfile.survey` 实际构建，固定 wrapper 重新编译成功；日志
`.cache/porth-survey/image-build-v1.log`，容器 overlay 编译见各次 launcher 日志。

```bash
UW_IMAGE=underwater-stack:m3-porth-survey-v1 ./scripts/uw test
./scripts/uw test --local
./scripts/uw porth config/run.porth-survey.yaml --arm
UW_IMAGE=underwater-stack:m3-porth-survey-v1 ./scripts/uw run config/run.empty_water.example.yaml
UW_IMAGE=underwater-stack:m3-porth-survey-v1 ./scripts/uw slam-export porth_survey_full_v4--20260923T224043Z--c68841acc630
UW_IMAGE=underwater-stack:m3-porth-survey-v1 ./scripts/uw survey-coverage porth_survey_full_v4--20260923T224043Z--c68841acc630 slam-export-20260923T233344Z-16cf3c0a
```

以上为已执行的具体入口：容器 80/80 PASS；本机依赖不足的 8 项跳过，
不算作 ROS 集成通过。全程采集一次 PASS，M0 本轮一次 60 s PASS；完整
19 次采集尝试的失败与未完成判定见 [运行索引](porth-survey-run-index.md)。
不是三次完整路线重复，不把不同版本、调参与正式冻结运行拼成统一通过。

剩余边界：部分表面重建、米级全局误差、未验证真正掉头返航、未完成三次
全程重复、没有封闭高精度纹理网格或自主避障。下一版改变返航朝向时另存
冻结版本，保留本次基线。M4、实机与多机器人未开始，没有自动 commit/push。
本次新增运行与报告约 14.26 GB，低于 25 GB 预算；旧证据未删除。

[运行与水体调节](runbook-porth-survey.md) · [实施计划](porth-survey-plan.md)
