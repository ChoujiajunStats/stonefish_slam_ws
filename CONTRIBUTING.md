# 协作约定

从 main 创建任务分支，通过 Pull Request 合并，不直接重写 main。
先读 [架构边界](docs/repository-structure.md)、[部署指南](docs/deployment.md) 和 `AGENTS.md`。
更改接口需同步消息、单位/frame/时间/QoS 契约及消费者；保持默认 DISARMED。

PR 说明具体问题、结果、验证命令、镜像 ID、run_id 和剩余限制。
单元测试、编译成功和真实仿真验收分别报告。改算法/配置后不能沿用旧版本最好成绩。
不提交大型实验数据、密钥、个人路径设置或生成配置；不覆盖历史运行。

```bash
./scripts/uw build --profile orbslam3
./scripts/uw test --profile orbslam3
```

CI 轻量容器检查不需要 GPU。涉及图形、控制、末端 watchdog、时间戳、观测或
SLAM 的变更还需真实仿真回归，并在 docs 保存结果索引。每轮展示 RViz 和 Stonefish；
每个 run 使用新目录，禁止伪造反馈或放宽失败后的门槛。

上游变更使用固定提交上的最小 patch，更新 hash、理由和回归；不直接改镜像内源码
当作可复用修复。新增包必须有真实职责，不创建占位算法包。

许可现状见 [NOTICE](NOTICE.md)。原创代码发行许可尚待所有者决定，公开可见
不代表已采用开源许可证。只提交自己有权提供的代码与资料。
