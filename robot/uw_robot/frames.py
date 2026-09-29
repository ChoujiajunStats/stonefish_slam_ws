"""Pure coordinate math, quaternion order x,y,z,w; REP-103 boundary."""

import math


def qmul(a, b):
    x, y, z, w = a
    X, Y, Z, W = b
    return (w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
            w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z)


def normalized(q):
    n = math.sqrt(sum(x*x for x in q))
    if not math.isfinite(n) or n < 1e-12:
        raise ValueError("Invalid quaternion")
    return tuple(x/n for x in q)


def rpy_quaternion(roll, pitch, yaw):
    sr, cr = math.sin(roll/2), math.cos(roll/2)
    sp, cp = math.sin(pitch/2), math.cos(pitch/2)
    sy, cy = math.sin(yaw/2), math.cos(yaw/2)
    return (sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy,
            cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy)


def rotate(q, vector):
    q = normalized(q)
    return qmul(qmul(q, (*vector, 0.0)), (-q[0], -q[1], -q[2], q[3]))[:3]


Q_ENU_NED = (math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0)
Q_FRD_FLU = (1.0, 0.0, 0.0, 0.0)


def ned_to_enu(v):
    return (v[1], v[0], -v[2])


def frd_to_flu(v):
    return (v[0], -v[1], -v[2])


def attitude_to_enu_flu(q):
    return normalized(qmul(qmul(Q_ENU_NED, normalized(q)), Q_FRD_FLU))


def signed_permutation_covariance(values, indices, signs):
    """R C R^T including pose/twist cross-covariances; preserves unknown -1."""
    n = len(indices)
    if len(values) != n*n:
        raise ValueError("Covariance dimensions differ")
    if values[0] == -1:
        return list(values)
    return [signs[i]*signs[j]*values[indices[i]*n+indices[j]]
            for i in range(n) for j in range(n)]


def quaternion_rpy(q):
    """Roll/pitch/yaw radians for unit x,y,z,w quaternions; pitch is clamped at poles."""
    x,y,z,w=q
    return (math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),
            math.asin(max(-1,min(1,2*(w*y-z*x)))),
            math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)))
