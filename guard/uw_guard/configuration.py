"""Guard-owned safety envelope derivation for explicitly screened survey routes."""
import math


def route_safety_envelope(route):
    """Return position bounds with the existing 1 m depth / 2 m horizontal margins.

    This bounds a pre-screened diagnostic route; it does not establish clearance
    or grant ARM. Runtime health checks and the terminal watchdog still apply.
    """
    if not route or any(len(p) != 3 or not all(math.isfinite(x) for x in p) for p in route):
        raise ValueError('Safety envelope requires a nonempty finite XYZ route')
    return {
        'depth_enu_m': [min(p[2] for p in route) - 1, max(p[2] for p in route) + 1],
        'horizontal_position_abs_m': max(abs(x) for p in route for x in p[:2]) + 2,
    }
