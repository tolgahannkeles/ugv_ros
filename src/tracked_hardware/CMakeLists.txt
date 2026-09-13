cmake_minimum_required(VERSION 3.8)
project(tracked_hardware)

# PERFORMANCE / COMPILER: Enforce strict warnings and aggressive optimization for hardware I/O
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -O3)
endif()

# DEPENDENCIES: ROS 2 core framework and standard interface messages
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

# TESTING: Automatic code quality linters configuration
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

# TARGET: Build the main hardware bridge binary
add_executable(esp32_bridge src/esp32_bridge.cpp)

# CRITICAL / INCLUDE PATHS: Required for resolving headers inside include/tracked_hardware/
target_include_directories(esp32_bridge PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# LINKING: Attach ROS 2 dependencies and include directories
ament_target_dependencies(esp32_bridge
  rclcpp
  geometry_msgs
  sensor_msgs
)

# INSTALL: Install executable to package lib directory (required by ros2 run and launch files)
install(TARGETS
  esp32_bridge
  DESTINATION lib/${PROJECT_NAME}
)

# INSTALL: Export headers if other C++ packages link against tracked_hardware
install(DIRECTORY include/
  DESTINATION include
)

ament_package()