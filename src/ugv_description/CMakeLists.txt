cmake_minimum_required(VERSION 3.8)
project(ugv_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config urdf launch rviz meshes
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
