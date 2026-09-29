"""Real stereo SLAM probe plus explicitly authorized, finite data-collection path."""
import json,math,signal,time
import numpy as np
import rclpy
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from rtabmap_msgs.msg import Info,MapGraph
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as PathMsg
from visualization_msgs.msg import Marker
from uw_benchmark.m3_case import Case as MissionCase
from uw_runtime.artifacts import write_json
from uw_robot.frames import quaternion_rpy as rpy
from uw_robot.frames import rpy_quaternion


class Case(MissionCase):
    def __init__(self):
        super().__init__()
        self.asset=json.loads((self.out/'cave-asset.json').read_text());self.expected_initial_position=self.asset['spawn_enu']
        self.execute_path=self.cfg['execute_path']
        if self.execute_path:self.spec_case=dict(group='missions',waypoints=self.asset['waypoints_mission_start'],mission_timeout_sec=130)
        self.slam_rows=[];self.graph_nodes=0;self.graph_links=0;self.cloud=None;self.cloud_updates=0;self.last_slam_wall=0
        self.max_cloud_points=0;self.graph_poses=[];self.reference_sent=False
        self.next_reference_wall=0.;self.mission_finished_wall=None
        self.slam_path=self.create_publisher(PathMsg,'slam/trajectory',1)
        self.reference=self.create_publisher(Marker,'slam/known_cave',1)
        self.create_subscription(Info,'slam/info',self.slam_info,10)
        self.create_subscription(MapGraph,'slam/map_graph',self.slam_graph,5)
        self.create_subscription(PointCloud2,'slam/cloud_map',self.slam_cloud,1)
    def slam_info(self,m):
        row=dict(wall=time.monotonic(),stamp=m.header.stamp.sec+m.header.stamp.nanosec*1e-9,
            node_id=m.ref_id,loop_closure_id=m.loop_closure_id,proximity_id=m.proximity_detection_id,
            stats=dict(zip(m.stats_keys,m.stats_values)))
        self.slam_rows.append(row);self.last_slam_wall=row['wall']
        with (self.out/'slam-events.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    def slam_graph(self,m):
        self.graph_nodes=max(self.graph_nodes,len(m.poses_id));self.graph_links=max(self.graph_links,len(m.links))
        message=PathMsg(header=m.header)
        for pose in m.poses:message.poses.append(PoseStamped(header=m.header,pose=pose))
        self.slam_path.publish(message)
        self.graph_poses=[[p.position.x,p.position.y,p.position.z] for p in m.poses]
        write_json(self.out/'slam-graph.json',dict(frame=m.header.frame_id,ids=list(m.poses_id),poses=self.graph_poses,
            links=[dict(source=x.from_id,target=x.to_id,type=x.type) for x in m.links]))
    def slam_cloud(self,m):
        self.cloud=m;self.cloud_updates+=1;self.max_cloud_points=max(self.max_cloud_points,m.width*m.height)
    def known_reference(self):
        if not self.estimates:return
        # Display registration uses the configured spawn and first VIO gauge only.
        # No simulator truth is supplied to OpenVINS or RTAB-Map.
        estimate=self.estimates[0];yaw=rpy(estimate['quaternion'])[2]
        alpha=yaw-math.radians(self.cfg['initial_rpy_enu_deg'][2])
        c,s=math.cos(alpha),math.sin(alpha);rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]])
        x,y,z=self.asset['cave_offset_ned']
        t=rotation@(np.array([y,x,-z])-np.array(self.asset['spawn_enu']))+np.array(estimate['position'])
        marker=Marker();marker.header.frame_id=self.prefix+'/odom';marker.header.stamp=self.get_clock().now().to_msg()
        marker.ns='KNOWN_ASSET_NOT_SLAM';marker.id=0;marker.type=Marker.MESH_RESOURCE;marker.action=Marker.ADD
        directory=self.out.parent.parent/'assets'/self.cfg['cave_asset']
        marker.mesh_resource=(directory/'rviz_cutaway.obj').as_uri();marker.mesh_use_embedded_materials=True
        marker.pose.position.x,marker.pose.position.y,marker.pose.position.z=map(float,t)
        q=rpy_quaternion(math.pi,0,alpha+math.pi/2-self.asset['cave_yaw_ned'])
        marker.pose.orientation.x,marker.pose.orientation.y,marker.pose.orientation.z,marker.pose.orientation.w=q
        marker.scale.x=marker.scale.y=marker.scale.z=self.asset['scale'];marker.color.a=1.
        self.reference.publish(marker)
    def tick(self):
        super().tick()
        if self.done:return
        if self.begin is not None:
            if self.execute_path and self.goal_future is None:
                g=self.goal('porth_prescribed_slam_path');self.goals=list(g.waypoints)
                self.goal_future=self.action_client.send_goal_async(g,feedback_callback=self.feedback)
                self.event('explicit_path_arm_request',waypoints=self.asset['waypoints_mission_start'])
            if time.monotonic()>self.next_reference_wall:
                self.known_reference();self.next_reference_wall=time.monotonic()+1
            if self.execute_path and self.action_result:
                if self.mission_finished_wall is None:self.mission_finished_wall=time.monotonic()
                if time.monotonic()-self.mission_finished_wall>5:self.finish();return
        if self.truth:
            x,y,z=self.truth[-1]['position'];angles=rpy(self.truth[-1]['quaternion'])
            if not (-12<z<-4 and max(abs(x),abs(y))<4 and max(abs(angles[0]),abs(angles[1]))<math.radians(25)):
                self.errors.append('Porth evaluation safety envelope');self.call('FAULT');self.finish()
    def export_cloud(self):
        if self.cloud is None:return 0
        fields={f.name for f in self.cloud.fields};color='rgb' if 'rgb' in fields else 'rgba' if 'rgba' in fields else None
        names=['x','y','z']+([color] if color else [])
        points=point_cloud2.read_points(self.cloud,field_names=names,skip_nans=True).reshape(-1)
        xyz=np.column_stack([points[k] for k in ('x','y','z')]).astype('<f4')
        rgb=np.zeros((len(points),3),dtype=np.uint8)
        if color:
            packed=points[color]
            if packed.dtype.kind=='f':packed=packed.view(np.uint32)
            for i,shift in enumerate((16,8,0)):rgb[:,i]=(packed.astype(np.uint32)>>shift)&255
        data=np.empty(len(points),dtype=[('xyz','<f4',3),('rgb','u1',3)]);data['xyz']=xyz;data['rgb']=rgb
        header=f'ply\nformat binary_little_endian 1.0\nelement vertex {len(points)}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n'
        (self.out/'slam-map.ply').write_bytes(header.encode()+data.tobytes())
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig=plt.figure(figsize=(12,6));ax=fig.add_subplot(121,projection='3d');bx=fig.add_subplot(122)
        stride=max(1,len(xyz)//20000);p=xyz[::stride];colors=rgb[::stride]/255.
        ax.scatter(*p.T,c=colors,s=.6);bx.scatter(p[:,0],p[:,1],c=colors,s=.6)
        if self.graph_poses:
            v=np.array(self.graph_poses);ax.plot(*v.T,color='crimson',label='SLAM graph');bx.plot(v[:,0],v[:,1],color='crimson')
        ax.set(xlabel='map X (m)',ylabel='map Y (m)',zlabel='map Z (m)',title='Stereo SLAM cloud (no imported mesh)')
        bx.set(xlabel='map X (m)',ylabel='map Y (m)',title='Top view');bx.axis('equal');fig.tight_layout()
        fig.savefig(self.out/'figures/slam-map.png',dpi=160);plt.close(fig)
        return len(points)
    def finish(self):
        if self.done:return
        evaluation_wall=time.monotonic()
        super().finish()
        thresholds=self.spec['thresholds'];points=self.export_cloud()
        endpoints=[dict(name=x.node_name,namespace=x.node_namespace,gid=list(x.endpoint_gid)) for x in self.get_publishers_info_by_topic('/tf')]
        checks=dict(live_slam_updates=len(self.slam_rows)>5,
            slam_graph=self.graph_nodes>=(thresholds['slam_graph_nodes_motion'] if self.execute_path else 1),
            stereo_map_points=points>=thresholds['slam_map_points'],
            map_tf_received=self.tf_edges.get(self.prefix+'/map->'+self.prefix+'/odom',0)>0,
            slam_fresh=evaluation_wall-self.last_slam_wall<5,
            no_automatic_arm=self.initial_disarmed)
        if self.execute_path:
            positions=np.array([v['position'] for v in self.estimates])
            checks['motion_data_collected']=len(positions)>0 and float(np.linalg.norm(positions[:,:2]-positions[0,:2],axis=1).max())>=thresholds['estimated_horizontal_travel_m']
        else:checks['remained_disarmed']=all(x['state']=='DISARMED' for x in self.guard_rows)
        loops=[x for x in self.slam_rows if x['loop_closure_id']>0];proximity=[x for x in self.slam_rows if x['proximity_id']>0]
        passed=self.result==0 and all(checks.values())
        write_json(self.out/'slam-metrics.json',dict(status='PASS' if passed else 'FAIL',checks={k:bool(v) for k,v in checks.items()},
            scope='PRESCRIBED_PATH_SLAM' if self.execute_path else 'STATIC_SENSOR_AND_MAPPING_SMOKE',
            graph_nodes=self.graph_nodes,graph_links=self.graph_links,map_points=points,cloud_updates=self.cloud_updates,
            tf_publisher_endpoints=endpoints,per_message_map_tf_gid='NOT_AVAILABLE_IN_THIS_RCLPY',
            loop_closures=len(loops),proximity_detections=len(proximity),
            loop_closure_verification='OBSERVED' if loops else 'NOT_OBSERVED',
            truth_input_to_slam=False,known_asset_is_slam_output=False,
            unverified=['autonomous exploration','obstacle avoidance','full-cave coverage','real hardware']))
        self.result=0 if passed else 1


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO);node=Case();stop=[False]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    try:
        while rclpy.ok() and not stop[0] and not node.done:rclpy.spin_once(node,timeout_sec=.05)
    finally:
        result=node.result;node.stream.close();node.destroy_node();rclpy.try_shutdown()
    raise SystemExit(result)
