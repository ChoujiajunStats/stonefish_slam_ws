// SPDX-License-Identifier: GPL-3.0-or-later
// Independent stereo SLAM: no truth, asset, IMU or external odometry input.
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <nav_msgs/msg/path.hpp>
#include <std_msgs/msg/string.hpp>
#include <tf2_ros/transform_broadcaster.h>
#include <System.h>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <chrono>
#include <algorithm>
#include <sstream>
#include <stdexcept>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <thread>

using Steady = std::chrono::steady_clock;
static double wall() {return std::chrono::duration<double>(Steady::now().time_since_epoch()).count();}
static int64_t stamp(const builtin_interfaces::msg::Time& t) {return int64_t(t.sec)*1000000000+t.nanosec;}
static volatile std::sig_atomic_t stopped=0;
static void interrupt(int) {stopped=1;}

class StereoSlam : public rclcpp::Node {
 public:
  StereoSlam():Node("orbslam3") {
    prefix_=declare_parameter<std::string>("frame_prefix", "rov01");
    directory_=declare_parameter<std::string>("run_dir", "");
    auto settings=declare_parameter<std::string>("settings_path", "");
    if(directory_.empty() || settings.empty()) throw std::runtime_error("Explicit run/settings required");
    maximum_age_=declare_parameter<double>("maximum_input_age_sec",.30);
    capacity_=declare_parameter<int>("maximum_pending_per_side",3);
    double hz=declare_parameter<double>("map_publish_hz",1.);
    if(maximum_age_<=0 || maximum_age_>.5 || capacity_<1 || capacity_>10 || hz<=0 || hz>5) throw std::runtime_error("Invalid queue/age/publish bounds");
    map_period_=1./hz;
    double clip=declare_parameter<double>("clahe_clip_limit",3.0);int grid=declare_parameter<int>("clahe_grid_size",8);
    if(clip<1 || clip>10 || grid<2 || grid>16) throw std::runtime_error("Invalid explicit CLAHE bounds");
    clahe_=cv::createCLAHE(clip,cv::Size(grid,grid));
    cv::setNumThreads(1);
    cv::FileStorage fs(settings,cv::FileStorage::READ);cv::Mat t;fs["Research.T_body_camera"]>>t;
    if(t.rows!=4 || t.cols!=4 || t.type()!=CV_32F) throw std::runtime_error("Missing calibrated camera-to-body transform");
    Eigen::Matrix4f matrix;for(int i=0;i<4;++i) for(int j=0;j<4;++j) matrix(i,j)=t.at<float>(i,j);
    body_camera_=Sophus::SE3f(matrix);
    pose_=create_publisher<geometry_msgs::msg::PoseStamped>("slam/pose",5);
    path_=create_publisher<nav_msgs::msg::Path>("slam/trajectory",1);
    cloud_=create_publisher<sensor_msgs::msg::PointCloud2>("slam/cloud_map",1);
    status_=create_publisher<std_msgs::msg::String>("slam/status",10);
    tf_=std::make_unique<tf2_ros::TransformBroadcaster>(*this);
    std::filesystem::create_directories(directory_+"/orb-camera-samples");
    frames_.open(directory_+"/orb-frames.jsonl");frames_<<std::setprecision(12);
    // Upstream Atlas filenames are relative to process cwd, never shared across runs.
    std::filesystem::current_path(directory_);
    slam_=std::make_unique<ORB_SLAM3::System>("/opt/uw_src/ORB_SLAM3/Vocabulary/ORBvoc.txt",settings,ORB_SLAM3::System::STEREO,false);
    for(int side=0;side<2;++side) image_[side]=create_subscription<sensor_msgs::msg::Image>(
      std::string("sensors/stereo/")+(side==0?"left":"right")+"/image_raw",rclcpp::SensorDataQoS().keep_last(3),
      [this,side](sensor_msgs::msg::Image::ConstSharedPtr m){image(m,side);});
  }
  void finish() {
    slam_->Shutdown();
    auto snapshot=slam_->GetResearchSnapshot();
    save(snapshot);
    if(!snapshot.keyframes.empty()) {
      // These are post-run optimized trajectories; preserve the distinct raw online poses.
      slam_->SaveTrajectoryTUM(directory_+"/orb-optimized-camera-tum.txt");
      slam_->SaveKeyFrameTrajectoryTUM(directory_+"/orb-keyframes-camera-tum.txt");
    }
    frames_.flush();frames_.close();
  }
 private:
  geometry_msgs::msg::Pose pose(const Sophus::SE3f& t) {
    geometry_msgs::msg::Pose p;auto x=t.translation();auto q=t.unit_quaternion();
    p.position.x=x.x();p.position.y=x.y();p.position.z=x.z();
    p.orientation.x=q.x();p.orientation.y=q.y();p.orientation.z=q.z();p.orientation.w=q.w();return p;
  }
  void image(sensor_msgs::msg::Image::ConstSharedPtr m,int side) {
    ++received_[side];int64_t t=stamp(m->header.stamp);
    if(t<=last_) {++dropped_;return;}
    if(m->header.frame_id!=prefix_+(side==0?"/left_camera_optical":"/right_camera_optical") ||
       m->encoding!="rgb8" || m->width!=640 || m->height!=480 || m->step!=1920 || m->data.size()!=921600) {
      fault_="IMAGE_CONTRACT";publish_status(t,0);return;
    }
    pending_[side][t]=m;
    for(auto& queue:pending_) while(queue.size()>size_t(capacity_)) {queue.erase(queue.begin());++dropped_;}
    if(!pending_[1-side].count(t)) return;
    const double age=(get_clock()->now().nanoseconds()-t)*1e-9;
    if(age>maximum_age_ || age<-.10) {for(auto& queue:pending_) queue.erase(queue.begin(),queue.upper_bound(t));++dropped_;return;}
    if(last_ && t<last_) {fault_="TIME_REWIND";return;}
    if(!fault_.empty()) return;
    cv::Mat rgb[2];for(int i=0;i<2;++i) {auto& im=*pending_[i].at(t);rgb[i]=cv::Mat(im.height,im.width,CV_8UC3,const_cast<unsigned char*>(im.data.data()),im.step);}
    double begin=wall();cv::Mat processed[2];
    for(int i=0;i<2;++i) {cv::Mat gray;cv::cvtColor(rgb[i],gray,cv::COLOR_RGB2GRAY);clahe_->apply(gray,processed[i]);}
    auto Tcw=slam_->TrackStereo(processed[0],processed[1],t*1e-9);compute_=wall()-begin;
    features_=slam_->GetTrackedKeyPointsUn().size();
    state_=slam_->GetTrackingState();++processed_;last_=t;latency_=(get_clock()->now().nanoseconds()-t)*1e-9;
    bool valid=state_==2 && Tcw.matrix().allFinite();if(valid) ++tracked_;else ++lost_;
    Sophus::SE3f body;
    if(valid) {
      body=body_camera_*Tcw.inverse()*body_camera_.inverse();
      geometry_msgs::msg::PoseStamped p;p.header.stamp=rclcpp::Time(t,RCL_ROS_TIME);p.header.frame_id=prefix_+"/map";p.pose=pose(body);pose_->publish(p);
      geometry_msgs::msg::TransformStamped tf;tf.header=p.header;tf.child_frame_id=prefix_+"/orb_body";
      tf.transform.translation.x=p.pose.position.x;tf.transform.translation.y=p.pose.position.y;tf.transform.translation.z=p.pose.position.z;
      tf.transform.rotation=p.pose.orientation;tf_->sendTransform(tf);
    }
    frames_<<"{\"stamp\":"<<t*1e-9<<",\"wall\":"<<wall()<<",\"tracking_state\":"<<state_<<",\"valid\":"<<(valid?"true":"false")
       <<",\"compute_sec\":"<<compute_<<",\"latency_sec\":"<<latency_<<",\"map_id\":"<<snapshot_.map_id;
    if(valid) {auto p=body.translation();auto q=body.unit_quaternion();frames_<<",\"position\":["<<p.x()<<","<<p.y()<<","<<p.z()<<"],\"quaternion\":["<<q.x()<<","<<q.y()<<","<<q.z()<<","<<q.w()<<"]";}
    frames_<<"}\n";
    if(wall()-last_snapshot_>=map_period_) {
      snapshot_=slam_->GetResearchSnapshot();publish_map(t);last_snapshot_=wall();frames_.flush();
      for(int i=0;i<2;++i) {
        cv::Mat bgr;cv::cvtColor(rgb[i],bgr,cv::COLOR_RGB2BGR);
        if(!cv::imwrite(directory_+"/orb-camera-samples/"+std::to_string(t)+(i==0?"-left.jpg":"-right.jpg"),bgr,{cv::IMWRITE_JPEG_QUALITY,90})) throw std::runtime_error("Cannot write camera evidence");
      }
    }
    for(auto& queue:pending_) queue.erase(queue.begin(),queue.upper_bound(t));
    publish_status(t,valid);
  }
  void publish_map(int64_t t) {
    nav_msgs::msg::Path path;path.header.frame_id=prefix_+"/map";path.header.stamp=rclcpp::Time(t,RCL_ROS_TIME);
    for(auto& k:snapshot_.keyframes) {geometry_msgs::msg::PoseStamped p;p.header=path.header;p.header.stamp=rclcpp::Time(int64_t(k.stamp*1e9),RCL_ROS_TIME);p.pose=pose(body_camera_*k.Twc*body_camera_.inverse());path.poses.push_back(p);}
    path_->publish(path);
    sensor_msgs::msg::PointCloud2 cloud;cloud.header=path.header;
    sensor_msgs::PointCloud2Modifier modifier(cloud);modifier.setPointCloud2Fields(3,"x",1,sensor_msgs::msg::PointField::FLOAT32,"y",1,sensor_msgs::msg::PointField::FLOAT32,"z",1,sensor_msgs::msg::PointField::FLOAT32);
    const size_t stride=std::max(size_t(1),(snapshot_.points.size()+199999)/200000);modifier.resize((snapshot_.points.size()+stride-1)/stride);
    sensor_msgs::PointCloud2Iterator<float> x(cloud,"x"),y(cloud,"y"),z(cloud,"z");
    for(size_t i=0;i<snapshot_.points.size();i+=stride,++x,++y,++z) {auto p=body_camera_*snapshot_.points[i];*x=p.x();*y=p.y();*z=p.z();}
    cloud_->publish(cloud);
  }
  void publish_status(int64_t t,bool valid) {
    std::ostringstream s;s<<std::setprecision(12)<<"{\"backend\":\"ORB_SLAM3\",\"mode\":\"STEREO\",\"stamp\":"<<t*1e-9
      <<",\"processed\":"<<processed_<<",\"tracking_state\":"<<state_<<",\"tracked\":"<<(valid?"true":"false")
      <<",\"tracked_count\":"<<tracked_<<",\"lost_count\":"<<lost_<<",\"dropped\":"<<dropped_
      <<",\"received_left\":"<<received_[0]<<",\"received_right\":"<<received_[1]<<",\"compute_sec\":"<<compute_<<",\"latency_sec\":"<<latency_
      <<",\"features\":"<<features_<<",\"map_id\":"<<snapshot_.map_id<<",\"map_count\":"<<snapshot_.maps<<",\"keyframes\":"<<snapshot_.keyframes.size()<<",\"sparse_points\":"<<snapshot_.points.size()
      <<",\"loop_edges\":"<<snapshot_.loop_edges<<",\"big_changes\":"<<snapshot_.big_changes<<",\"fault\":\""<<fault_<<"\",\"truth_input\":false,\"external_odometry_input\":false}";
    std_msgs::msg::String message;message.data=s.str();status_->publish(message);
  }
  void save(const ORB_SLAM3::System::ResearchSnapshot& s) {
    std::ofstream cloud(directory_+"/orb-sparse-map.ply",std::ios::binary);
    cloud<<"ply\nformat binary_little_endian 1.0\nelement vertex "<<s.points.size()<<"\nproperty float x\nproperty float y\nproperty float z\nend_header\n";
    for(auto& point:s.points) {Eigen::Vector3f p=body_camera_*point;cloud.write(reinterpret_cast<const char*>(p.data()),12);}
    std::ofstream keys(directory_+"/orb-keyframes-body.jsonl");keys<<std::setprecision(12);
    for(auto& k:s.keyframes) {auto t=body_camera_*k.Twc*body_camera_.inverse();auto p=t.translation();auto q=t.unit_quaternion();
      keys<<"{\"id\":"<<k.id<<",\"stamp\":"<<k.stamp<<",\"map_id\":"<<s.map_id<<",\"position\":["<<p.x()<<","<<p.y()<<","<<p.z()<<"],\"quaternion\":["<<q.x()<<","<<q.y()<<","<<q.z()<<","<<q.w()<<"]}\n";}
    std::ofstream summary(directory_+"/orb-final.json");summary<<"{\"shutdown_completed\":true,\"map_count\":"<<s.maps<<",\"map_id\":"<<s.map_id
      <<",\"keyframes\":"<<s.keyframes.size()<<",\"sparse_points\":"<<s.points.size()<<",\"loop_edges\":"<<s.loop_edges<<",\"processed\":"<<processed_<<",\"tracked\":"<<tracked_<<",\"lost\":"<<lost_<<",\"dropped\":"<<dropped_<<"}\n";
  }
  cv::Ptr<cv::CLAHE> clahe_;size_t features_=0;
  std::string prefix_,directory_,fault_;std::ofstream frames_;Sophus::SE3f body_camera_;
  std::unique_ptr<ORB_SLAM3::System> slam_;ORB_SLAM3::System::ResearchSnapshot snapshot_;
  std::map<int64_t,sensor_msgs::msg::Image::ConstSharedPtr> pending_[2];int64_t last_=0;
  double maximum_age_=.30,map_period_=1.;int capacity_=3;
  size_t received_[2]={0,0},processed_=0,tracked_=0,lost_=0,dropped_=0;int state_=0;double compute_=0,latency_=0,last_snapshot_=0;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_[2];
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pose_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr path_;rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr cloud_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_;std::unique_ptr<tf2_ros::TransformBroadcaster> tf_;
};
int main(int argc,char** argv) {
  rclcpp::init(argc,argv,rclcpp::InitOptions(),rclcpp::SignalHandlerOptions::None);
  std::signal(SIGINT,interrupt);std::signal(SIGTERM,interrupt);
  try {auto node=std::make_shared<StereoSlam>();while(rclcpp::ok()&&!stopped) {rclcpp::spin_some(node);std::this_thread::sleep_for(std::chrono::milliseconds(1));}node->finish();node.reset();rclcpp::shutdown();return 0;}
  catch(const std::exception& e) {std::cerr<<"ORB adapter failure: "<<e.what()<<std::endl;rclcpp::shutdown();return 1;}
}
