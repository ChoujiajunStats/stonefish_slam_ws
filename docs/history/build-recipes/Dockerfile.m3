# Checked against vendor/source-lock.m3.yaml by scripts/uw before building.
FROM underwater-stack:m2-v3
COPY vendor/source-lock.m3.yaml /opt/uw/source-lock.m3.yaml
RUN sha256sum /opt/uw/source-lock.m3.yaml > /opt/uw/m3-lock.sha256
