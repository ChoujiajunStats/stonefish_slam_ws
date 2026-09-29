# Porth 纹理、灯光与青色水体

2026-09-24 核验。Porth 的 `albedo.png` 为 4096×4096，SHA-256
`52457047ad182b19c07ac0e58ee0d0757a2573dd2e24b27ce980940660c8f720`。
视觉 OBJ 含 1,324,157 个 UV，面显式引用 UV。实际生成场景的 `porth_rock`
材质引用该 PNG，Stonefish 日志确认加载成功。原图没有被替换为纯色。
RViz 的 SLAM 点云为观测重建数据，与原始带纹理网格是不同的显示对象。

## OceanSim 参考与本项目取舍

审计 OceanSim commit `49c35d6f05c703144b3731a5c10a8dffbd702f92`：

- [示例](https://github.com/umfieldrobotics/OceanSim/blob/49c35d6f05c703144b3731a5c10a8dffbd702f92/standalone/UWCam_sdg_seaclear.py)
  使用 dome 环境光，其默认强度为 1500。
- [场景工具](https://github.com/umfieldrobotics/OceanSim/blob/49c35d6f05c703144b3731a5c10a8dffbd702f92/isaacsim/oceansim/utils/UWCam_sdg_utils.py)
  将灯光与自动曝光等渲染设置分开。
- [水下相机](https://github.com/umfieldrobotics/OceanSim/blob/49c35d6f05c703144b3731a5c10a8dffbd702f92/isaacsim/oceansim/sensors/UW_Camera.py)
  使用按颜色通道配置的水下衰减与散射参数。

上述公开实现不能证明其所有外部 USD 场景使用相同灯光，也不能把 Isaac Sim
强度数值直接移植为 Stonefish 的光通量。未运行或迁移 OceanSim。
本项目借鉴将场景照明与介质成像分开配置的方式，使用锁定 Stonefish 原生渲染。

## 原生实现核验

Stonefish commit `6d285a955d19c9ecef3defd3f0605907f4594dbb`：
`ScenarioParser.cpp` 读取 water/jerlov 与灯的 illuminance、cone_angle；
`OpenGLOcean.cpp` 将 Jerlov 0–1 插值到 64 项 RGB 吸收/散射表。
不是单一屏幕颜色叠加，也不是线性的“浑浊度百分比”。
`OpenGLSpotLight.cpp` 实际将 XML illuminance 参数按光通量除以圆锥立体角；
因此配置和证据称 `native_flux_each`，不把它标成现场照度测量。

当前试验：两盏随车前向灯，每盏原生参数 20000，圆锥全角 110°、5000 K；
原生 FRD 安装点 `(0.20, ±0.23, 0.05)` m，沿 +X，向两侧各偏 0.05 rad。
原相机安装位置、基线、内参、采样与 IMU 不变。移除沿路固定诊断灯。
这些是仿真配置，未按真实 BlueROV 灯具进行测光标定。

Jerlov 参数 0.22（配置键为 `survey_water_jerlov`）提供青色散射雾感。
注意锁定版本 `ApplyBlur()` 的独立 blur shader 调用处于注释块，不能宣称
该模糊器已经启用；当前没有额外图像后处理。近处岩石纹理仍可见，距离增加时
吸收和散射压低对比度。它改变送入 OpenVINS/RTAB-Map 的实际图像。

## 最小上游补丁

[补丁 0009](../vendor/patches/0009-survey-optical-lights.patch) 由本项目编写，
叠加在固定 `stonefish_ros2` commit `3fc1fc7e9f959f988cd3e9c71fcf7944163abd0d`
与既有补丁之后。只在 UWTerminal 枚举电机时跳过无推力 `LIGHT`，仍要求
八个推进器，其他类型仍抛异常；时效、授权、故障锁存和中和逻辑不变。
SHA-256 与父镜像见 [独立 survey 锁](../vendor/source-lock.survey.yaml)。
不改变水动力，不增加绕过 Guard 的推进器输入。

运行命令、持久化参数和可视窗口说明见 [运行指南](runbook-porth-survey.md)。
单元测试不能替代末端保护与真实运行证据，实际结果在全洞运行报告中记录。
