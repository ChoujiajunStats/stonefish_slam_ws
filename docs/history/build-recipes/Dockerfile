ARG UW_BASE_IMAGE=ros:jazzy-ros-base@sha256:c3706ef0a0aa45413c07803cf433602f543b22e45b4855f6fca955c2d8ecc4e8
FROM ${UW_BASE_IMAGE}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG UW_BASE_IMAGE
ARG UW_BUILD_JOBS=8
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates \
    libglm-dev libsdl2-dev libfreetype6-dev libgl1-mesa-dev \
    python3-colcon-common-extensions python3-yaml python3-pip python3-matplotlib \
    ros-jazzy-ament-cmake-python ros-jazzy-image-transport \
    ros-jazzy-pcl-conversions ros-jazzy-rosgraph-msgs \
    ros-jazzy-tf2-ros ros-jazzy-diagnostic-msgs \
    ros-jazzy-rviz2 ros-jazzy-robot-state-publisher \
    ros-jazzy-rosbag2-storage-mcap mesa-utils xauth \
    && rm -rf /var/lib/apt/lists/*

COPY vendor /opt/uw/vendor
COPY scripts/fetch_upstream.py /opt/uw/fetch_upstream.py
COPY scripts/record_build.py /opt/uw/record_build.py
RUN python3 /opt/uw/fetch_upstream.py --lock /opt/uw/vendor/source-lock.yaml \
      --destination /opt/uw_src --evidence /opt/uw/upstream-evidence.json \
    && cmake -S /opt/uw_src/stonefish -B /opt/uw_build/stonefish \
      -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF \
    && cmake --build /opt/uw_build/stonefish --parallel "${UW_BUILD_JOBS}" \
    && cmake --install /opt/uw_build/stonefish && ldconfig

RUN source /opt/ros/jazzy/setup.bash \
    && export MAKEFLAGS="-j${UW_BUILD_JOBS}" CMAKE_BUILD_PARALLEL_LEVEL="${UW_BUILD_JOBS}" \
    && colcon build --base-paths /opt/uw_src/stonefish_ros2 /opt/uw_src/stonefish_bluerov2 \
      --build-base /opt/uw_build/ros --install-base /opt/uw_underlay --merge-install \
      --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    && colcon build --base-paths /opt/uw_src/rviz/rviz_common /opt/uw_src/rviz/rviz_default_plugins \
      --build-base /opt/uw_build/rviz --install-base /opt/uw_underlay --merge-install \
      --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    && dpkg-query -W > /opt/uw/dpkg-packages.txt \
    && python3 -m pip list --format=json > /opt/uw/python-packages.json \
    && UW_BUILD_BASE="${UW_BASE_IMAGE}" python3 /opt/uw/record_build.py

COPY test/rviz_lifecycle /opt/uw/rviz_lifecycle
RUN source /opt/ros/jazzy/setup.bash && source /opt/uw_underlay/setup.bash \
    && cmake -S /opt/uw/rviz_lifecycle -B /opt/uw_build/rviz_lifecycle \
    && cmake --build /opt/uw_build/rviz_lifecycle --parallel "${UW_BUILD_JOBS}" \
    && QT_QPA_PLATFORM=offscreen ASAN_OPTIONS=detect_leaks=0 /opt/uw_build/rviz_lifecycle/image_unsubscribe

COPY docker/entrypoint.sh /opt/uw/entrypoint.sh
RUN chmod +x /opt/uw/entrypoint.sh && mkdir -p /work/overlay && chmod 1777 /work/overlay
ENV PYTHONDONTWRITEBYTECODE=1 ROS_HOME=/tmp/uw-ros XDG_CACHE_HOME=/tmp/uw-cache
WORKDIR /workspace
ENTRYPOINT ["/opt/uw/entrypoint.sh"]
CMD ["bash"]
