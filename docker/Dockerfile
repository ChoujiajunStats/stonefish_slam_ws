# syntax=docker/dockerfile:1
# Portable source build. No local historical image tags are required.
ARG UW_BASE_IMAGE=ros:jazzy-ros-base@sha256:c3706ef0a0aa45413c07803cf433602f543b22e45b4855f6fca955c2d8ecc4e8
FROM ${UW_BASE_IMAGE} AS core
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
LABEL org.opencontainers.image.title="stonefish_slam_ws" io.stonefish-slam.profile="core"

# M0/M1 tags and their original source lock remain untouched.
FROM core AS vio
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
LABEL org.opencontainers.image.title="stonefish_slam_ws" io.stonefish-slam.profile="vio"

# The M3 lock is retained as a runtime-verified source provenance marker.
FROM vio AS navigation
COPY vendor/source-lock.m3.yaml /opt/uw/source-lock.m3.yaml
RUN sha256sum /opt/uw/source-lock.m3.yaml > /opt/uw/m3-lock.sha256
LABEL org.opencontainers.image.title="stonefish_slam_ws" io.stonefish-slam.profile="navigation"

# Parent layers are built above; historical M0--M3 tags are never overwritten.
FROM navigation AS rtabmap
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ros-jazzy-rtabmap-slam=0.23.7-1noble.20260903.103010 \
    ros-jazzy-rtabmap-util=0.23.7-1noble.20260903.095812 \
    ros-jazzy-rtabmap-msgs=0.23.7-1noble.20260902.042917 \
    && dpkg-query -W > /opt/uw/porth-dpkg-packages.txt \
    && rm -rf /var/lib/apt/lists/*
COPY vendor/source-lock.porth.yaml /opt/uw/source-lock.porth.yaml
RUN sha256sum /opt/uw/source-lock.porth.yaml > /opt/uw/porth-lock.sha256
LABEL org.opencontainers.image.title="stonefish_slam_ws" io.stonefish-slam.profile="rtabmap"

# Additive optical-only patch to the locked Porth image; old tags stay intact.
FROM rtabmap AS survey
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY vendor/source-lock.survey.yaml /opt/uw/survey/source-lock.survey.yaml
COPY vendor/patches/0009-survey-optical-lights.patch /opt/uw/survey/
RUN python3 - <<'PY'
import hashlib,pathlib,subprocess,yaml
r=pathlib.Path('/opt/uw/survey');l=yaml.safe_load((r/'source-lock.survey.yaml').read_text())
assert hashlib.sha256(pathlib.Path('/opt/uw/source-lock.porth.yaml').read_bytes()).hexdigest()==l['parent_porth_lock_sha256']
target='/opt/uw_src/'+l['repository'];p=r/l['patch']
assert subprocess.check_output(['git','-C',target,'rev-parse','HEAD'],text=True).strip()==l['commit']
assert hashlib.sha256(p.read_bytes()).hexdigest()==l['patch_sha256']
subprocess.run(['git','-C',target,'apply','--check',str(p)],check=True)
subprocess.run(['git','-C',target,'apply',str(p)],check=True)
PY
RUN source /opt/ros/jazzy/setup.bash && source /opt/uw_underlay/setup.bash \
    && cmake --build /opt/uw_build/ros/stonefish_ros2 --parallel 4 \
    && cmake --install /opt/uw_build/ros/stonefish_ros2 \
    && sha256sum /opt/uw/survey/source-lock.survey.yaml > /opt/uw/survey-lock.sha256
LABEL org.opencontainers.image.title="stonefish_slam_ws" io.stonefish-slam.profile="survey"

# Additive research SLAM image; accepted simulator and historical tags unchanged.
FROM survey AS orbslam3
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libglew-dev libepoxy-dev libboost-serialization-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
# Source fetch is cached separately from local patch revisions.
RUN python3 - <<'PYFETCH'
import pathlib,subprocess,time
for name,url,commit in [('ORB_SLAM3','https://github.com/UZ-SLAMLab/ORB_SLAM3.git','4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4'),('Pangolin','https://github.com/stevenlovegrove/Pangolin.git','aff6883c83f3fd7e8268a9715e84266c42e2efe3')]:
    target=pathlib.Path('/opt/uw_src')/name
    subprocess.run(['git','init',str(target)],check=True)
    for attempt in range(3):
        result=subprocess.run(['git','-C',str(target),'-c','http.lowSpeedLimit=1024','-c','http.lowSpeedTime=30','fetch','--depth','1',url,'refs/tags/v0.8' if name=='Pangolin' else commit],timeout=180)
        if result.returncode==0:break
        if attempt==2:raise RuntimeError('Pinned source download failed')
        time.sleep(2)
    subprocess.run(['git','-C',str(target),'checkout','--detach','FETCH_HEAD'],check=True)
PYFETCH
COPY vendor/source-lock.orbslam3.yaml /opt/uw/orbslam3/source-lock.orbslam3.yaml
COPY vendor/patches/0010-orbslam3-build-export-shutdown.patch vendor/patches/0011-pangolin-fixed-width-integers.patch /opt/uw/orbslam3/
RUN python3 - <<'PY'
import hashlib,pathlib,subprocess,yaml
r=pathlib.Path('/opt/uw/orbslam3');l=yaml.safe_load((r/'source-lock.orbslam3.yaml').read_text())
assert hashlib.sha256(pathlib.Path('/opt/uw/survey/source-lock.survey.yaml').read_bytes()).hexdigest()==l['parent_lock_sha256']
for source in l['repositories']:
    target=pathlib.Path('/opt/uw_src')/source['name']
    assert subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()==source['commit']
    for item in source['patches']:
        p=r/item['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
        subprocess.run(['git','-C',str(target),'apply','--check',str(p)],check=True)
        subprocess.run(['git','-C',str(target),'apply',str(p)],check=True)
PY
RUN cmake -S /opt/uw_src/Pangolin -B /opt/uw_build/pangolin \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_TOOLS=OFF -DBUILD_TESTS=OFF \
    -DBUILD_PANGOLIN_PYTHON=OFF -DBUILD_PANGOLIN_VIDEO=OFF \
    && cmake --build /opt/uw_build/pangolin --parallel 4 \
    && cmake --install /opt/uw_build/pangolin
RUN cmake -S /opt/uw_src/ORB_SLAM3/Thirdparty/DBoW2 -B /opt/uw_build/dbow2 -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/uw_build/dbow2 --parallel 4 \
    && cmake -S /opt/uw_src/ORB_SLAM3 -B /opt/uw_build/orbslam3 -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/uw_build/orbslam3 --target ORB_SLAM3 --parallel 4 \
    && tar -xf /opt/uw_src/ORB_SLAM3/Vocabulary/ORBvoc.txt.tar.gz -C /opt/uw_src/ORB_SLAM3/Vocabulary \
    && printf '%s\n' /opt/uw_src/ORB_SLAM3/lib /opt/uw_src/ORB_SLAM3/Thirdparty/DBoW2/lib /opt/uw_src/ORB_SLAM3/Thirdparty/g2o/lib > /etc/ld.so.conf.d/uw-orbslam3.conf \
    && ldconfig \
    && sha256sum /opt/uw/orbslam3/source-lock.orbslam3.yaml > /opt/uw/orbslam3-lock.sha256 \
    && sha256sum /opt/uw_src/ORB_SLAM3/Vocabulary/ORBvoc.txt > /opt/uw/orbslam3/vocabulary.sha256 \
    && dpkg-query -W > /opt/uw/orbslam3/dpkg-packages.txt
LABEL org.opencontainers.image.title="stonefish_slam_ws" io.stonefish-slam.profile="orbslam3"
