// Exercises the actual installed patched ImageTransportDisplay, without a GPU or ROS graph.
#include <QApplication>
#include <memory>
#include <rviz_default_plugins/displays/image/image_transport_display.hpp>
#include <sensor_msgs/msg/image.hpp>

class DiagnosticImageDisplay final
  : public rviz_default_plugins::displays::ImageTransportDisplay<sensor_msgs::msg::Image>
{
public:
  void connect_local_filter()
  {
    subscription_ = std::make_shared<image_transport::SubscriberFilter>();
    subscription_callback_ = subscription_->registerCallback(
      [](const sensor_msgs::msg::Image::ConstSharedPtr &) {});
  }
  void hide_dock() {unsubscribe();}
protected:
  void processMessage(sensor_msgs::msg::Image::ConstSharedPtr) override {}
};

int main(int argc, char ** argv)
{
  QApplication app(argc, argv);
  for (int i = 0; i < 100; ++i) {
    DiagnosticImageDisplay display;
    display.connect_local_filter();
    display.hide_dock();
    display.hide_dock();
    // The base destructor unsubscribes once more after the subscriber was freed.
  }
  return 0;
}
