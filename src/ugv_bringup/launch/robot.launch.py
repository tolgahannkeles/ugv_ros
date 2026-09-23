"""Gerçek robot (Raspberry Pi 5 + ESP32).

Simülasyonla (ugv_gazebo/sim.launch.py) aynı katmanlar kullanılır; fark sadece
ros2_control donanım plugin'i ve gerçek robota özel parametre dosyalarıdır:

  web (/cmd_vel_teleop_raw) -> collision_guard -> twist_mux -> /cmd_vel
  -> diff_drive_controller -> ugv_hardware/ESP32System -> UART -> ESP32

  ESP32 -> /imu/data_raw -> Madgwick -> /imu/data ┐
  ESP32 -> /gps/fix ──────────────────────────────┴-> ugv_localization (EKF)

Kullanım:
  ros2 launch ugv_bringup robot.launch.py
  ros2 launch ugv_bringup robot.launch.py use_mock_hardware:=true use_camera:=false  # PC'de test
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_bringup = get_package_share_directory('ugv_bringup')
    pkg_desc = get_package_share_directory('ugv_description')
    pkg_control = get_package_share_directory('ugv_control')
    pkg_loc = get_package_share_directory('ugv_localization')

    args = [
        DeclareLaunchArgument(
            'use_mock_hardware', default_value='false',
            description='true: ESP32 yerine mock_components (donanimsiz test)'),
        DeclareLaunchArgument(
            'serial_port', default_value='/dev/ttyAMA0', description='ESP32 UART portu'),
        DeclareLaunchArgument('baudrate', default_value='115200'),
        DeclareLaunchArgument(
            'enable_localization', default_value='true',
            description='Madgwick + cift EKF + navsat_transform'),
        DeclareLaunchArgument(
            'use_camera', default_value='true', description='camera_ros (CSI kamera) surucusu'),
    ]

    # ==================== ROBOT MODELİ ====================
    rsp = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_desc, 'launch', 'rsp.launch.py')),
        launch_arguments={
            'use_mock_hardware': LaunchConfiguration('use_mock_hardware'),
            'serial_port': LaunchConfiguration('serial_port'),
            'baudrate': LaunchConfiguration('baudrate'),
        }.items()
    )

    # ==================== ROS2_CONTROL ====================
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        output='screen',
        parameters=[
            os.path.join(pkg_control, 'config', 'controllers.yaml'),
            os.path.join(pkg_bringup, 'config', 'controllers_real.yaml'),
        ],
        remappings=[('~/robot_description', '/robot_description')],
    )

    joint_state_broadcaster = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
        output='screen'
    )
    # Standart topic adları: /cmd_vel (TwistStamped) ve /odom
    diff_drive_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'diff_drive_controller',
            '--controller-ros-args', '-r /diff_drive_controller/cmd_vel:=/cmd_vel',
            '--controller-ros-args', '-r /diff_drive_controller/odom:=/odom',
        ],
        output='screen'
    )
    # Spawner'lar controller_manager hazır olana kadar kendileri bekler
    spawn_controllers = [joint_state_broadcaster, diff_drive_controller]

    # ==================== LOCALIZATION ====================
    # Ham IMU'dan (yönelimsiz) yönelim hesaplar: /imu/data_raw -> /imu/data
    madgwick = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter',
        output='screen',
        parameters=[{
            'use_mag': False,
            'publish_tf': False,
            'world_frame': 'enu',
            'fixed_frame': 'odom',
            'gain': 0.01,               # Düşük kazanç gyro gürültüsünü sönümler (varsayılan: 0.1)
            'do_bias_estimation': True  # Robot dururken gyro kaymasını hesaplar ve sıfırlar
        }],
        remappings=[('imu/data_raw', '/imu/data_raw'), ('imu/data', '/imu/data')],
        condition=IfCondition(LaunchConfiguration('enable_localization'))
    )

    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_loc, 'launch', 'localization.launch.py')),
        launch_arguments={
            'override_params': os.path.join(pkg_bringup, 'config', 'localization_real.yaml'),
        }.items(),
        condition=IfCondition(LaunchConfiguration('enable_localization'))
    )

    # ==================== KOMUT ZİNCİRİ ====================
    twist_mux = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        output='screen',
        parameters=[os.path.join(pkg_control, 'config', 'twist_mux.yaml')],
        remappings=[('cmd_vel_out', '/cmd_vel')]
    )

    # SAFETY: PC'deki YOLO tespitine göre manuel sürüş sırasında çarpmayı önleyen filtre
    collision_guard = Node(
        package='ugv_intelligence',
        executable='collision_guard',
        name='collision_guard',
        output='screen',
        respawn=True,
        respawn_delay=2.0,
        parameters=[{'obstacle_timeout_sec': 1.0, 'use_stamped': True}]
    )

    # ==================== KAMERA ====================
    # HARDWARE / CSI: Libcamera driver for Raspberry Pi 5 RP1-CFE architecture
    camera = Node(
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
            'frame_id': 'camera_link_optical',
        }],
        condition=IfCondition(LaunchConfiguration('use_camera'))
    )

    # ==================== WEB ARAYÜZÜ ====================
    web = [
        # MJPEG kamera yayını
        Node(
            package='web_video_server',
            executable='web_video_server',
            name='web_video_server',
            output='screen',
            parameters=[{'port': 8080}]
        ),
        # roslibjs için WebSocket köprüsü
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen',
            parameters=[{'port': 9090}]
        ),
        # Statik arayüz (HTML/JS/Leaflet)
        Node(
            package='ugv_web',
            executable='web_server',
            name='web_server_node',
            output='screen',
            parameters=[{'port': 8000}]
        ),
    ]

    return LaunchDescription(
        args
        + [rsp, controller_manager]
        + spawn_controllers
        + [madgwick, localization, twist_mux, collision_guard, camera]
        + web
    )
