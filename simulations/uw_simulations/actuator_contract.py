"""Motor channel validation shared by the external adapter and contract tests."""
import math


def valid_channels(names, values, expected):
    return (len(expected) in (6, 8) and len(set(expected)) == len(expected)
            and list(names) == list(expected) and len(values) == len(expected)
            and all(math.isfinite(x) and abs(x) <= 0.6 + 1e-9 for x in values))
