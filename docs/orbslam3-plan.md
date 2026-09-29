# ORB-SLAM3 在线接入计划：2026-09-24

用户要求接入并主要运行 online ORB-SLAM3。复用当前 Porth 原生双目、
571 m 保留朝向路线、光学与控制链路；不改变已验收 M0–M3 配置。
当前无本项目仿真实例；存在其他项目容器，保持不动。仓库无提交基线，
实施前文件哈希保存在外部 reports/orbslam3-integration-*。

1. 固定官方 ORB-SLAM3 和 Pangolin 提交，新建独立派生镜像。
2. localization/ 增加 ROS 2 纯双目接收器：严格同采样时间配对、有限队列、
   实时状态/位姿/稀疏地图、最终轨迹及 Atlas 保存。无真值、OpenVINS 位姿
   或资产订阅。OpenVINS 保留为独立比较。实施中发现其初始朝向与 ORB
   gauge 不同，最终 RViz 机器人直接跟随 ORB 的 map→orb_body，两个树不相连。
3. app/ 增加显式 orbslam3_stereo profile；benchmark/ 复用规定路线安全
   采集，单独检查 ORB 跟踪与延迟；robot/、controller/、guard/ 和 DDS 不改。
4. 容器构建和契约测试，短程真实运行；通过后冻结配置并在线跑全洞路线。
   每轮显示 Stonefish/RViz，使用新目录，失败保留。控制为 PRIVILEGED_DEBUG，
   ORB 结果不进入推进器反馈。没有新增自主探索或避障。
5. 导出本轮轨迹、稀疏地图和实际在线跟踪统计，独立对照真值评价，汇报
   丢失/重定位/多地图情况。稀疏地图不作为稠密表面重建通过证据。

修改范围：localization/ 源码与配置、app/ 组装与证据、benchmark/ 检查和
评价、scripts/uw 薄入口默认镜像、docker/ 派生构建、vendor/ 固定锁与
必要补丁、config/ 新配置、test/ 新契约/清单、docs/ 报告/运行指南。
本轮数据预算 25 GB，宿主不安装依赖，旧镜像/历史 run 不覆盖。
