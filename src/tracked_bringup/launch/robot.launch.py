import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_bringup = get_package_share_directory('tracked_bringup')
    param_file = os.path.join(pkg_bringup, 'config', 'robot_params.yaml')

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

    # HARDWARE / CSI: Libcamera driver for Raspberry Pi 5 RP1-CFE architecture
    camera_node = Node(
        package='camera_ros',
        executable='camera_node',
        name='camera',
        output='screen',
        parameters=[{
            'camera': 0,
            'width': 960,       # 16:9 oranı tam FOV sağlar
            'height': 540,
            'format': 'BGR888',
            'framerate': 30.0
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
        camera_node,
        web_video_node,
        rosbridge_node,
        web_server_node
    ])