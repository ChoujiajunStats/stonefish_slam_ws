# Asset provenance

M0 uses only BlueROV2 meshes and texture referenced by the locked upstream robot.
No tank, seabed, cave or other robot asset is instantiated.
The scene generator rejects missing assets and scenario hash mismatches, records
each referenced asset hash in the run's `empty_water.assets.json`, compares it to
the image build's `asset-lock.json`, and records the generated scene hash.
The robot geometry remains in the upstream image underlay.

Model units: metres, source native FRD; shared public extrinsics are converted to FLU.
RViz uses a transparent schematic box, not these physics meshes.
Per-asset license verification remains open; see [sources](../docs/sources.md).
