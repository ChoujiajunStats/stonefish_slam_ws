"""Last external adapter; never owns the final watchdog and never repeats cached output."""
import json,math,time
from pathlib import Path
import signal
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.node import Node
from std_msgs.msg import String
from uw_interfaces.msg import ActuatorOutput


class ActuatorAdapter(Node):
    def __init__(self):
        super().__init__('actuator_adapter')
        self.output=Path(self.declare_parameter('run_dir','').value);self.run=self.output.name
        self.terminal={};self.seq=0;self.fault_generation=None
        self.native=self.create_publisher(String,'sim/terminal/input',1)
        self.status=self.create_publisher(String,'control/adapter_status',1)
        self.create_subscription(String,'sim/terminal/status',lambda m:setattr(self,'terminal',json.loads(m.data)),1)
        self.create_subscription(ActuatorOutput,'control/output',self.on_output,1)

    def on_output(self,msg):
        now=time.monotonic_ns();a=msg.authorization;r=a.request
        valid=(self.terminal.get('state')=='ARMED' and r.run_id==self.run and
               r.generation==int(self.terminal.get('generation',0)) and
               self.fault_generation!=r.generation and
               r.issued_steady_ns<=msg.computed_steady_ns<=now and now-msg.computed_steady_ns<=200_000_000 and
               now<a.deadline_steady_ns<=r.issued_steady_ns+250_000_000 and
               list(msg.names)==self.terminal.get('names') and len(msg.setpoint)==8 and
               all(math.isfinite(x) and abs(x)<=0.6+1e-9 for x in msg.setpoint))
        if not valid:
            # Inactive/late authorization is simply dropped. Invalid current output latches.
            if self.terminal.get('state')=='ARMED' and r.generation==int(self.terminal['generation']):
                self.fault_generation=r.generation
            self.status.publish(String(data=json.dumps(dict(state='REJECTED',generation=r.generation,wall_ns=now))))
            return
        self.seq+=1
        p=dict(run=self.run,generation=r.generation,token=r.token,issued_ns=r.issued_steady_ns,
               deadline_ns=a.deadline_steady_ns,computed_ns=msg.computed_steady_ns,request_seq=r.sequence,
               output_seq=self.seq,names=list(msg.names),values=list(msg.setpoint))
        self.native.publish(String(data=json.dumps(p)))
        self.status.publish(String(data=json.dumps(dict(state='FORWARDED',generation=r.generation,
                                                       wall_ns=now,output_seq=self.seq))))


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=ActuatorAdapter()
    stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0]:rclpy.spin_once(node,timeout_sec=.1)
    except (KeyboardInterrupt,rclpy.executors.ExternalShutdownException):pass
    finally:node.destroy_node();rclpy.try_shutdown()
