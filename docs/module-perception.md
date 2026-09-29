# Perception：M2 双目与 IMU

实现包 `perception/uw_perception`；运行验证状态见 [M2 验收报告](validation-2026-09-23-m2.md)。

输入为 M2 原生双目 RGB8 与具体物理语义的 IMU；不依赖真值位姿。输出为
`sensors/stereo/{left,right}/{image_raw,camera_info}` 与 `sensors/imu`。
所有时间戳继承采样时刻。图像保持 640×480、75° 水平视场和 0.145 m 基线。
IMU 为 100 Hz FLU 比力/角速度，无姿态测量。原 M0/M1 使用各自原适配器。

`ExactPairs` 按采样纳秒严格配对、限制待匹配缓存，拒绝旧帧；不足一对时不
合成图像。每对最多 20 Hz 发布。重复/丢弃/节流数在 `perception/status`。
校验尺寸、编码、数据长度、原始 frame、单调时间、有限 IMU 数值以及 -1 姿态
标记。时钟回跳锁存，不通过重新打时间戳恢复。

诊断运行才接受有 run/secret/单调期限的传感器丢弃指令；不会改变图像内容或
给估计器注入真值。噪声参数是研究用模拟设置，没有真实传感器标定含义。
详见 [传感器与估计发布权决定](adr-0003-sensor-time-and-estimator-authority.md)。
