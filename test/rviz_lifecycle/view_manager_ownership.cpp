// Real RViz frame/controller lifecycle; needs the container's NVIDIA/X11 display.
#include <QApplication>
#include <QPointer>
#include <iostream>
#include <rviz_common/ros_integration/ros_client_abstraction.hpp>
#include <rviz_common/visualization_frame.hpp>
#include <rviz_common/visualization_manager.hpp>
#include <rviz_common/view_manager.hpp>

int main(int argc, char ** argv)
{
  QApplication app(argc, argv);
  rviz_common::ros_integration::RosClientAbstraction client;
  auto node = client.init(argc, argv, "rviz_lifecycle_regression", false);
  auto * frame = new rviz_common::VisualizationFrame(node, nullptr);
  frame->initialize(node, "/workspace/test/rviz_lifecycle/minimal.rviz");
  QPointer<rviz_common::ViewManager> view_manager(frame->getManager()->getViewManager());
  delete frame;
  const bool released = view_manager.isNull();
  std::cout << "VIEW_MANAGER_RELEASED=" << released << std::endl;
  client.shutdown();
  return released ? 0 : 42;
}
