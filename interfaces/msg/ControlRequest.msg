# Public velocity is body FLU at base_link origin, SI units.
geometry_msgs/TwistStamped command
string run_id
string source
string token
uint64 generation
uint64 sequence
uint64 issued_steady_ns
# Optional absolute intent deadline; zero keeps the original 0.25 s request lease.
uint64 valid_until_steady_ns
# Only legal in explicit actuator_probe mode; empty for velocity requests.
sensor_msgs/JointState actuator_probe
