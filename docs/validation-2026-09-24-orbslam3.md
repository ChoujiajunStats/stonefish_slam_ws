# ORB-SLAM3 在线双目：2026-09-24

结论：**约 571 m 规定路线在线采集 PASS**，纯双目 ORB-SLAM3 已实际接入。
原始在线轨迹位置 RMSE 0.458 m，p99 延迟 80 ms；保存了原生稀疏地图。
Atlas 原生加载成功，但预先设定的逐分量 1e-6 严格一致性检查 **FAIL**，
最大平移分量差 0.061 mm，详见下文，未放宽门槛或回写判定。
本文件只报告本轮 ORB 证据；没有重新执行 M0 仿真回归。

## 任务与范围

使用既有 Porth v14 约 570.883 m 规定路线，保留朝向、倒车返航。
该 v14 路线使用主通道 527 个原中心线样本中的 511 个，保留末端视觉间距，
并走三条支路的可达内部端点；1.8 倍资产尺度是实验尺度，不是测绘标定。
路线走完不能解释为资产所有表面均被观察。
每次真实仿真都显示 Stonefish 和 RViz；固定体、理想外力、位姿写入均未用于
本轮运动。传感器、灯光、Jerlov 0.22、水动力、推进器、控制增益和 DDS 保持
原配置。控制及路径反馈仍为 **PRIVILEGED_DEBUG**。

ORB 接收实时左右 RGB，灰度＋显式 CLAHE(3.0, 8×8)，使用官方 **STEREO** 模式。
不读取 IMU、OpenVINS 里程计、真值或已知洞穴网格。OpenVINS 独立运行用于
比较；不供给 ORB，也不参与本轮路线控制。没有新增自主探索、避障或实机接口。

前端是 ORB 特征双目跟踪；后端为原生局部建图/局部 BA、回环和 Atlas。
不是将 OpenVINS 里程计改名，也不是事后离线重放后声称在线运行。
独立轨迹评价和 Atlas 重读在运行结束后进行，不向在线 SLAM 回灌结果。

## 构建与锁定

- 官方 [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3) 固定提交
  `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`。
