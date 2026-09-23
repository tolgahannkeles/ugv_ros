cmake_minimum_required(VERSION 3.8)
project(ugv_gazebo)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch models worlds
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/gps_driver.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
