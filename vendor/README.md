# Locked upstream dependencies

`source-lock.yaml` fixes complete commits, base image digest and patch SHA-256.
`scripts/fetch_upstream.py` fetches into the image, verifies HEAD and hashes, then
applies patches with `git apply --check`. Existing checkout directories are refused.

`0001-simulation-clock-and-node-ownership.patch` is against stonefish_ros2 v1.3:

- Publishes `/clock` from completed physics-step time, stamps observations using it.
- Uses a steady clock for simulator pacing, independent of ROS `/clock`.
- Shares step time atomically with rendering callbacks; one simulator per process.
- Fails when scenario parsing fails.
- Uses a borrowed node pointer instead of creating a second owning shared_ptr.

`0002-stonefish-fixed-width-integers.patch` explicitly includes `<cstdint>` in
Stonefish's common header. The first Ubuntu 24.04 build failed because v1.3's
`Sample.h` used `uint64_t` without including its defining standard header.

Patch application is testable independently of compilation. Compilation, rendering,
clock pacing and shutdown remain runtime acceptance requirements.
See [sources and license scope](../docs/sources.md).

M1 retains both patches above and adds:

- `0003-pre-actuator-safety-hook.patch`: a default no-op
  `SimulationManager::SimulationStepStarted` hook before native actuator updates.
- `0004-terminal-command-lease.patch`: optional scenario terminal, independent
  executor and steady watchdog, checked again before applying native setpoints;
  receiver/RPM/thrust feedback and explicitly enabled clock diagnostic fixture.
  No dependency on project controller/guard interfaces is introduced upstream.

Both are authored in this repository against the same locked commits. File hashes
and patch ordering are authoritative in `source-lock.yaml`; original model dynamics
are unchanged. The default M1 image derives from the verified local M0 image and
replays the locked patch set inside the new image. The M0 image tag is not written.
See [decision and regression evidence](../docs/adr-0002-control-authority-and-watchdog.md).

- `0005-rviz-idempotent-image-unsubscribe.patch`: pins RViz **14.1.23** at
  `feb01669f1297df2af755ce9cd2ed18083e7a8b2`, matching the installed version,
  and clears a disconnected image-filter callback before destroying its owner.
  Repeated dock hiding / destruction otherwise dereferences freed filter memory.
  The patch follows RViz's BSD-3-Clause license. The ASan lifecycle regression
  fails before this patch and passes after it; real GUI shutdown is separately
  tested. No DDS transport settings or middleware packages are changed.
  See [RViz diagnosis](../docs/m1-rviz-lifecycle-fix.md).

- `0006-rviz-release-view-manager.patch`: releases the same-version RViz
  ViewManager before its scene and ROS node are torn down. Its view controller
  owns a reset-time ROS service; leaking it delays participant cleanup until
  Fast DDS static destruction. The real-frame QPointer regression records an
  unreleased manager and exit 139 before the patch, released manager and exit 0
  after it. DDS binary and XML are unchanged.

Optional whole-cave survey adds `0009-survey-optical-lights.patch` in
`source-lock.survey.yaml`: skip wrench-free LIGHT actuators while preserving the
eight verified motor channels and rejecting other actuator types. Applied only
in the separately tagged survey image. See [optical audit](../docs/porth-optics.md).
