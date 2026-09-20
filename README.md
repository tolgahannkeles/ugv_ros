# UGV ROS — Tracked Tactical Ground Vehicle

A ROS 2-based software stack for a tracked (skid-steer) unmanned ground vehicle (UGV). The system runs on a **Raspberry Pi 5**, shares motion control with an **ESP32** over a serial link, and provides a browser-based **tactical command panel** (live camera feed, map, IMU/GPS telemetry, and joystick control).

## Architecture Overview

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
                          │  /cmd_vel_teleop_raw, /imu, /gps, /camera
                ┌─────────▼────────────┐
                │  collision_guard      │◄── /obstacle_zones (PC, YOLO) + /assist_enabled (web)
                │ (tracked_intelligence)│
                └─────────┬────────────┘
                          │ /cmd_vel_teleop
                ┌─────────▼────────────┐
                │      twist_mux       │  (/cmd_vel_teleop, /cmd_vel_auto, /e_stop)
                └─────────┬────────────┘
                          │ /cmd_vel
                ┌─────────▼────────────┐
                │  tracked_hardware     │  UART (binary protocol)
                │  esp32_bridge (C++)   │◄────────────► ESP32 (motor driver)
                └───────────────────────┘
```

The fully autonomous depth estimation + obstacle avoidance nodes in `tracked_intelligence` (`depth_node`, `avoidance_node`) exist in code but are currently **disabled** in the main launch file. Instead, the lightweight `collision_guard` node in the same package provides **driver-assisted collision avoidance** (see below), which is active.

## Packages (`src/`)

| Package | Build type | Status | Description |
|---|---|---|---|
| [tracked_bringup](src/tracked_bringup) | ament_python | Active | System-wide launch files and configuration (`robot.launch.py`, parameter YAMLs) |
| [tracked_hardware](src/tracked_hardware) | ament_cmake (C++) | Active | Hardware bridge communicating with the ESP32 over UART (`esp32_bridge`) |
| [tracked_intelligence](src/tracked_intelligence) | ament_python | Partially active | `collision_guard` (active, collision avoidance) + ONNX depth estimation/autonomous avoidance (code ready, disabled in launch) |
| [ugv_web](src/ugv_web) | ament_python | Active | Web UI server and static files (control panel) |

### tracked_bringup

Hosts the launch file and shared parameter files that bring up the whole robot with a single command.

- **`launch/robot.launch.py`** starts the following nodes:
  - `esp32_bridge` (tracked_hardware) — hardware bridge
  - `twist_mux` — velocity command arbiter
  - `collision_guard` (tracked_intelligence) — driver-assisted collision avoidance filter
  - `camera_ros` — camera driver
  - `web_video_server` — MJPEG stream from the camera
  - `rosbridge_websocket` — WebSocket bridge for the web UI
  - `ugv_web` `web_server` — static frontend server
  - *(disabled)* `depth_node`, `avoidance_node` — fully autonomous obstacle avoidance
- **`config/robot_params.yaml`** — serial port (`/dev/ttyAMA0`), baud rate (115200), track width (0.22 m), slip factor (1.25), IMU/GPS frame IDs.
- **`config/twist_mux.yaml`** — `/cmd_vel_teleop` (priority 100), `/cmd_vel_auto` (priority 50), `/e_stop` lock (priority 255); output is remapped to `/cmd_vel`.

### tracked_hardware

A C++ `esp32_bridge` node that manages UART communication between the Raspberry Pi and the ESP32.

- Converts `/cmd_vel` (Twist) messages into left/right track speeds using skid-steer kinematics and sends them to the ESP32 over a custom binary protocol.
- Publishes `/imu/data_raw` (sensor_msgs/Imu) and `/gps/fix` (sensor_msgs/NavSatFix) from data received from the ESP32.
- `include/tracked_hardware/protocol.hpp` — a simple checksummed, state-machine-based frame protocol.
- `include/tracked_hardware/uart_driver.hpp` — a POSIX `termios`-based serial port driver. **Linux-only** (Raspberry Pi OS); it does not build/run elsewhere.

### tracked_intelligence

Hosts two separate approaches to camera-based environment awareness.

**`collision_guard` (active) — Driver-Assisted Collision Avoidance**

Not full autonomous navigation; it's a safety filter that prevents collisions with nearby obstacles while driving manually via joystick. It requires no extra hardware (IMU/GPS/lidar); distance estimation is done by **YOLO26's native monocular depth estimation (`yolo26n-depth.pt`)** running on a separate **PC** that can reach the robot's camera over the ROS network — it produces an absolute distance in meters for every pixel.

- Joystick/keyboard commands from the web UI are no longer published directly to `twist_mux`; they go to the `/cmd_vel_teleop_raw` topic instead.
- The `collision_guard` node listens to this raw command; if the web UI's **"Autonomous Assist"** toggle is on via `/assist_enabled` (`std_msgs/Bool`) and the `/obstacle_zones` signal from the PC (`std_msgs/Int32MultiArray`, `[left, center, right]`, each 0/1) reports an obstacle in a zone the robot is driving into, it **cuts forward motion** (turning/reverse remain free) and publishes the adjusted command to `/cmd_vel_teleop` — `twist_mux` continues to operate unchanged downstream.
- If `/obstacle_zones` data is older than `obstacle_timeout_sec` (default 1.0 s), it is treated as if there's no obstacle — so if the PC/YOLO side drops off the network, joystick control continues uninterrupted.
- The current intervention state is published as `/assist/blocking` (`std_msgs/Bool`) and visualized in the web UI by the toggle turning red.
- Example depth→ROS bridge script to run on the PC: [tools/pc_obstacle_detector.py](tools/pc_obstacle_detector.py) (this script is not part of the Pi's colcon workspace; it runs on a separate machine). It splits the depth map into left/center/right zones and compares the nearest (low-percentile) distance in each zone against the `--near-distance` threshold (default 1.2 m).
- By default (`--show`, disable with `--no-show`) the script overlays each zone's obstacle status and estimated distance on the camera feed and displays it live in an OpenCV window — useful for visually tuning the threshold.

**`depth_node` / `avoidance_node` (code ready, disabled in launch) — Fully Autonomous Avoidance**

- `depth_node` — processes `/camera/image_raw` with an embedded ONNX model (`models/depth_model.onnx`, MiDaS v2.1 Small) on the CPU and publishes `/depth/image_raw`.
- `avoidance_node` — splits the depth image into left/center/right zones and produces a turn/forward decision on `/cmd_vel_auto`.
- This pair requires additional IMU/GPS/lidar integration for fully autonomous driving, so it's currently commented out in `robot.launch.py`.

### ugv_web

Serves the browser-based **"UGV Tactical Command Station"** control panel.

- The `web_server` node serves the `www/` folder as static files over a simple HTTP server (default port `8000`).
- `www/index.html` is a single-page, dark-themed tactical interface:
  - Live MJPEG camera feed from `web_video_server`
  - WebSocket connection to ROS via `rosbridge` (roslibjs)
  - Artificial horizon and yaw/heading estimation from IMU data
  - A live Leaflet mini-map with GPS-based position and trail drawing
  - On-screen joystick + WASD keyboard control, adjustable power percentage, publishing to `/cmd_vel_teleop_raw` every 50 ms (forwarded to `/cmd_vel_teleop` via `collision_guard`)
  - **"Autonomous Assist"** toggle — turns the collision avoidance filter on/off (see [tracked_intelligence](#tracked_intelligence))
  - Emergency stop button / SPACE key (**note:** currently only zeroes velocity commands; it does not trigger `twist_mux`'s `/e_stop` lock — see [Known Gaps](#known-gaps-and-todos))

## Requirements

- ROS 2 (colcon workspace layout)
- Python 3, `onnxruntime`, `cv_bridge`
- ROS 2 packages that must be installed system-wide (not included in this repo): `twist_mux`, `camera_ros`, `web_video_server`, `rosbridge_server`
- `tracked_hardware` only builds on Linux (POSIX `termios`) — development/testing requires a Raspberry Pi or Linux machine.
- For **Autonomous Assist**, a separate PC on the same ROS network (same `ROS_DOMAIN_ID`) as the robot needs `ultralytics` (YOLO26 depth) and `opencv-python` installed — see [tools/pc_obstacle_detector.py](tools/pc_obstacle_detector.py). Images are decoded directly with numpy without requiring `cv_bridge`; either a raw (`sensor_msgs/Image`) or compressed (`sensor_msgs/CompressedImage`) camera topic can be used.

## Setup and Running

```bash
# From the workspace root
colcon build
source install/setup.bash

# Bring up the whole system
ros2 launch tracked_bringup robot.launch.py
```

Access the web UI at: `http://<robot-ip>:8000`

For Autonomous Assist (collision avoidance), on a PC on the same ROS network:

```bash
python3 tools/pc_obstacle_detector.py
```

then enable the **"Autonomous Assist"** toggle in the web UI.

## Known Gaps and Todos

- The emergency stop button in the web UI does not publish to the `/e_stop` topic; it needs to be integrated with the `twist_mux` lock.
- `collision_guard` cuts forward motion whenever any of the three zones reports an obstacle, regardless of turn direction (not direction-aware or gradual) — kept intentionally simple for this first version.
- The fully autonomous depth estimation and obstacle avoidance nodes in `tracked_intelligence` are kept disabled in the launch file for now.
