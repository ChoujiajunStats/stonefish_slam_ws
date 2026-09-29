#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /opt/uw_underlay/setup.bash
if [[ -f /work/overlay/install/setup.bash ]]; then
    source /work/overlay/install/setup.bash
fi
exec "$@"
