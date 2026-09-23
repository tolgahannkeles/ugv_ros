"""Tracked UGV Gazebo (Harmonic) simülasyonu.

Komut zinciri:
  web (/cmd_vel_teleop_raw, Twist) -> collision_guard -> /cmd_vel_teleop (TwistStamped)
  -> twist_mux -> /cmd_vel -> diff_drive_controller (gz_ros2_control) -> Gazebo

Sensörler (ros_gz_bridge): /imu/data, /gps/fix, /camera/image_raw, /scan (opsiyonel)
TF (REP-105): map -> odom -> base_footprint -> base_link -> sensörler

Kullanım:
  ros2 launch tracked_gazebo sim.launch.py                       # TEKNOFEST parkuru
  ros2 launch tracked_gazebo sim.launch.py headless:=true rviz:=true use_lidar:=true
  ros2 launch tracked_gazebo sim.launch.py world:=$(ros2 pkg prefix tracked_gazebo)/share/tracked_gazebo/worlds/test_arena.sdf x:=0 y:=0
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument,
                            IncludeLaunchDescription, RegisterEventHandler)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_gazebo = get_package_share_directory('tracked_gazebo')
    pkg_desc = get_package_share_directory('tracked_description')
    pkg_control = get_package_share_directory('tracked_control')
    pkg_loc = get_package_share_directory('tracked_localization')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    world = LaunchConfiguration('world')
    headless = LaunchConfiguration('headless')
    use_lidar = LaunchConfiguration('use_lidar')
    sim_time = {'use_sim_time': True}

    args = [
        DeclareLaunchArgument(
            'world', default_value=os.path.join(pkg_gazebo, 'worlds', 'teknofest_2026.sdf'),
            description='Gazebo dunya (SDF) dosyasi'),
        # Başlangıç: TEKNOFEST parkuru üst kol girişi, parkur yönüne (+x) bakar
        DeclareLaunchArgument('x', default_value='-24.5', description='Dogus konumu x (m)'),
        DeclareLaunchArgument('y', default_value='20.0', description='Dogus konumu y (m)'),
        DeclareLaunchArgument('yaw', default_value='0.0', description='Dogus yonu (rad)'),
        DeclareLaunchArgument(
            'headless', default_value='false',
            description='true: Gazebo arayuzu acilmaz (sensorler yine calisir)'),
        DeclareLaunchArgument(
            'use_lidar', default_value='false', description='Opsiyonel LiDAR sensoru'),
        DeclareLaunchArgument(
            'localization', default_value='true', description='Cift EKF + navsat_transform'),
        DeclareLaunchArgument('rviz', default_value='false', description='RViz2 ac'),
    ]

    # ==================== ROBOT MODELİ ====================
    rsp = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_desc, 'launch', 'rsp.launch.py')),
        launch_arguments={
            'use_sim_time': 'true',
            'sim_mode': 'true',
            'use_lidar': use_lidar,
        }.items()
    )

    # ==================== GAZEBO ====================
    # -r: başlar başlamaz oynat; headless'ta -s: sadece sunucu
    gz_args = [
        '-r ',
        PythonExpression(["'-s --headless-rendering ' if '", headless, "' == 'true' else ''"]),
        world,
    ]
    # Dünyalardaki model:// URI'leri (ör. teknofest_ika_parkur) bu klasörden çözülür
    model_path = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH', os.path.join(pkg_gazebo, 'models'))

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': gz_args, 'on_exit_shutdown': 'true'}.items()
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description', '-name', 'tracked_ugv',
                   '-x', LaunchConfiguration('x'), '-y', LaunchConfiguration('y'), '-z', '0.03',
                   '-Y', LaunchConfiguration('yaw')],
        output='screen'
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': os.path.join(pkg_gazebo, 'config', 'gz_bridge.yaml')},
                    sim_time],
        output='screen'
    )

    gps_driver = Node(
        package='tracked_gazebo',
        executable='gps_driver.py',
        name='gps_driver',
        output='screen',
        parameters=[sim_time]
    )

    # ==================== ROS2_CONTROL ====================
    # Controller'lar robot Gazebo'da doğduktan sonra sırayla yüklenir
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
    spawn_controllers = [
        RegisterEventHandler(OnProcessExit(
            target_action=spawn_robot, on_exit=[joint_state_broadcaster])),
        RegisterEventHandler(OnProcessExit(
            target_action=joint_state_broadcaster, on_exit=[diff_drive_controller])),
    ]

    # ==================== LOCALIZATION ====================
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_loc, 'launch', 'localization.launch.py')),
        launch_arguments={'use_sim_time': 'true'}.items(),
        condition=IfCondition(LaunchConfiguration('localization'))
    )

    # ==================== KOMUT ZİNCİRİ ====================
    twist_mux = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        output='screen',
        parameters=[os.path.join(pkg_control, 'config', 'twist_mux.yaml'), sim_time],
        remappings=[('cmd_vel_out', '/cmd_vel')]
    )

    collision_guard = Node(
        package='tracked_intelligence',
        executable='collision_guard',
        name='collision_guard',
        output='screen',
        parameters=[{'obstacle_timeout_sec': 1.0, 'use_stamped': True}, sim_time]
    )

    # ==================== WEB ARAYÜZÜ ====================
    web = [
        Node(
            package='web_video_server',
            executable='web_video_server',
            name='web_video_server',
            output='screen',
            parameters=[{'port': 8080}]
        ),
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen',
            parameters=[{'port': 9090}]
        ),
        Node(
            package='ugv_web',
            executable='web_server',
            name='web_server_node',
            output='screen',
            parameters=[{'port': 8000}]
        ),
    ]

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(pkg_desc, 'rviz', 'tracked_ugv.rviz')],
        parameters=[sim_time],
        condition=IfCondition(LaunchConfiguration('rviz'))
    )

    return LaunchDescription(
        args
        + [model_path, rsp, gazebo, spawn_robot, bridge, gps_driver]
        + spawn_controllers
        + [localization, twist_mux, collision_guard]
        + web
        + [rviz]
    )
