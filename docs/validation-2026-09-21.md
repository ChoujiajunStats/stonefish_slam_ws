# 首次实现验证：2026-09-21

这是 Docker 授权前的历史记录。其后已完成构建和两轮真实运行，
当前状态见 [运行验收记录](runtime-validation-2026-09-21.md)。

## 已完成的检查

| 检查 | 实际结果 | 能证明的范围 |
|---|---|---|
| `./scripts/uw test --local` | 41 项通过 | 纯 Python 契约、配置、数学、资产、运行结果和仓库边界 |
| `./scripts/uw validate --local` | 通过 | 示例清单符合 M0 能力，控制器禁用、真值调试显式标记 |
| `./scripts/uw compose-config` | 通过 | Compose 语法/变量解析，不验证 daemon/GPU |
| Python AST 与 Bash 语法检查 | 通过 | 语法正确，不验证 ROS 导入或 C++ 编译 |
| `git apply --check` 对锁定 ROS wrapper 源文件 | 通过 | 补丁可应用，不验证编译和行为 |
| 下载固定提交的 7 个引用资产并派生场景 | 通过 | 实际模型输入可读、哈希记录、单机器人和传感器裁剪正确 |
| 直接调用运行器的无镜像预检 | 如预期退出 1，记录 NOT_STARTED 和缺少镜像证据原因 | 失败路径会落盘，不伪造运行成功 |

实际派生场景 SHA-256：
`1666cb1e36a9e1dbaf58541051eedeaee7ad94ac5c24b41a0d8728f7bcc5c3d7`。
资产清单保存在仓库 `resources/bluerov2-assets.yaml`；临时下载仅用于审计，
未将第三方源码/网格加入本仓库。

Git 仓库已初始化为 `main`，尚无提交；运行记录在 SHA 不存在时会明确写 null，
并以源码文件哈希记录实际内容，不虚构提交 ID。

## 已尝试但未完成

`./scripts/uw build` 在连接 Docker daemon 时退出 1：

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

未开始下载/构建项目镜像，未执行 colcon，未启动 Stonefish/RViz，未生成仿真 bag。
`nvidia-smi` 能识别 RTX 5090，X11 cookie 和 DISPLAY 存在；这不证明容器图形链路可用。
没有修改宿主组权限、驱动、全局 shell 或 Python 环境。

## 继续条件

当前用户的 `docker info` 正常返回后，按 [运行指南](runbook.md) 执行
`build → test → run`。其后才可评价 C++/ROS 构建、OpenGL、实际传感器、TF、
clock、bag 正常关闭与重复运行清理。M0 阶段门当前仍为 **未通过**。