- [Pangolin](https://github.com/stevenlovegrove/Pangolin) v0.8 固定提交
  `aff6883c83f3fd7e8268a9715e84266c42e2efe3`。
- 独立镜像 `underwater-stack:orbslam3-porth-v2`，最终本地 image ID：
  `sha256:d70e3ecc78a558ada68d836887732fbf77bf67668999c146dc585b199d743e41`。
  这是实际本地内容 ID，不冒称已推送仓库的 RepoDigest。
- 父镜像 `underwater-stack:m3-porth-survey-v1`，ID
  `sha256:6962e626a341a9141dce2e0e679d2dd472e5eaf022324599319efe002b5d1cf4`。
  M0 和历史标签未覆盖。
- 源锁为 `vendor/source-lock.orbslam3.yaml`，全程冻结清单为
  `test/orbslam3-freeze.json`（191 个文件）；容器实际二进制哈希另存
  `orb-binaries.json`。仓库无提交基线，保留完整源码归档与 dirty 状态。
- 单容器私有 IPC、原 SHM/DDS 未变；DDS SHA-256：
  `ca6961088346410f2e4770396caecb17ade8848974bfa6b427a31d7d307f53f7`。

上游补丁单独列出：

| 补丁 | 用途 | SHA-256 |
|---|---|---|
| `0010-orbslam3-build-export-shutdown.patch` | C++17/可移植编译；g2o 构建依赖；GBA 代际计数从 bool 修正为 int；加锁复制地图只读快照；关闭时等待建图/回环与所有 GBA 工作者；空 Atlas 退出修复 | `c730f1ed2a0fd2680814502cdd80066e669ebabf98a53426b46dbc30c9d870bd` |
| `0011-pangolin-fixed-width-integers.patch` | GCC 13 下显式包含标准整数定义 | `8480cbe0e5972bbb5066e1b0eda6bd6baa14c8ef11f3cae0878d8fb09d79dc99` |

首次构建遇到 Pangolin 缺标准整数头、网络 clone 中断、ORB 的 bool 自增不兼容
C++17；原始日志保留 `.cache/orbslam3/image-build-*.log`。最终库与项目 overlay
均编译成功。没有安装宿主 ROS、算法依赖或修改驱动/shell。

实际命令：

```bash
UW_IMAGE=underwater-stack:orbslam3-porth-v2 \
UW_DOCKERFILE=docker/Dockerfile.orbslam3 ./scripts/uw build
./scripts/uw test --local
UW_IMAGE=underwater-stack:orbslam3-porth-v2 ./scripts/uw test
./scripts/uw porth config/run.porth-orbslam3-short.yaml --arm
./scripts/uw porth config/run.porth-orbslam3.yaml --arm
```

本地 83 项测试：75 PASS / 8 SKIP（需要容器依赖）；容器 **83/83 PASS**，
没有删除旧 80 项断言。另有真实 native ORB 空 Atlas 生命周期组件回归：
不送图像、SIGINT、0.314 s 退出、exit 0；它是组件检查，不是仿真验收。

## 所有真实仿真尝试

运行目录均位于 `$HOME/.local/share/underwater-stack/runs/`。

| run_id | 范围 / 版本 | 结果 |
|---|---|---|
| `porth_orbslam3_short_v1--20260924T091316Z--9b0529ceeecf` | 6 m，未经 CLAHE 的灰度输入 | **FAIL**：438 帧未初始化，20 s 门槛触发停止；路线未开始。空地图关闭卡住，slam 最终 -9，失败原样保留 |
| `porth_orbslam3_short_v2--20260924T092048Z--9d6e9027a6e7` | 6 m，CLAHE 与空地图关闭修复 | **PASS**：745/745 帧跟踪，0 lost/drop，61 KF / 3195 点，12 个进程退出均 0。此轮 RViz 仍有独立 OpenVINS/ORB gauge 显示错位，后续已修正 |
| `porth_orbslam3_short_v2--20260924T092526Z--ec08fb5b6d5b` | 6 m，最终 ORB 机器人显示 | **PASS**：746/746 帧，0 lost/drop，64 KF / 3131 点，19.69 Hz，p99 50 ms；12 个进程退出均 0 |
| `porth_orbslam3_full_v2--20260924T092836Z--3d3507eb1a61` | v14 全洞规定路线、最终冻结代码 | **采集 PASS**：60949/60949 帧，0 lost/drop，最终 1576 KF / 77450 点，12 个进程退出均 0；Atlas 原生加载成功，严格数值一致性 FAIL |

不是三次同版独立重复。首次失败后仅在下一版本修复，未回写失败数据，未降低
原生双目初始化特征门槛，未提高灯光或修改水体。保存图像样本上的 OpenCV ORB
诊断显示原灰度只有约 34–41 个特征，CLAHE3 约 1368–1393 个；该诊断使用 JPEG
样本与 OpenCV 提取器，不能冒充原生 ORB-SLAM3 的逐帧特征统计。

第二轮短程独立评价：原始在线位姿位置 RMSE **0.035395 m**，最终优化关键帧
RMSE 0.035720 m；p99 延迟 0.05 s，p99 TrackStereo 耗时 0.01749 s。
只用首次真值重叠样本的 yaw/平移配准，不做尺度或全轨迹拟合。
原生 Atlas 重读 **PASS**：61/61 KF，最大时间差 1.42e-14 s，最大姿态/位置
分量差 5e-8，源 Atlas SHA 不变。
最终显示版本的第三轮短程也独立评价：在线 RMSE 0.036719 m，最终关键帧
RMSE 0.036940 m；Atlas 重读 64/64 KF，误差上限同上，源文件不变。
两个短程均在本次运行结束后只读评价。短程精度不代表全洞精度。

## 全程在线实际结果

2026-09-24 UTC 09:28:36 至 10:20:17，含启动/退出墙钟 **3101.736 s（51 分 42 秒）**。
全部四次真实仿真为 **3 PASS / 1 FAIL / 0 NOT_RUN**（上表）；全程只有一次，
没有宣称三次重复或跨场景泛化。冻结的 15 项采集断言全部通过。

| 指标 | 全程实际值 |
|---|---|
| 规定路线长度 / 最终沿线进度 | 570.882878 / 570.737777 m；剩余 0.1451 m，满足既有终点容差 |
| 独立真值实际累计行程 | 566.998473 m |
| 原生处理 / 跟踪 / lost / adapter drop | 60949 / 60949 / 0 / 0 |
| 采集阶段处理率 / 跟踪比例 | 19.7083 Hz / 100% |
| 延迟 p50 / p95 / p99 / 最大 | 40 / 50 / 80 / 140 ms |
| TrackStereo 与预处理耗时 p50 / p99 / 最大 | 16.45 / 24.16 / 38.32 ms |
| 原始在线位姿 RMSE / 最大 / 末端误差 | 0.458226 / 1.207837 / 0.014321 m |
| 最终优化关键帧 RMSE / 最大 / 末端误差 | 0.533072 / 1.201398 / 0.004619 m |
| 最终 Atlas / 关键帧 / 稀疏点 | 1 / 1576 / 77450 |
| 接受的回环边 | 0；本轮不宣称验证了回环修正或丢失重定位 |
| 必要进程 / 容器退出 | 12/12 为 0；容器 0，launch 0 |
| MCAP | 2826091 条消息，metadata 正常完成 |

精度评价使用全部有效真值重叠样本：在线 60690 个（1.11–3080.48 s），最终关键帧
1553 个（1.11–3079.26 s）。其余原生帧/关键帧发生在 benchmark 停止记录真值后、
仿真退出前，不伪造真值补齐。两套采样分布不同，因此 RMSE 的差别不能简单解释为
优化变差。只做初始 yaw/平移配准，无尺度或全轨迹拟合。延迟统计覆盖全部原生帧。
`drop=0` 是接收器计数，不是所有负载下 DDS 永不丢包的保证。

采集终止时 probe 看见 1564 KF / 78281 点；之后原生后台处理和冗余剔除继续，
最终关闭保存为 1576 / 77450，两个时间点分别保留。最后一份定时
`survey-progress.json` 仍是运动中快照；实际最终状态由 `control-status.json`
的 DISARMED、native_neutral 断言和退出记录证明，不改写旧快照伪造终态。

### Atlas 重读与严格一致性失败

使用同一冻结镜像/实际原生二进制，原运行目录只读挂载，完整 Atlas 成功加载并
导出 1576/1576 KF，native process exit 0。原 Atlas SHA-256 在重读前后不变：
`b21ce0dcbea5cf45dba3d7902a91e8f377435d41cb489e54e581f2c7dea33a53`。

`atlas-reload.json` 中原先冻结的比较要求时间差 <1e-5 s、所有 pose 分量差 <1e-6：
时间最大差 2.10e-8 s、四元数分量差 1.25e-7，但平移分量最大差
**6.099e-5 m**，三维位置差最大 **6.513e-5 m**，位置差 RMSE 3.512e-6 m。
因此该检查保持 **FAIL**，不能写“全部验收通过”。

读取锁定源码发现 `SerializationUtils.h::serializeSophusSE3` 用单精度四元数/
平移重建 Sophus，`KeyFrame::PostLoad` 再调用 `SetPose` 计算逆变换。
此差异与单精度归一化/逆变换舍入量级相符；没有保存序列化前的内部 Tcw 原值，
故精确因果归因仍为 NOT_VERIFIED。没有为改判而调整阈值、修改上游或重写文件。
`reload-numerical-diagnostic.json` 保留每项误差及最差样本。

辅助 OpenVINS 本轮位置 RMSE 16.988 m，末端误差 21.139 m，日志含重复 IMU dt
剔除警告。它不输入 ORB 或本轮控制，不能冒称通过长程精度验收，亦不能将
TRACKING 状态本身当作准确性证明。本轮未调参或修复这一独立估计器。

## 冻结判据与输出解释

`test/orbslam3-acceptance.yaml` 在全程前冻结：初始化后跟踪比例 ≥95%，
p99 在线处理延迟 ≤0.5 s，平均处理 ≥15 Hz，只有一个且不切换 map，
至少 3 KF / 1000 稀疏地标；沿用采集路径/姿态/传感器/末端中和检查。
跟踪丢失期间发零速度闭环目标，超过 5 s 则结束并锁存故障。普通启动仍
DISARMED；本轮 `--arm` 是明确授权，旧消息不能自动恢复。

20 Hz 双目按原采样纳秒严格配对，每侧最多缓存 3 帧，过旧图像丢弃，
不更新输入时间戳伪装新鲜。RViz 的 BlueROV2 真实外观直接跟随 ORB
`map -> orb_body`，显示用 URDF 不改变实际物理模型。初始机体 FLU 是地图
坐标约定；纯双目不能测量重力或全球 ENU 方位。OpenVINS 的独立 odom 树
不与 ORB map 人为连接。

- `orb-frames.jsonl`：原始实时处理位姿、采样戳、跟踪状态、延迟和耗时。
- `orb-keyframes-body.jsonl` / `orb-sparse-map.ply`：完成原生后台优化后的地图。
- `orb-optimized-camera-tum.txt`：原生最终轨迹，光学相机坐标约定。
- `orb-atlas.osa`：原生序列化地图，需单独重读证明，不能只看文件存在。
- `slam-events.jsonl`：实际 ORB 状态；`loop_edges` 为接受的无向回环边数量，
  不等于回环事件数。`big_changes` 不单独解释为回环数量。
- `orb-subscription-inspection.json`：运行图实际订阅，检查无 truth/odom/IMU。
- `m3-metrics.json` / `slam-metrics.json`：采集判定；manifest/进程退出独立记录。
  `auxiliary_openvins` 指标不能当作 ORB 精度。
- `orb-camera-samples/`：约 1 Hz 实际相机 JPEG 样本；全 20 Hz 图像未录制。
  本轮使用 state MCAP，实际传感器仍持续发布，RViz 两幅图像持续显示。

## 证据与边界

接入总目录：`$HOME/.local/share/underwater-stack/reports/orbslam3-integration-20260924T084656Z/`。
短程评价：`reports/orb-evaluation-porth_orbslam3_short_v2--20260924T092048Z--9d6e9027a6e7/`，
内含 `metrics.json`、`online-tracking.png`、`sparse-map.png/html`、`atlas-reload.json`。
本轮真实窗口截图在各 run 的 `figures/`；没有合成可视证据。

全程评价位于 `reports/orb-evaluation-porth_orbslam3_full_v2--20260924T092836Z--3d3507eb1a61/`：

- `online-tracking.png`：完整原始在线/最终关键帧轨迹、位置误差、延迟和跟踪状态。
- `sparse-map.html`：离线可交互原生稀疏地图；无网络资源、无已知洞穴网格输入。
- `sparse-map-top.png`：等比例平面图；`sparse-map.png` 为三维图。
- `metrics.json`、`atlas-reload.json`、`reload-numerical-diagnostic.json`：原始判定及诊断。

接入报告的 `full-run-provenance-audit.json` 核对 191 个冻结文件、运行源码归档、
实际二进制、镜像 ID、DDS、512 MiB 私有 IPC 均匹配。`final-run-summary.json`
记录四轮共 **3747073670 字节（3.75 GB）**；全程 run 为 3661803200 字节。
接入报告另保存构建/测试/失败日志，所有历史证据未删除。容器/网络无本轮
`uw-run-*` 残留，其他项目容器仍运行。宿主 detached CLI 的退出码未捕获，
没有把它伪称为 0；独立 Docker wait 捕获实际容器退出码 0。

```text
ONLINE_STEREO_ACQUISITION = PASS
NATIVE_ATLAS_LOAD = PASS
STRICT_ATLAS_POSE_EQUIVALENCE = FAIL
DENSE_CAVE_RECONSTRUCTION = NOT_VERIFIED
LOOP_CORRECTION_OR_RELOCALIZATION = NOT_VERIFIED
CONTROL_STATE_SOURCE = PRIVILEGED_DEBUG
ORB_CONTROL_FEEDBACK = NO
ORB_INERTIAL_MODE = NO
REAL_HARDWARE_TESTED = NO
```

本轮只验证显式 Porth profile 的在线纯双目 SLAM。没有稠密补全、完整视觉
表面覆盖结论、ORB 双目惯性、ORB 控制反馈、自主探索/避障或实机结果。
现有控制安全链路沿用既有实现，本轮没有重跑全套 M0–M3 / ORB 故障注入矩阵。
长程位姿精度、回环和重定位要看本轮数据，不能由 TRACKING 状态推导正确。

[运行指南](runbook-orbslam3.md) · [接入计划](orbslam3-plan.md) · [文件范围](orbslam3-file-changes.md) · [主页](00-home.md)
