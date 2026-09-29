# Navigation：局部航点跟踪

`navigation/`（`uw_navigation`）提供 20 Hz 比例位置/偏航跟踪器。输入是任务
授权的航点和 `state/odometry`；将 odom 位置误差通过完整姿态旋转到机体 FLU，
输出 `[vx,vy,vz,yaw_rate]`，经既有 Guard 和速度/姿态控制器驱动推进器。
水平速度范数上限 0.12 m/s、竖直 0.06 m/s、偏航率 0.12 rad/s；增益和到点
容差见 `navigation/config/defaults.yaml`。到点必须同时满足位置、偏航、线/角
速度条件并持续 1 秒，不能只在穿过目标时宣称成功。

几何路径是连接用户航点的直线段。当前只在已知空闲、带纹理的有限诊断场景
验证；没有避障、地图、全局规划、全局北向或场景泛化能力。

任务起点相对坐标由 Tasks 在接单时从真实估计固定下来，再数值转换成 odom
目标；Navigation 不通过修改 frame 字符串伪装转换。`navigation/path` 是几何
航点序列，不是带动力学约束的时间轨迹。

每条输出保留任务心跳的单调时钟签发时间，且有效期不超过整个任务的绝对
期限。任务死亡、目标过期、状态过期或 Guard 撤权时停止输出；不持续刷新
缓存目标的授权。不读取真值，不发送推进器数组。

相关：[Tasks](module-tasks.md)、[接口](interfaces.md)、[M3 决策](adr-0004-estimated-navigation-and-missions.md)。
