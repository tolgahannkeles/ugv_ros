import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_bringup = get_package_share_directory('tracked_bringup')
    param_file = os.path.join(pkg_bringup, 'config', 'robot_params.yaml')

   # 1. ESP32 Köprüsü
    esp32_bridge_node = Node(
        package='tracked_hardware',
        executable='esp32_bridge',
        name='esp32_bridge',
        output='screen',
        parameters=[param_file]
    )

    # 2. Raspberry Pi 5 CSI Kamera Düğümü (camera_ros)
    camera_node = Node(
        package='camera_ros',
        executable='camera_node',
        name='camera',
        output='screen',
        parameters=[{
            'width': 640,
            'height': 480,
            'format': 'BGR888',   # Web video server ve OpenCV için standart
            'framerate': 30.0
        }],
        remappings=[
            # camera_ros varsayılan olarak /camera/image_raw yayınlar
            ('/camera/image_raw', '/camera/image_raw')
        ]
    )

    # 3. Web Video Server (HTTP MJPEG Stream, Port 8080)
    web_video_node = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        output='screen',
        parameters=[{'port': 8080}]
    )

    # 4. Rosbridge WebSocket (Port 9090)
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        output='screen',
        parameters=[{'port': 9090}]
    )

    # 5. Web UI Sunucusu (Port 8000)
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