import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_bringup = get_package_share_directory('tracked_bringup')
    param_file = os.path.join(pkg_bringup, 'config', 'robot_params.yaml')

    # 1. ESP32 Donanım Köprüsü (UART)
    esp32_bridge_node = Node(
        package='tracked_hardware',
        executable='esp32_bridge',
        name='esp32_bridge',
        output='screen',
        parameters=[param_file]
    )

    # 2. Kamera Düğümü (ROS 2 Standart Kamera Yayını)
    camera_node = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        output='screen',
        parameters=[{
            'video_device': '/dev/video0',
            'image_size': [640, 480],
            'time_per_frame': [1, 30]
        }]
    )

    # 3. Web Video Server (ROS Image -> HTTP MJPEG çevirici, Port 8080)
    web_video_node = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        output='screen',
        parameters=[{'port': 8080}]
    )

    # 4. Rosbridge WebSocket (Tarayıcı -> ROS 2 Topic Köprüsü, Port 9090)
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        output='screen',
        parameters=[{'port': 9090}]
    )

    # 5. Web UI Sunucusu (HTML Arayüzü, Port 8000)
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