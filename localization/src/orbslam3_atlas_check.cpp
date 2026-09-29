// SPDX-License-Identifier: GPL-3.0-or-later
// Read-only native Atlas reload. Settings must omit System.SaveAtlasToFile.
#include <System.h>
#include <opencv2/core.hpp>
#include <filesystem>
#include <iostream>
int main(int argc,char** argv) {
  if(argc!=4) {std::cerr<<"usage: orbslam3_atlas_check RUN_DIR SETTINGS OUTPUT_EUROC\n";return 2;}
  try {
    cv::FileStorage settings(argv[2],cv::FileStorage::READ);
    if(!settings["System.SaveAtlasToFile"].empty() || settings["System.LoadAtlasFromFile"].empty()) return 2;
    cv::setNumThreads(1);std::filesystem::current_path(argv[1]);
    ORB_SLAM3::System slam("/opt/uw_src/ORB_SLAM3/Vocabulary/ORBvoc.txt",argv[2],ORB_SLAM3::System::STEREO,false);
    slam.Shutdown();slam.SaveKeyFrameTrajectoryEuRoC(argv[3]);
    return std::filesystem::exists(argv[3]) && std::filesystem::file_size(argv[3])>0 ? 0:1;
  } catch(const std::exception& e) {std::cerr<<e.what()<<std::endl;return 1;}
}
