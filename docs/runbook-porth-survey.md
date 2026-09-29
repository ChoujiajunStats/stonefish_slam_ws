> 新工作区部署请先阅读 [deployment.md](deployment.md)。本页保留历史镜像名与验收上下文；新镜像使用 `stonefish-slam:<profile>`。

# Porth 全范围 SLAM 采集

这是已知路线的数据采集模式，没有自主避障。控制反馈明确标记
`PRIVILEGED_DEBUG`，继续通过 Guard、速度控制器、分配和 Stonefish 八推进器
运动；OpenVINS 和 RTAB-Map 不订阅真值或洞穴网格。

## 运行

```bash
# 默认保持 DISARMED；长时手动观察仍受配置时限约束
./scripts/uw porth config/run.porth-survey.yaml

# 显式授权执行已筛选路线
./scripts/uw porth config/run.porth-survey.yaml --arm

# 在另一终端查询和停止
./scripts/uw m3-status
./scripts/uw disarm
```

路线文件为 `$UW_DATA_ROOT/plans/porth-survey-v14/plan.json`，配置绑定其 SHA-256。
默认数据根目录为 `$HOME/.local/share/underwater-stack`。约 571 m 的路线包含
主通道往返和三条侧支路，0.2 m/s 限速；加转弯和垂向运动需要更长时间。
每次新进程、新 run，不自动恢复旧授权。普通启动无自动 ARM。
显式 ARM 后先零速度闭环稳定，最多等待 20 秒让 OpenVINS 用真实双目/IMU
完成初始化，再开始路径采集；超时锁存故障。该启动方式只用于真值控制采集。
启动时 RViz 和 Stonefish 自动调至前台并排，窗口匹配同时检查当前运行 PID
和启动前窗口集合，不操作其他项目窗口。Stonefish 保持原 960×720 渲染尺寸。

新场景尺度为 1.8，仍为实验尺度，不是地质测量标定；旧 Porth 短演示的
1.5 倍尺度和原始导入资产未修改。两盏 110° 前向灯随机器人运动，原生 Jerlov 水体参数为 0.22；没有更改
机器人尺度、质量、浮力、阻尼、步长或相机采样。RViz 默认跟随机器人，
可切换视角观察逐渐增长的地图。显示点云用 0.20 m 栅格限制传输负载，
离线从原始双目数据库导出 0.06 m 点云。

长程版本 v4 将 RTAB-Map 在线工作记忆限制为 600 个节点，内存管理时间目标
为 250 ms；历史传感器关键帧仍保存在数据库，可被再次取回。在线显示主要
对应当前工作图，坐标修正和工作图切换可能使显示变化。完整地图在采集后对
所有保留节点执行全局优化并导出；不把在线工作图的大小当作已采集范围。
这一调整用于避免字典索引重建长暂停，原 5 秒 SLAM 新鲜度保护保持不变。

采用原单容器私有 IPC/DDS，不启动第二个仿真或第二个 `/clock`。
状态 MCAP 不重复保存整段左右原图，原始关键帧双目图像保存在 RTAB-Map DB。
新任务数据预算为 25 GB；旧证据不删除。不要切换到长时间 debug 图像录制。

## 水体外观

```bash
# 以新运行保存光学参数；0.22 是当前青色雾感试验值
./scripts/uw porth config/run.porth-survey.yaml --water-jerlov 0.22 --arm
```

也可修改配置中的 `survey_water_jerlov`。原生范围 0–1，数值并非线性浑浊度，
0.05 较清澈，0.22 增加散射；更大值需要重新验证跟踪能力。未做实水标定。
原始 Porth 贴图和 UV 保留，相机图像不叠加人工青色滤镜。Stonefish 左侧
OCEAN 的 Jerlov 滑块可临时预览，但不会保存到 YAML；正式采集请保持冻结值。
锁定版本的独立 blur shader 处于注释代码中，本模式不宣称启用了该模糊器。
原生光学吸收、散射与灯光会共同改变相机和 SLAM 输入。

新增镜像 `underwater-stack:m3-porth-survey-v1`，旧 Porth/M0–M3 镜像未覆盖。
只给原末端接收器增加对无推力 LIGHT 类型的跳过，仍严格要求八个推进器，
其他意外执行器仍拒绝。见 [光学审计](porth-optics.md)。

## 保存地图和检查覆盖

运行结束后，使用实际 run_id：

```bash
UW_IMAGE=underwater-stack:m3-porth-survey-v1 ./scripts/uw slam-export <run_id>
UW_IMAGE=underwater-stack:m3-porth-survey-v1 ./scripts/uw survey-coverage <run_id> <上一条输出的 slam-export-目录名>
```

导出会复制数据库到新的 `reports/slam-export-*`，重读并导出 PLY/优化轨迹，
不修改运行中的原始数据库。覆盖评价按完整 `visual.obj` 面积均匀抽样 30 万点，
报告距测量点云 0.15/0.30/0.50 m 以内的表面比例。只做初始位姿规范对齐，
不使用真值修正、ICP 或非刚性拼接。原始模型只作为评价参照，不加入输出点云。

对启用工作记忆限制的记录，导出器自动使用 `rtabmap-export --opt 0`，重新
优化完整历史图；原无限工作记忆记录继续采用保存的优化位姿。命令和选择
写入新报告，不覆盖旧运行。后处理完成不代表运行中的全局地图始终实时更新。

`survey-progress.json` 是实时路线进度；`m3-metrics.json`/`slam-metrics.json`
是采集判定；`coverage.json` 才是重建覆盖数据。完成路线不等于完成整个表面，
稀疏、未观察和漂移造成的空缺必须保留。点云也不等于完整封闭三角网格。
当前通用 `m3-status` 的 `current_mission` 字段在此模式下可能显示
`STALE_OR_STOPPED`，因为采集器没有启动 M3 任务 Action；结合
`scope=PORTH_SURVEY`、`survey_progress` 与 Guard 状态读取。最终是否完成
以采集 metrics 为准，最后一条周期性 progress 可能仍是到点前的状态。

若 Guard、相机、估计器、SLAM 更新或走廊跟随异常，采集器撤权并保留失败。
修复原因后用新运行重试，不能仅凭消息恢复自动 ARM。

## 回退

原局部演示仍为 `./scripts/uw porth --arm`；M0 仍沿用
[原运行指南](runbook.md)，不会因为新增采集模式获得控制入口。

路线推导见 [实施计划](porth-survey-plan.md)，结果另在实际运行报告中记录。
