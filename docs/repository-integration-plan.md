# 仓库整合审计与实施范围：2026-09-29

原项目保持在旁边的 StoneFish_Nav；本目录为新建 stonefish_slam_ws。
原项目无提交、无远端；没有重置或覆盖其文件。历史运行、图片、视频、资产、
Docker 标签保留原处。新仓库不纳入 .cache、生成病例配置、bag、Atlas 或大资产。

审计：现有 12 个包的 ROS 声明无环，但 app 与 benchmark 经证据工具和数据库
检查存在 Python 反向依赖。构建链依赖仅本机存在的历史镜像 ID；全洞路线与
Porth 资产位于外部数据根，没有可移植导入入口。协作入口、CI、贡献规范缺失。

实施：
1. 保留算法/安全包职责及根目录并列方式。提取真实共用证据/存储工具到 runtime，
   解除 app/benchmark 的反向 Python 依赖，测试架构边界。
2. 将历史层叠构建整合为以公开锁定 ROS 基础镜像开始的多阶段 Dockerfile，
   profile 统一选择 core/vio/navigation/rtabmap/survey/orbslam3，实际镜像独立命名。
3. scripts/uw 保持薄入口；主机部署代码在 tools/uw_workspace 中按环境、构建、
   资产职责拆分，不承载控制或 SLAM 算法，不安装宿主算法依赖。
4. 显式导入带 SHA 的外部 Porth 资产与已验收路线；不把来源未明确可公开分发的
   大资产放入 Git。新数据根隔离于历史实验，历史冻结清单归档并明确不是新验收。
5. README、部署/结构/贡献指南、CI、模板与忽略规则。保留原设计和历史结论。
6. 本地/容器契约、实际镜像构建、M0 与 ORB 短程仿真复测；每次显示双窗口。
   最后检查可发布文件，提交新仓库并向用户指定远端推送，不 force push。

范围不含控制器/估计器调参、完整 M1–M3 再验收、新导航功能或实机。
远端确认为公开 ChoujiajunStats/stonefish_slam_ws；署名为用户提供的 Jiajun Zhou。
实际结果见 [部署验证](validation-2026-09-29-workspace.md)。
