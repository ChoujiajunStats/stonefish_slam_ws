# Porth 洞穴可视化与预设路径演示

用户于 2026-09-24 授权导入 Porth yr Ogof Sump 9，调整显示尺度，显示真实
BlueROV2 模型并运行一条预设路径。修改前归档：
`reports/porth-baseline-20260923T183225Z/`（UTC）。

当前 RViz 使用几何示意体；M3 用 OpenVINS 估计反馈，已有 SLAM 状态特征，
没有回环、持久地图或自主探索规划。用户进一步明确先验证现有仿真内的 SLAM，
暂不考虑自主避障。本次保留 OpenVINS 前端，接入 RTAB-Map 双目建图后端，
检查实时点云/位姿图、持久数据库和重新读取。固定路径仅用于采集数据，
由既有任务 Action 执行；不把导入的洞穴网格冒充建图输出。

实施范围：robot 的独立 mesh URDF；simulations 的资产导入、尺度/坐标变换、
洞穴场景及显示；localization 的 RTAB-Map 配置；app/config 的显式
Porth 场景分支；benchmark 的有限时长演示评价；scripts/uw 薄入口；docs。
保留 M0–M3 默认配置、动力学、原生 watchdog、DDS 与旧镜像/证据。

先保存带哈希的外部资产，检查路径与碰撞表面距离；构建、静止检查后再显式
执行短路径。尺度是本次仿真实验选择，不宣称原模型真实测量尺度已经标定。
所有运行使用新目录，保留失败与截图、传感器、估计和实际推进器证据。
