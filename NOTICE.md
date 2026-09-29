# Source and license status

Repository owner: Jiajun Zhou <ChoujiajunStats@126.com>.

Existing project-owned code has not been assigned a distribution license.
Its `LicenseRef-Not-Yet-Licensed` metadata is retained; this integration does not
silently apply MIT, Apache or GPL to all files. Files already carrying a license
notice retain that notice. Public visibility is not a claim that all contents
are licensed for unrestricted reuse. The owner must resolve this before offering
the entire project under a single open-source license.

Locked third-party projects and patch licenses are documented in
[sources](docs/sources.md) and `vendor/source-lock*.yaml`. Builds fetch full
sources and preserve upstream license files. Historical Docker parent image IDs
describe provenance; the new source build uses the multi-stage recipe.

Porth meshes, textures, derived route bundles, bags and Atlas files are external
and are not published here. Their owners control access and redistribution.
Public checksums identify the expected local bundle; they do not grant asset rights.
