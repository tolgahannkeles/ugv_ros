# UGV ROS — Tracked Tactical Ground Vehicle

A ROS 2 (Jazzy) software stack for a tracked (skid-steer) unmanned ground vehicle (UGV). The robot runs on a **Raspberry Pi 5**, drives its tracks through an **ESP32** over a serial link, and provides a browser-based **tactical command panel** (live camera feed, map, IMU/GPS telemetry, and joystick control). The same stack runs in a **Gazebo Harmonic** simulation.

## Architecture Overview

The real robot and the simulation share every layer except the ros2_control hardware plugin and the sensor source:

```
                ┌──────────────────────┐
                │     Web Frontend     │  (browser, roslibjs + Leaflet)
                │   ugv_web / www      │
                └─────────┬────────────┘
                    WS 9090 │ MJPEG 8080
                ┌─────────▼────────────┐
                │ rosbridge_websocket  │
                │ web_video_server     │
                │ ugv_web/web_server   │
                └─────────┬────────────┘
                          │  /cmd_vel_teleop_raw (Twist)
                ┌─────────▼────────────┐
                │  collision_guard      │◄── /obstacle_zones (PC, YOLO) + /assist_enabled (web)
                │ (tracked_intelligence)│
                └─────────┬────────────┘
                          │ /cmd_vel_teleop (TwistStamped)
                ┌─────────▼────────────┐
                │      twist_mux       │  (/cmd_vel_teleop, /cmd_vel_auto, /e_stop)
                └─────────┬────────────┘
                          │ /cmd_vel (TwistStamped)
                ┌─────────▼─────────────┐
                │ diff_drive_controller │  ros2_control (tracked_control)
                └─────────┬─────────────┘
                          │ wheel velocity commands
          ┌───────────────┴────────────────┐
┌─────────▼──────────────┐     ┌───────────▼──────────────┐
│ tracked_hardware/      │     │ gz_ros2_control/         │
│ ESP32System (UART)     │     │ GazeboSimSystem          │
│   ◄──► ESP32           │     │   ◄──► Gazebo            │
└────────────────────────┘     └──────────────────────────┘
        real robot                      simulation

IMU + GPS ──► /imu/data, /gps/fix ──► tracked_localization
              (ekf_local: odom→base_footprint, ekf_global + navsat_transform: map→odom)
```

TF tree (REP-105): `map → odom → base_footprint → base_link → sensors`.

The fully autonomous depth estimation + obstacle avoidance nodes in `tracked_intelligence` (`depth_node`, `avoidance_node`) exist in code but are **disabled**. Instead, the lightweight `collision_guard` node provides **driver-assisted collision avoidance** (see below).

## Packages (`src/`)

| Package | Build type | Description |
|---|---|---|
| [tracked_description](src/tracked_description) | ament_cmake | URDF (xacro) of the tracked chassis: 3 wheels per side, only the rear sprocket is driven and the front/middle wheels follow it through the track (`<mimic>`). `ros2_control.xacro` (Gazebo / mock / ESP32 hardware), `gazebo.xacro` (sensors with noise). `rsp.launch.py`, `display.launch.py`, RViz config |
| [tracked_control](src/tracked_control) | ament_cmake | `controllers.yaml` (`diff_drive_controller`, `joint_state_broadcaster`), `twist_mux.yaml` (TwistStamped). Shared by the robot and the simulation |
| [tracked_localization](src/tracked_localization) | ament_cmake | robot_localization dual EKF + `navsat_transform` (`ekf.yaml`, `localization.launch.py`) |
| [tracked_hardware](src/tracked_hardware) | ament_cmake (C++) | ros2_control plugin `tracked_hardware/ESP32System`: ESP32 UART protocol, track commands, IMU/GPS telemetry |
| [tracked_bringup](src/tracked_bringup) | ament_python | Real robot: `robot.launch.py` and robot-specific parameter overrides |
| [tracked_gazebo](src/tracked_gazebo) | ament_cmake | Simulation: world, `gz_bridge.yaml`, `sim.launch.py`, `gps_driver.py` |
| [tracked_intelligence](src/tracked_intelligence) | ament_python | `collision_guard` (active) + ONNX depth estimation/autonomous avoidance (disabled) |
| [ugv_web](src/ugv_web) | ament_python | Web UI server and static files (control panel) |

### tracked_bringup (real robot)

`launch/robot.launch.py` starts:

