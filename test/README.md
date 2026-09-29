# Verification layers

`scripts/uw test --local` runs pure contract tests with existing Python + PyYAML.
`scripts/uw test` runs the same suite in the project image.

`scripts/uw run` invokes the ROS M0 probe: advancing single clock, recent correctly
framed stereo/IMU/odometry, stereo projection fields, TF connectivity, no motor
endpoints, and a finite continuous observation window. Evidence stays with the run.

Image build, NVIDIA/OpenGL, rendered views, clean shutdown/bag flush and two fresh
launches were verified on 2026-09-21; see docs/runtime-validation-2026-09-21.md.
Physical camera calibration and sensor sample synchrony remain unverified.
Integration results must not be inferred from this unit suite.

M1 adds `test_m1.py` contracts and the real-run manifest `m1-acceptance.yaml`.
`m1-freeze.json` freezes runtime source/parameters/image; document-only changes are excluded.
Use `./scripts/uw acceptance --phase formal --cases mapping authority velocity extra fault m0 m0 --continue-on-failure`.
The original 41 tests remain; only the package membership expectations now include the three implemented M1 packages.
