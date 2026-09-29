# RViz 图像订阅与 ViewManager 生命周期修复

M1-v1/v2 在双图像负载结束时偶发 RViz -6/-11。控制和观测通过不抵消此失败。
最初的分阶段退出仅改变时序，没有修复内存所有权；相关失败 run 全部保留。

## 实际诊断

`v3_rviz_memcheck_full--20260921T173657Z--ffc52f37d368` 的 `rviz-memcheck.log`
在 ImageDisplay 析构中记录了对已释放 `message_filters::Signal1<Image>` 的访问：
Dock 隐藏先调用 `onDisable()` → `unsubscribe()`，释放 SubscriberFilter；
随后析构再次 `disconnect()`，旧 Connection 仍保留指向已释放 Signal1 的回调。
实际安装版本为 RViz 14.1.23。

上游固定源码：
[ImageTransportDisplay](https://github.com/ros2/rviz/blob/feb01669f1297df2af755ce9cd2ed18083e7a8b2/rviz_default_plugins/include/rviz_default_plugins/displays/image/image_transport_display.hpp)。
同版本提交 `feb01669f1297df2af755ce9cd2ed18083e7a8b2` 加入 source-lock；没有升级到 latest。

## 最小补丁与回归

`vendor/patches/0005-rviz-idempotent-image-unsubscribe.patch` 在 disconnect 后、
释放 subscriber 前清空 Connection，使重复取消订阅安全。
SHA-256：`55fd803d8ee7922baf2bac3d88569a6b6491a985f4b5181b9c800902ad68d912`。
此补丁重新编译同版本 `rviz_default_plugins`；DDS XML、Fast DDS 二进制与传输布局未改。

`test/rviz_lifecycle/image_unsubscribe.cpp` 使用实际 ImageTransportDisplay、真实
SubscriberFilter，模拟 Dock 隐藏后再次取消订阅及析构，循环 100 次。
同一用例在未修补镜像内由 ASan 稳定报告 heap-use-after-free，退出 1；
修补后退出 0。日志 `.cache/m1/rviz-regression-before.log` /
`rviz-regression-after.log`，构建中的同一回归也通过。

此用例无 GPU/ROS graph，只验证订阅生命周期；图形负载及正常进程退出另行实际验收，
见 [M1 报告](validation-2026-09-22-m1.md)。诊断期间还观察到 Fast DDS 静态清理栈异常，
不据此声称消除了所有上游内存问题。修复依据是可重现的 ImageDisplay UAF 和最小测试，
最终运行证据的有效范围是本机、本版本及已执行病例。

M0 与 v3 镜像中的 `libfastrtps.so.2.14.6` SHA-256 均为
`5c42ee390b403e0bacfbc5c535dc13fce0fe86b4a1f0243a115f3236f4b9c7de`，
`librmw_fastrtps_cpp.so` 均为
`51c1476d193f62f8f75535b52998c84f3e64177ab0c97368042aac8653bc02d0`。
实际比对日志保存于数据根 `reports/m1-v3-build-evidence/`，同目录保存构建、57 项测试、
ASan 修复前后日志及原 41 项测试保留审计。

## 第二个所有权问题：ViewManager 未释放

v3 的正式两轮负载仍退出 -6，且实际 `/proc/<rviz>/maps` 已确认加载修补插件。
后续 `v4_rviz_memcheck_patched--20260921T181707Z--5ba6127f198d` 不再报告原
ImageDisplay 回调 UAF，但仍出现 Fast DDS 静态销毁路径的端口 WatchTask UAF。
其 GPU 初始化较慢，本轮仅作退出内存诊断，不作为观测或控制验收。

固定 RViz 源码中 VisualizationManager 创建 ViewManager 后漏掉删除；
ViewController 的 reset_time 服务因此滞留。补丁 0006 在 scene 和 ROS node
仍有效时删除 ViewManager；没有修改 Fast DDS 或其传输配置。
哈希 `39f3065889ad2406def504c1302cb5aa429a0ac6404f1ff15c8993b078eb5bd2`。

`test/rviz_lifecycle/view_manager_ownership.cpp` 创建实际 RViz frame、Orbit
view controller 和 ROS 服务，以 QPointer 验证 frame 销毁后 ViewManager 是否销毁。
修补前打印 `VIEW_MANAGER_RELEASED=0` 并在进程退出崩溃（139）；修补后为 1、退出 0。
日志 `view-ownership-before-2.log` / `view-ownership-after.log` 位于 `.cache/m1/`。
早期一次测试编译使用错误构造函数签名的失败也保留，未当作运行结果。

完整图像 Memcheck 还报告 Ogre STBI 载入占位图的 malloc/delete[] 配对问题及
NVIDIA 零长度分配告警；本轮不声称所有上游内存诊断零告警。实际必需阶段门仍以
正常运行的原始退出码及控制/观测断言判定，不忽略任何普通运行的非零退出。

修补后的真实 frame 所有权回归另在 Valgrind 下执行：
`VIEW_MANAGER_RELEASED=1`，没有 Invalid read/write、没有 DDS 清理 UAF；
仅保留 NVIDIA glcore 的 realloc(size=0) / posix_memalign(size=0) 两个诊断上下文，
因此工具退出 99，而普通执行退出 0。未压制日志或将 Memcheck 写成零告警。
原始记录为 `.cache/m1/view-ownership-after-memcheck.log`；
补丁前后镜像、日志哈希和真实退出码另存 `view-ownership-proof.json`。

最终 v4 同时构建 `rviz_common` 与默认插件。最终镜像再次通过 ASan 图像用例及
实际 GPU frame 所有权回归；日志与源码锁归档在数据根
`reports/m1-v4-build-evidence/`。该目录 `final-middleware-binary-hashes.txt` 证实上述两个
DDS 库在 M0 与最终 v4 中仍完全相同。正式两轮完整图形负载及两轮 M0 的正常退出
结果独立记录在 [本轮报告](validation-2026-09-22-m1.md)。