- `robot_state_publisher` with the URDF (`tracked_description/rsp.launch.py`)
- `ros2_control_node` with `tracked_control/config/controllers.yaml` plus `config/controllers_real.yaml`, and spawners for `joint_state_broadcaster` and `diff_drive_controller`
- `imu_filter_madgwick` (`/imu/data_raw` → `/imu/data`) and `tracked_localization` with `config/localization_real.yaml`
- `twist_mux`, `collision_guard` (`use_stamped: true`), `camera_ros`, `web_video_server`, `rosbridge_websocket`, `ugv_web`

Robot-specific overrides (only the differences from the shared config):

- **`config/controllers_real.yaml`**: track width 0.22 m × slip factor 1.25 (`wheel_separation_multiplier`), `open_loop: true` because the ESP32 reports no encoder data.
- **`config/localization_real.yaml`**: the IMU has no magnetometer, so the Madgwick yaw is relative to the start-up heading. `navsat_transform` assumes the robot starts facing north (`yaw_offset: π/2`, `magnetic_declination_radians: 0.10`).

Arguments: `serial_port` (default `/dev/ttyAMA0`), `baudrate` (115200), `use_mock_hardware` (test without an ESP32), `enable_localization`, `use_camera`.

### tracked_hardware

`tracked_hardware/ESP32System` is a ros2_control `SystemInterface` that owns the UART link to the ESP32.

- **Commands:** wheel velocities from `diff_drive_controller` (rad/s) × `wheel_radius` → track speeds (m/s), scaled proportionally to a 0.6 m/s limit so the turning radius is preserved, and sent as `CmdVelPayload` at the controller rate (50 Hz). On deactivation the tracks are stopped.
- **State:** the ESP32 sends no encoder data, so the wheel states mirror the commands (open loop), and `/odom` is command-based.
- **Telemetry:** a receive thread parses ESP32 packets and publishes `/imu/data_raw` (no orientation), `/imu/temperature`, `/gps/fix` (covariance from HDOP) and `/gps/fix_velocity`.
- Hardware parameters come from the URDF (`serial_port`, `baudrate`, `wheel_radius`, `max_track_speed`, `imu_frame_id`, `gps_frame_id`).
- `include/tracked_hardware/protocol.hpp`: a checksummed, state-machine-based frame protocol. `include/tracked_hardware/uart_driver.hpp`: a POSIX `termios` serial driver, **Linux-only**.

### tracked_intelligence

Hosts two separate approaches to camera-based environment awareness.

**`collision_guard` (active): Driver-Assisted Collision Avoidance**

This is not full autonomous navigation. It is a safety filter that prevents collisions with nearby obstacles while driving manually via joystick. It requires no extra hardware (IMU/GPS/lidar); distance estimation is done by **YOLO26's native monocular depth estimation (`yolo26n-depth.pt`)** running on a separate **PC** that can reach the robot's camera over the ROS network. It produces an absolute distance in meters for every pixel.

- Joystick/keyboard commands from the web UI go to the `/cmd_vel_teleop_raw` topic.
- The `collision_guard` node listens to this raw command. If the web UI's **"Autonomous Assist"** toggle is on (`/assist_enabled`, `std_msgs/Bool`) and the `/obstacle_zones` signal from the PC (`std_msgs/Int32MultiArray`, `[left, center, right]`, each 0/1) reports an obstacle in a zone the robot is driving into, it **cuts forward motion** (turning/reverse remain free) and publishes the adjusted command to `/cmd_vel_teleop`. With `use_stamped: true` (robot and simulation), it publishes `TwistStamped` for `twist_mux` and `diff_drive_controller`.
- If `/obstacle_zones` data is older than `obstacle_timeout_sec` (default 1.0 s), it is treated as if there's no obstacle, so if the PC/YOLO side drops off the network, joystick control continues uninterrupted.
- The current intervention state is published as `/assist/blocking` (`std_msgs/Bool`) and visualized in the web UI by the toggle turning red.
- Example depth→ROS bridge script to run on the PC: [tools/pc_obstacle_detector.py](tools/pc_obstacle_detector.py) (not part of the colcon workspace; it runs on a separate machine). It splits the depth map into left/center/right zones and compares the nearest (low-percentile) distance in each zone against the `--near-distance` threshold (default 1.2 m).
- By default (`--show`, disable with `--no-show`) the script overlays each zone's obstacle status and estimated distance on the camera feed and displays it live in an OpenCV window, which is useful for visually tuning the threshold.

**`depth_node` / `avoidance_node` (code ready, disabled): Fully Autonomous Avoidance**

