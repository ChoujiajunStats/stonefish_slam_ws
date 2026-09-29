# Project instructions

- Read `docs/00-home.md` and `docs/roadmap.md` before changing implementation.
- The original `underwater-stack-architecture.md` is the supplied design; preserve it.
- Implement the current milestone. Do not create placeholder algorithm packages.
- Keep ROS, Stonefish, colcon and algorithm dependencies inside the container.
- Do not modify host drivers, global Python packages or shell configuration.
- Own ROS packages live at the repository root; use explicit colcon package paths.
- Do not start ArduSub or add actuator subscriptions in M0. No automatic arming.
- Public frames use FLU/ENU. Convert values and covariance, not just frame names.
- Upstream changes must be hashed patches against locked commits.
- Test pure contracts with `./scripts/uw test --local`; ROS checks require the image.
- Do not report static/unit checks as successful simulation acceptance.
- Use one simulator and one `/clock` authority per isolated DDS domain.
- Every run gets a new output directory. Never overwrite an earlier run.
