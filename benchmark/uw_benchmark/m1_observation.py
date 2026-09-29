"""M0 observation thresholds reused unchanged; control is verified separately."""
import rclpy
from uw_benchmark.probe import Probe
class M1Observation(Probe):
    result_file='observation-metrics.json'
    ready_file='observations-ready.json'
    scope='M1_observation_probe'
    forbidden_topics=()
    ready_message='PRIVILEGED_DEBUG; M1 control checked separately'
def main(args=None):
    rclpy.init(args=args);node=M1Observation()
    try:
        while rclpy.ok() and not node.done:rclpy.spin_once(node,timeout_sec=.2)
        code=node.result_code
    finally:node.destroy_node();rclpy.try_shutdown()
    raise SystemExit(code)