- `depth_node` processes `/camera/image_raw` with an embedded ONNX model (`models/depth_model.onnx`, MiDaS v2.1 Small) on the CPU and publishes `/depth/image_raw`.
- `avoidance_node` splits the depth image into left/center/right zones and produces a turn/forward decision on `/cmd_vel_auto`. It still publishes `Twist`; it must switch to `TwistStamped` before it is enabled with the stamped `twist_mux`.

### ugv_web

Serves the browser-based **"UGV Tactical Command Station"** control panel.

- The `web_server` node serves the `www/` folder as static files over a simple HTTP server (default port `8000`).
- `www/index.html` is a single-page, dark-themed tactical interface:
  - Live MJPEG camera feed from `web_video_server`
  - WebSocket connection to ROS via `rosbridge` (roslibjs)
  - Artificial horizon and yaw/heading estimation from `/imu/data`
  - A live Leaflet mini-map with GPS-based position and trail drawing
  - On-screen joystick + WASD keyboard control, adjustable power percentage, publishing to `/cmd_vel_teleop_raw` every 50 ms while active (then three zero commands on release)
  - **"Autonomous Assist"** toggle, which turns the collision avoidance filter on/off (see [tracked_intelligence](#tracked_intelligence))
  - Emergency stop button / SPACE key (**note:** currently only zeroes velocity commands; it does not trigger `twist_mux`'s `/e_stop` lock; see [Known Gaps](#known-gaps-and-todos))

## Requirements

**Full environment setup (PC simulation and Raspberry Pi), versions and troubleshooting: [docs/SETUP.md](docs/SETUP.md).** Both machines can be set up with `tools/setup/setup_pc_sim.sh` and `tools/setup/setup_robot.sh`.

- Ubuntu 24.04 + ROS 2 Jazzy (on Windows: WSL2), colcon
- ROS 2 packages: `ros2_control`, `ros2_controllers` (`diff_drive_controller`, `joint_state_broadcaster`), `twist_mux`, `robot_localization`, `imu_filter_madgwick`, `web_video_server`, `rosbridge_server`, `xacro`; on the robot also `camera_ros`; for simulation also `ros_gz`, `gz_ros2_control`
- Python 3, `onnxruntime`, `cv_bridge` (for `tracked_intelligence`)
- `tracked_hardware` builds on Linux only (POSIX `termios`).
- For **Autonomous Assist**, a separate PC on the same ROS network (same `ROS_DOMAIN_ID`) needs `ultralytics` (YOLO26 depth) and `opencv-python`; see [tools/pc_obstacle_detector.py](tools/pc_obstacle_detector.py). Images are decoded directly with numpy without requiring `cv_bridge`; either a raw (`sensor_msgs/Image`) or compressed (`sensor_msgs/CompressedImage`) camera topic can be used.

```bash
sudo apt install python3-colcon-common-extensions \
  ros-jazzy-ros2-control ros-jazzy-ros2-controllers ros-jazzy-ros2controlcli \
  ros-jazzy-twist-mux ros-jazzy-robot-localization ros-jazzy-imu-filter-madgwick \
  ros-jazzy-web-video-server ros-jazzy-rosbridge-server ros-jazzy-xacro
# Simulation only
sudo apt install ros-jazzy-ros-gz ros-jazzy-gz-ros2-control
```

**Temporary overlay:** `diff_drive_controller` 4.42.1 (apt) logs "Velocity command timed out" every second while idle; the upstream jazzy branch only logs on the transition. Build it as an underlay and delete `~/ugv_deps_ws` once apt ships a newer version:

```bash
mkdir -p ~/ugv_deps_ws/src && cd ~/ugv_deps_ws/src
git clone --depth 1 --filter=blob:none --sparse -b jazzy https://github.com/ros-controls/ros2_controllers.git
(cd ros2_controllers && git sparse-checkout set diff_drive_controller)
cd ~/ugv_deps_ws && colcon build --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
```

## Real Robot

```bash
source ~/ugv_deps_ws/install/setup.bash
colcon build && source install/setup.bash
ros2 launch tracked_bringup robot.launch.py

# Without an ESP32 (e.g. on a PC): mock hardware, no camera
ros2 launch tracked_bringup robot.launch.py use_mock_hardware:=true use_camera:=false
```

Access the web UI at `http://<robot-ip>:8000`. For Autonomous Assist, run `python3 tools/pc_obstacle_detector.py` on a PC on the same ROS network, then enable the **"Autonomous Assist"** toggle in the web UI.

The controller manager logs a warning if it cannot use FIFO real-time scheduling. On the Pi, add the user to a group with real-time privileges (see the [ros2_control docs](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/userdoc.html#determinism)).

## Simulation (Gazebo Harmonic, WSL2 Ubuntu 24.04)

`tracked_gazebo/launch/sim.launch.py` runs the same layers as the robot. `gz_ros2_control` replaces the ESP32 hardware plugin, and `ros_gz_bridge` provides the sensors.

- **Tracked model:** each side has three wheels (front, middle, rear sprocket). ros2_control drives only the two sprockets, as on the real robot (one motor per track); `gz_ros2_control` couples the front and middle wheels to the sprocket through their `<mimic>` joints, which stands in for the track. Turning is skid-steer: the tracks slide sideways, so `wheel_separation_multiplier: 1.51` in `controllers.yaml` was measured in the simulation (in-place turn, true yaw / odometry yaw ≈ 1.0).
- **Sensor contract:** camera, IMU (with ENU orientation) and GPS are required; LiDAR is optional (`use_lidar:=true`). Sensors have Gaussian noise (`tracked_description/urdf/gazebo.xacro`).
- `gps_driver.py` fills the GPS covariance that `ros_gz_bridge` drops, matching the simulated noise.

```bash
# Workspace on the Linux filesystem; src links to the repo on the Windows side
mkdir -p ~/ugv_ws && ln -s /mnt/c/Users/Tolgahan/Desktop/projects/ugv_ros/src ~/ugv_ws/src
source ~/ugv_deps_ws/install/setup.bash
cd ~/ugv_ws && colcon build && source install/setup.bash

ros2 launch tracked_gazebo sim.launch.py                  # with the Gazebo GUI
ros2 launch tracked_gazebo sim.launch.py headless:=true rviz:=true
ros2 launch tracked_description display.launch.py         # model only, in RViz
```

Web UI: `http://localhost:8000`. For Autonomous Assist, run `python3 tools/pc_obstacle_detector.py` alongside the sim; it reads Gazebo's `/camera/image_raw`.

Arguments: `headless`, `use_lidar`, `localization`, `rviz`, `world`, `x`, `y`, `yaw` (spawn pose).

### TEKNOFEST course world

The default world is `tracked_gazebo/worlds/teknofest_2026.sdf`: the TEKNOFEST unmanned ground vehicle course (`PRK26-A-001-001-00`, 49 × 42 m). The robot spawns at the entrance of the upper leg (`x -24.5, y 20`), facing along the course (+x). Along the S-shaped track the course has a steep ramp, speed bumps, a strip-curtain gate, a cone slalom, a step obstacle, a side slope, a gravel pad and a water crossing; separate parallel lanes sit to the north.

The course model (`tracked_gazebo/models/teknofest_ika_parkur`) is generated from the official STEP file in `teknofest_parkur/` by [tools/parkur_to_gazebo.py](tools/parkur_to_gazebo.py). The STEP has no colors, so colors are assigned from product names. Fasteners and other small parts are dropped. Barriers, cones and posts collide as per-part convex hulls; ramps, gravel and ground use their real geometry. The curtain strips, sign plates and floor lines have no collision.

```bash
# One-time converter environment (outside the repo)
python3 -m venv ~/.venvs/cad && ~/.venvs/cad/bin/pip install cadquery-ocp trimesh rtree scipy
# Regenerate the model after the STEP changes
~/.venvs/cad/bin/python tools/parkur_to_gazebo.py teknofest_parkur/20260604_PRK26-A-001-001-00.STEP   src/tracked_gazebo/models/teknofest_ika_parkur
```

The CAD models the water crossing as a solid water body level with the ground, so in the simulation it is a drivable surface at ground level with a translucent water visual. The previous small test world is still available: `world:=.../worlds/test_arena.sdf x:=0 y:=0`.

## Known Gaps and Todos

- The chassis dimensions in the URDF (wheel radius 0.065 m, wheel pitch 0.135 m, hull size) are estimated from a photo; only the track separation (0.22 m) comes from the robot config. Wheel dimensions are defined in both the URDF and `controllers.yaml` and must be kept in sync.
- The ESP32 reports no encoder data; odometry on the real robot is command-based.
- The real IMU has no magnetometer, so the global heading depends on the robot starting facing north.
- The emergency stop button in the web UI does not publish to the `/e_stop` topic; it needs to be integrated with the `twist_mux` lock.
- `collision_guard` cuts forward motion whenever any of the three zones reports an obstacle, regardless of turn direction (not direction-aware or gradual); this is kept intentionally simple for this first version.
- The fully autonomous depth estimation and obstacle avoidance nodes in `tracked_intelligence` are disabled.
