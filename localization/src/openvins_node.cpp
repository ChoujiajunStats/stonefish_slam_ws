// SPDX-License-Identifier: GPL-3.0-or-later
// Own ROS2 transport adapter for the pinned OpenVINS library. No truth input.
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/path.hpp>
#include <std_msgs/msg/string.hpp>
#include <rosgraph_msgs/msg/clock.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2_ros/transform_broadcaster.h>
#include <tf2_msgs/msg/tf_message.hpp>
#include <core/VioManager.h>
#include <state/State.h>
#include <state/Propagator.h>
#include <utils/sensor_data.h>
#include <utils/print.h>
#include <opencv2/imgproc.hpp>
#include <chrono>
#include <cmath>
#include <algorithm>
#include <map>
#include <deque>
#include <sstream>

using Steady = std::chrono::steady_clock;
static double wall() { return std::chrono::duration<double>(Steady::now().time_since_epoch()).count(); }
static double seconds(const builtin_interfaces::msg::Time &t) { return t.sec + 1e-9*t.nanosec; }
static int64_t nanoseconds(const builtin_interfaces::msg::Time &t) { return int64_t(t.sec)*1000000000+t.nanosec; }

class Estimator : public rclcpp::Node {
 public:
  Estimator() : Node("openvins") {
    prefix_=declare_parameter<std::string>("frame_prefix","rov01");
    run_=declare_parameter<std::string>("run_id","");
    allow_static_=declare_parameter<bool>("allow_static_initialization",false);
    normalized_health_=declare_parameter<bool>("normalize_health_image",false);
    auto config=declare_parameter<std::string>("config_path","");
    auto parser=std::make_shared<ov_core::YamlParser>(config);
    parser->parse_config("maximum_body_speed_m_s",max_speed_);
    max_speed_=declare_parameter<double>("maximum_body_speed_m_s",max_speed_);
    if(!std::isfinite(max_speed_) || max_speed_<=0) throw std::runtime_error("Invalid estimation plausibility limit");
    std::string verbosity="WARNING";
    parser->parse_config("verbosity",verbosity);
    ov_core::Printer::setPrintLevel(verbosity);
    options_.print_and_load(parser);
    if (!parser->successful()) throw std::runtime_error("Invalid OpenVINS calibration/configuration");
    options_.use_multi_threading_subs=false;
    options_.use_multi_threading_pubs=false;
    app_=std::make_shared<ov_msckf::VioManager>(options_);
    odom_=create_publisher<nav_msgs::msg::Odometry>("state/odometry",5);
    path_=create_publisher<nav_msgs::msg::Path>("localization/trajectory",2);
    status_=create_publisher<std_msgs::msg::String>("localization/status",1);
    tf_=std::make_unique<tf2_ros::TransformBroadcaster>(*this);
    tf_monitor_=create_subscription<tf2_msgs::msg::TFMessage>("/tf",rclcpp::QoS(100),
      [this](tf2_msgs::msg::TFMessage::ConstSharedPtr message,const rclcpp::MessageInfo &info) {
        for(const auto &t:message->transforms) if(t.child_frame_id==prefix_+"/base_link") {
          bool own=false;
          const auto &gid=info.get_rmw_message_info().publisher_gid;
          for(const auto &endpoint:get_publishers_info_by_topic("/tf")) {
            if(endpoint.node_name()==get_name() && endpoint.node_namespace()==get_namespace()
                && std::equal(endpoint.endpoint_gid().begin(),endpoint.endpoint_gid().end(),gid.data)) own=true;
          }
          if(own && t.header.frame_id==prefix_+"/odom") ++tf_verified_;
          else {++foreign_tf_;fail("FOREIGN_DYNAMIC_TF");}
        }
      });
    auto qos=rclcpp::SensorDataQoS().keep_last(50);
    imu_=create_subscription<sensor_msgs::msg::Imu>("sensors/imu",qos,[this](sensor_msgs::msg::Imu::ConstSharedPtr m){imu(m);});
    for (int i=0;i<2;++i) {
      image_[i]=create_subscription<sensor_msgs::msg::Image>(std::string("sensors/stereo/")+(i==0?"left":"right")+"/image_raw",
        rclcpp::SensorDataQoS().keep_last(5),[this,i](sensor_msgs::msg::Image::ConstSharedPtr m){image(m,i);});
    }
    clock_=create_subscription<rosgraph_msgs::msg::Clock>("/clock",rclcpp::SensorDataQoS(),[this](rosgraph_msgs::msg::Clock::ConstSharedPtr m){
      double t=seconds(m->clock);
      if (clock_t_>=0 && t<clock_t_-1e-9) fail("CLOCK_REWIND");
      if(t>clock_t_) clock_wall_=wall();
      clock_t_=t;
    });
    timer_=create_wall_timer(std::chrono::milliseconds(100),[this](){health();});
    started_=wall();
  }
 private:
  void fail(const std::string &why) {
    if(!fault_.empty()) return;
    RCLCPP_ERROR(get_logger(),"Estimator latched: %s; process restart required",why.c_str());
    fault_=why;
    for(auto &q:pending_) q.clear();
    frames_.clear();
  }
  void imu(sensor_msgs::msg::Imu::ConstSharedPtr m) {
    if(!fault_.empty()) return;
    double t=seconds(m->header.stamp);
    if(t<=imu_t_) {++rejected_; return;}
    if(m->header.frame_id!=prefix_+"/imu_link" || m->orientation_covariance[0]!=-1) {fail("IMU_CONTRACT");return;}
    ov_core::ImuData data;
    data.timestamp=t;
    data.wm<<m->angular_velocity.x,m->angular_velocity.y,m->angular_velocity.z;
    data.am<<m->linear_acceleration.x,m->linear_acceleration.y,m->linear_acceleration.z;
    if(!data.wm.allFinite() || !data.am.allFinite() || data.wm.norm()>20 || data.am.norm()>100) {fail("NONFINITE_OR_RANGE");return;}
    if(imu_t_>0 && t-imu_t_>.15) {fail("IMU_GAP");return;}
    imu_t_=t;imu_wall_=wall();++imu_count_;
    app_->feed_measurement_imu(data);
    drain();
    if((app_->initialized() || (allow_static_ && app_->initialized_time()>=0)) && features_>=15 && imu_t_-image_t_<.25 && wall()-image_wall_<.5
         && imu_t_-last_pub_>=.019 && fault_.empty()) publish();
  }
  void image(sensor_msgs::msg::Image::ConstSharedPtr m,int side) {
    if(!fault_.empty()) return;
    int64_t t=nanoseconds(m->header.stamp);
    if(t<=last_pair_) {++rejected_;return;}
    if(m->header.frame_id!=prefix_+(side==0?"/left_camera_optical":"/right_camera_optical")
       || m->encoding!="rgb8" || m->width!=640 || m->height!=480 || m->step!=m->width*3 || m->data.size()!=m->step*m->height) {
      fail("IMAGE_CONTRACT");return;
    }
    pending_[side][t]=m;
    for(auto &q:pending_) while(q.size()>8) {q.erase(q.begin());++rejected_;}
    if(!pending_[1-side].count(t)) return;
    ov_core::CameraData frame;frame.timestamp=t*1e-9;frame.sensor_ids={0,1};
    for(int i=0;i<2;++i) {
      const auto &im=*pending_[i].at(t);
      cv::Mat rgb(im.height,im.width,CV_8UC3,const_cast<unsigned char*>(im.data.data()),im.step),gray;
      cv::cvtColor(rgb,gray,cv::COLOR_RGB2GRAY);
      frame.images.push_back(gray);frame.masks.push_back(cv::Mat::zeros(gray.size(),CV_8UC1));
      pending_[i].erase(pending_[i].begin(),pending_[i].upper_bound(t));
    }
    last_pair_=t;
    frames_.push_back(frame);
    while(frames_.size()>5) {frames_.pop_front();++rejected_;}
    drain();
  }
  void drain() {
    while(!frames_.empty() && frames_.front().timestamp<imu_t_ && fault_.empty()) {
      auto f=frames_.front();frames_.pop_front();
      if(f.timestamp<=image_t_) {++rejected_;continue;}
      // Avoid feeding old images after a stalled process catches up.
      if(imu_t_-f.timestamp>.4) {++rejected_;continue;}
      double begin=wall();
      std::vector<cv::Point2f> corners;
      cv::goodFeaturesToTrack(f.images[0],corners,200,.02,10);
      raw_features_=corners.size();
      if(normalized_health_) {
        // Match locked OpenVINS TrackKLT.cpp CLAHE (10, 8x8), so a visible
        // bright lamp does not mask textured walls in the readiness probe.
        // Images delivered to VioManager and feature thresholds are unchanged.
        cv::Mat normalized;
        cv::createCLAHE(10.0,cv::Size(8,8))->apply(f.images[0],normalized);
        cv::goodFeaturesToTrack(normalized,corners,200,.02,10);
      }
      features_=corners.size();
      app_->feed_measurement_camera(f);
      compute_ms_=1000*(wall()-begin);
      image_t_=f.timestamp;image_wall_=wall();++image_count_;
      tracks_=app_->get_good_features_MSCKF().size();
    }
  }
  void publish() {
    Eigen::Matrix<double,13,1> x;
    Eigen::Matrix<double,12,12> covariance;
    if(!app_->get_propagator()->fast_state_propagate(app_->get_state(),imu_t_,x,covariance)) return;
    if(!x.allFinite() || !covariance.allFinite() || covariance.diagonal().minCoeff()<-1e-9
        || std::abs(x.head<4>().norm()-1)>.001) {fail("INVALID_ESTIMATE");return;}
    if(x.segment<3>(7).norm()>max_speed_) {fail("IMPLAUSIBLE_BODY_SPEED");return;}
    nav_msgs::msg::Odometry o;
    o.header.stamp=rclcpp::Time(int64_t(std::llround(imu_t_*1e9)),RCL_ROS_TIME);
    o.header.frame_id=prefix_+"/odom";o.child_frame_id=prefix_+"/base_link";
    // OpenVINS stores JPL G->I. Identical xyzw represents Hamilton I->G.
    auto &q=o.pose.pose.orientation;q.x=x(0);q.y=x(1);q.z=x(2);q.w=x(3);
    auto &p=o.pose.pose.position;p.x=x(4);p.y=x(5);p.z=x(6);
    auto &v=o.twist.twist.linear;v.x=x(7);v.y=x(8);v.z=x(9);
    auto &w=o.twist.twist.angular;w.x=x(10);w.y=x(11);w.z=x(12);
    Eigen::Matrix<double,12,12> J=Eigen::Matrix<double,12,12>::Zero();
    J.block<3,3>(0,3).setIdentity();
    // ROS pose orientation error is expressed in the parent (local ENU) frame.
    J.block<3,3>(3,0)=ov_core::quat_2_Rot(x.head<4>()).transpose();
    J.block<6,6>(6,6).setIdentity();
    covariance=J*covariance*J.transpose();
    for(int r=0;r<6;++r) for(int c=0;c<6;++c) {
      o.pose.covariance[6*r+c]=covariance(r,c);
      o.twist.covariance[6*r+c]=covariance(r+6,c+6);
    }
    odom_->publish(o);
    geometry_msgs::msg::TransformStamped transform;
    transform.header=o.header;transform.child_frame_id=o.child_frame_id;
    transform.transform.translation.x=p.x;transform.transform.translation.y=p.y;transform.transform.translation.z=p.z;
    transform.transform.rotation=q;tf_->sendTransform(transform);
    if(++published_%10==0) {
      trajectory_.header=o.header;
      geometry_msgs::msg::PoseStamped pose;pose.header=o.header;pose.pose=o.pose.pose;
      trajectory_.poses.push_back(pose);
      if(trajectory_.poses.size()>1500) trajectory_.poses.erase(trajectory_.poses.begin());
      path_->publish(trajectory_);
    }
    last_pub_=imu_t_;last_pub_wall_=wall();
  }
  void health() {
    double now=wall();
    if(imu_count_>10 && now-imu_wall_>.5) fail("IMU_STALE");
    if(image_count_>10 && now-image_wall_>.5) fail("IMAGE_STALE");
    if(clock_t_>0 && now-clock_wall_>.5) fail("CLOCK_STALLED");
    std::string state=!fault_.empty()?"FAULT":(features_<15 && image_count_>10?"DEGRADED":
      (now-last_pub_wall_<.25 && app_->initialized()?"TRACKING":
       (allow_static_ && app_->initialized_time()>=0 && now-last_pub_wall_<.25?"READY_STATIC":"INITIALIZING")));
    std::ostringstream out;
    out<<"{\"run\":\""<<run_<<"\",\"source\":\"OPENVINS_STEREO_IMU\",\"state\":\""<<state
       <<"\",\"reason\":\""<<fault_<<"\",\"epoch\":1,\"initialized\":"<<(app_->initialized()?"true":"false")
       <<",\"imu_count\":"<<imu_count_<<",\"stereo_count\":"<<image_count_<<",\"published\":"<<published_
       <<",\"health_image_normalized\":"<<(normalized_health_?"true":"false")<<",\"raw_features\":"<<raw_features_<<",\"features\":"<<features_<<",\"msckf_used_features\":"<<tracks_<<",\"rejected\":"<<rejected_
       <<",\"image_stamp\":"<<std::fixed<<image_t_<<",\"imu_stamp\":"<<imu_t_
       <<",\"tf_verified\":"<<tf_verified_<<",\"foreign_tf_seen\":"<<foreign_tf_<<",\"compute_ms\":"<<compute_ms_<<",\"truth_subscriptions\":0}";
    std_msgs::msg::String s;s.data=out.str();status_->publish(s);
  }
  bool normalized_health_=false;
  size_t raw_features_=0;
  std::string prefix_,run_,fault_;
  ov_msckf::VioManagerOptions options_;
  std::shared_ptr<ov_msckf::VioManager> app_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr path_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_[2];
  rclcpp::Subscription<rosgraph_msgs::msg::Clock>::SharedPtr clock_;
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Subscription<tf2_msgs::msg::TFMessage>::SharedPtr tf_monitor_;
  size_t tf_verified_=0,foreign_tf_=0;
  std::map<int64_t,sensor_msgs::msg::Image::ConstSharedPtr> pending_[2];
  std::deque<ov_core::CameraData> frames_;
  nav_msgs::msg::Path trajectory_;
  double imu_t_=-1,image_t_=-1,clock_t_=-1,last_pub_=-1;
  double max_speed_=1.0;
  bool allow_static_=false;
  double imu_wall_=0,image_wall_=0,clock_wall_=0,last_pub_wall_=0,started_=0,compute_ms_=0;
  int64_t last_pair_=-1;
  size_t imu_count_=0,image_count_=0,published_=0,rejected_=0,features_=0,tracks_=0;
};

int main(int argc,char **argv) {
  rclcpp::init(argc,argv);
  try {rclcpp::spin(std::make_shared<Estimator>());}
  catch(const std::exception &e) {fprintf(stderr,"M2 estimator: %s\n",e.what());rclcpp::shutdown();return 1;}
  rclcpp::shutdown();return 0;
}
