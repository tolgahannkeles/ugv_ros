import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_bringup = get_package_share_directory('tracked_bringup')
    param_file = os.path.join(pkg_bringup, 'config', 'robot_params.yaml')
    twist_mux_file = os.path.join(pkg_bringup, 'config', 'twist_mux.yaml')

    # ROBOTICS / HARDWARE: ESP32 bidirectional bridge (UART <-> ROS 2 topics)
    esp32_bridge_node = Node(
        package='tracked_hardware',
        executable='esp32_bridge',
        name='esp32_bridge',
        output='screen',
        respawn=True,
        respawn_delay=2.0,
        parameters=[param_file]
    )
    """
    # CONTROL / MULTIPLEXER: Priority-based velocity arbiter (Teleop > Autonomous > Lock)
    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        output='screen',
        parameters=[twist_mux_file],
        remappings=[('cmd_vel_out', '/cmd_vel')]
    )

    
    # 4. INTELLIGENCE: ONNX Monocular Depth Estimation (MiDaS v2.1 Small)
    depth_node = Node(
        package='tracked_intelligence',
        executable='depth_node',
        name='depth_node',
        output='screen',
        parameters=[{
            'input_width': 256,
            'input_height': 256,
            'skip_frames': 1
        }]
    )

    # 5. INTELLIGENCE: Sektörel Engelden Kaçınma (/cmd_vel_auto basar)
    avoidance_node = Node(
        package='tracked_intelligence',
        executable='avoidance_node',
        name='avoidance_node',
        output='screen',
        parameters=[{
            'safe_threshold': 0.60,
            'forward_speed': 0.45,
            'turn_speed': 1.20
        }]
    )
    """
    # HARDWARE / CSI: Libcamera driver for Raspberry Pi 5 RP1-CFE architecture
    camera_node = Node(
        package='camera_ros',
        executable='camera_node',
        name='camera',
        output='screen',
        parameters=[{
            'camera': 0,
            'width': 640,
            'height': 480,
            'format': 'BGR888',
            'framerate': 60.0,
        }]
    )

    # WEB / STREAMING: Converts ROS image topic to browser-compatible MJPEG over HTTP
    web_video_node = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        output='screen',
        parameters=[{'port': 8080}]
    )

    # WEB / TELEOP: JSON WebSocket bridge for roslibjs (topics/services/actions)
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        output='screen',
        parameters=[{'port': 9090}]
    )

    # WEB / HOSTING: Serves static GCS frontend assets (HTML/JS/Leaflet)
    web_server_node = Node(
        package='ugv_web',
        executable='web_server',
        name='web_server_node',
        output='screen',
        parameters=[{'port': 8000}]
    )

    return LaunchDescription([
        esp32_bridge_node,
        twist_mux_node,
        depth_node,
        avoidance_node,
        camera_node,
        web_video_node,
        rosbridge_node,
        web_server_node
    ])