# M0/M1 tags and their original source lock remain untouched.
FROM underwater-stack:m1-v4
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG UW_BUILD_JOBS=6
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopencv-dev libceres-dev python3-opencv \
    && rm -rf /var/lib/apt/lists/*
RUN git init /opt/uw_src/open_vins \
    && git -C /opt/uw_src/open_vins fetch --depth 1 https://github.com/rpng/open_vins.git 93adc241390d13e99232652cf05cbe18a93c7bea \
    && git -C /opt/uw_src/open_vins checkout --detach FETCH_HEAD
RUN git init /opt/uw_src/ceres \
    && git -C /opt/uw_src/ceres fetch --depth 1 https://github.com/ceres-solver/ceres-solver.git f68321e7de8929fbcdb95dd42877531e64f72f66 \
    && git -C /opt/uw_src/ceres checkout --detach FETCH_HEAD \
    && cmake -S /opt/uw_src/ceres -B /opt/uw_build/ceres -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX=/opt/uw_ceres -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF \
       -DBUILD_SHARED_LIBS=ON -DSUITESPARSE=OFF -DCXSPARSE=OFF -DLAPACK=OFF \
    && cmake --build /opt/uw_build/ceres --parallel "${UW_BUILD_JOBS}" \
    && cmake --install /opt/uw_build/ceres \
    && echo /opt/uw_ceres/lib > /etc/ld.so.conf.d/uw-ceres.conf && ldconfig
# Upstream's supported standalone C++ library; our ROS2 adapter owns topics and TF.
RUN cmake -S /opt/uw_src/open_vins/ov_msckf -B /opt/uw_build/open_vins \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/opt/uw_ceres -DENABLE_ROS=OFF -DENABLE_ARUCO_TAGS=OFF \
      -DCMAKE_DISABLE_FIND_PACKAGE_ament_cmake=ON \
    && cmake --build /opt/uw_build/open_vins --parallel "${UW_BUILD_JOBS}" \
    && cmake --install /opt/uw_build/open_vins && ldconfig
COPY vendor /opt/uw/m2-vendor
COPY scripts/prepare_m2_upstream.py /opt/uw/
RUN python3 /opt/uw/prepare_m2_upstream.py \
    && cmake -S /opt/uw_src/stonefish -B /opt/uw_build/stonefish -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF \
    && cmake --build /opt/uw_build/stonefish --parallel "${UW_BUILD_JOBS}" \
    && cmake --install /opt/uw_build/stonefish && ldconfig \
    && source /opt/ros/jazzy/setup.bash \
    && export MAKEFLAGS="-j${UW_BUILD_JOBS}" CMAKE_BUILD_PARALLEL_LEVEL="${UW_BUILD_JOBS}" \
    && colcon build --base-paths /opt/uw_src/stonefish_ros2 /opt/uw_src/stonefish_bluerov2 \
       --build-base /opt/uw_build/ros --install-base /opt/uw_underlay --merge-install \
       --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
RUN dpkg-query -W > /opt/uw/m2-dpkg-packages.txt \
    && python3 -m pip list --format=json > /opt/uw/m2-python-packages.json \
    && sha256sum /opt/uw/m2-vendor/source-lock.m2.yaml > /opt/uw/m2-lock.sha256
