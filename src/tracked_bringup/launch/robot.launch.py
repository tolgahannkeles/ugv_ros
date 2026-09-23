import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_bringup = get_package_share_directory('tracked_bringup')
    param_file = os.path.join(pkg_bringup, 'config', 'robot_params.yaml')
    twist_mux_file = os.path.join(pkg_bringup, 'config', 'twist_mux.yaml')
    localization_launch_file = os.path.join(pkg_bringup, 'launch', 'localization.launch.py')

    # ARGUMENT: Konumlandırma katmanını isteğe bağlı açıp/kapatma (varsayılan: true)
    enable_localization_arg = DeclareLaunchArgument(
        'enable_localization',
        default_value='true',
        description='Madgwick, Navsat ve EKF dugumlerini baslatir'
    )

    # LOCALIZATION: localization.launch.py alt yapısını dahil etme
    localization_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(localization_launch_file),
        condition=IfCondition(LaunchConfiguration('enable_localization'))
    )

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
    
    # CONTROL / MULTIPLEXER: Priority-based velocity arbiter (Teleop > Autonomous > Lock)
    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        output='screen',
        parameters=[twist_mux_file],
        remappings=[('cmd_vel_out', '/cmd_vel')]
    )

    # SAFETY: PC'deki YOLO tespitine gore manuel surus sirasinda carpmayi onleyen filtre
    collision_guard_node = Node(
        package='tracked_intelligence',
        executable='collision_guard',
        name='collision_guard',
        output='screen',
        respawn=True,
        respawn_delay=2.0,
        parameters=[{'obstacle_timeout_sec': 1.0}]
    )

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
        enable_localization_arg,
        localization_launch,
        esp32_bridge_node,
        twist_mux_node,
        collision_guard_node,
        camera_node,
        web_video_node,
        rosbridge_node,
        web_server_node
    ])