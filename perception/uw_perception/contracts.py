"""ROS-free M2 contracts. Pixel coordinates refer to pixel centres (OpenCV)."""
import math


def intrinsics(width, height, horizontal_fov):
    if width <= 0 or height <= 0 or not 0 < horizontal_fov < 180:
        raise ValueError('Invalid pinhole geometry')
    focal = width / (2 * math.tan(math.radians(horizontal_fov)/2))
    return focal, focal, (width-1)/2, (height-1)/2


class ExactPairs:
    """Bounded exact acquisition-stamp pairing; never rewrite a source stamp."""
    def __init__(self, capacity=8):
        self.capacity = capacity
        self.pending = [{}, {}]
        self.last = -1
        self.dropped = 0

    def add(self, side, stamp, payload):
        if side not in (0, 1) or stamp <= self.last:
            self.dropped += 1
            return None
        self.pending[side][stamp] = payload
        for queue in self.pending:
            while len(queue) > self.capacity:
                del queue[min(queue)]
                self.dropped += 1
        if stamp not in self.pending[1-side]:
            return None
        pair = tuple(queue.pop(stamp) for queue in self.pending)
        self.last = stamp
        for queue in self.pending:
            for stale in [s for s in queue if s <= stamp]:
                del queue[stale]
                self.dropped += 1
        return pair


def valid_imu(accel, gyro, orientation_covariance, frame, expected):
    return (frame == expected and len(accel) == len(gyro) == 3
            and orientation_covariance[0] == -1
            and all(math.isfinite(v) for v in (*accel, *gyro))
            and max(map(abs, accel)) < 100 and max(map(abs, gyro)) < 20)
