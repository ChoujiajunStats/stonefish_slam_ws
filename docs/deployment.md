# 部署与复用

入口是 `scripts/uw`，可从任意工作目录以绝对路径调用。
宿主不安装 ROS、算法库或全局 Python 包；普通部署命令仅需要 Python 标准库。
X11/XWayland 和 GPU 访问由 doctor 检查，不自动改宿主驱动、Docker 权限或 shell。

## 构建 profile

```bash
./scripts/uw doctor
./scripts/uw compose-config
UW_BUILD_JOBS=8 ./scripts/uw build --profile orbslam3
./scripts/uw test --profile orbslam3
```

| profile | 累积内容 |
|---|---|
| core | Stonefish、M0 观察、M1 控制 |
| vio | core + OpenVINS 双目/IMU |
| navigation | vio + 局部导航/任务 |
| rtabmap | navigation + RTAB-Map |
| survey | rtabmap + 原生随车灯/洞穴规定路线 |
| orbslam3 | survey + ORB-SLAM3 在线双目 |

默认 profile 为 orbslam3；也可设置 `UW_PROFILE`。镜像名为 `stonefish-slam:<profile>`，
`UW_IMAGE` 可指定自定义标签，但内容必须具备所选 profile 能力。overlay 按工作区路径、
UID 和 profile 隔离；镜像 ID 变化时清理该专用 volume 内的构建缓存，避免复用不兼容二进制。完整构建从锁定的 ROS 基础镜像开始，不要求历史 `underwater-stack:*` 镜像。
APT 依赖有实际清单，尚不保证逐位可复现。源码提交与 vendor 补丁哈希保持原锁。

## 数据与外部资产

默认 `UW_DATA_ROOT=$HOME/.local/share/stonefish-slam`，不能是 HOME、根目录或仓库内。
数据目录包含 `assets/`、`plans/`、`runs/`；Git 不包含资产包、bag、Atlas、运行会话或凭据。
每次运行目录唯一。不要把其他工程的数据目录混入当前活动会话。

在有已准备资产的机器导出：

```bash
./scripts/uw assets export --source-data-root /path/to/existing-data --bundle /path/to/porth-bundle.tar.gz
```

由资产持有人决定分发权限，通过约定渠道单独交付。接收者导入：

```bash
./scripts/uw assets import --bundle /path/to/porth-bundle.tar.gz
./scripts/uw assets verify
```

同机迁移也可直接使用 `assets import --source-data-root /path/to/existing-data`。
导入仅接受 [清单](../resources/porth-bundle.lock.json) 中的资产与 v14 路线，校验大小与 SHA；
拒绝目录穿越、符号链接、重复成员、损坏内容及覆盖冲突，不导入历史 runs。
资产内保留的原始来源路径是历史 provenance，不是运行依赖。

## 启动与停止

```bash
# M0：60 秒观察，RViz + Stonefish + debug bag，无控制入口
./scripts/uw run config/run.empty_water.example.yaml
# ORB 短程：未加 --arm 时保持 DISARMED
./scripts/uw porth config/run.porth-orbslam3-short.yaml --arm
# 完整规定路线：约 571 m，先验证短程
./scripts/uw porth config/run.porth-orbslam3.yaml --arm
# 另一个终端查询/中和本工作区的活动仿真实例
./scripts/uw status
./scripts/uw disarm
```

`Ctrl+C` 触发有界退出；末端 watchdog 独立处理外部进程异常失联。
只操作活动 manifest 对应容器，不使用全局 pkill 或 docker prune。
启动前检查 `df -h`、`nvidia-smi` 和 `docker ps`。各实验预算仍保留；完整图像录制很大，
长程默认使用精简 state profile。M0 debug 录制约 3.3 GB/分钟。

ORB 只接收双目图像，路径跟踪仍是真值辅助；`map`、里程计与评价真值不能混用。
全程 Atlas 加载与严格数值一致性是两个判定，历史严格一致性 FAIL 保留。

## 验证与故障处理

`./scripts/uw test` 在容器内执行契约/数值测试，不启动仿真。
`./scripts/uw test --local` 仅使用宿主已存在的 PyYAML；缺少 NumPy/OpenCV 时跳过相关测试，
不自动安装。CI 使用轻量容器执行全部契约；GPU/真实仿真结果单独记录。

显示失败先运行 doctor，确认 `DISPLAY` 和 xauth cookie。镜像标签不存在先 build 对应 profile。
如果锁定 APT 版本或上游源码不可下载，应保留错误并修复来源锁，不改成 latest。
完整构建内存不足可降低 `UW_BUILD_JOBS`。不要改动已验收 DDS 私有 IPC/SHM 布局。

旧正式 campaign 入口仍在，但旧冻结清单已归档，不能用它认定新代码通过。
新正式评估应先建立当前源码/镜像的 freeze，再完整重跑受影响病例；本次部署短程
不替代 M1/M2/M3 全套验收。详见 [本次验证](validation-2026-09-29-workspace.md)。
