# uw_interfaces — M1 authorization contracts

M0 continues to use standard observation messages with no actuator input.
M1 adds a minimal envelope around TwistStamped: ControlRequest,
AuthorizedCommand, ActuatorOutput, and the Control management service.
Original request timestamps and deadlines propagate to the native receiver.

This is an ament_cmake/rosidl interface package, with no running node.
See [the actual interface contract](../docs/interfaces.md) and
[authority limitations](../docs/module-guard.md).
