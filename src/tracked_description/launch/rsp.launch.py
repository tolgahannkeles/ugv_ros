"""robot_state_publisher: URDF'i /robot_description olarak yayınlar, sabit TF'leri kurar."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    xacro_file = os.path.join(
        get_package_share_directory('tracked_description'), 'urdf', 'tracked_ugv.urdf.xacro')

    robot_description = ParameterValue(
        Command([
            'xacro ', xacro_file,
            ' sim_mode:=', LaunchConfiguration('sim_mode'),
            ' use_lidar:=', LaunchConfiguration('use_lidar'),
            ' use_mock_hardware:=', LaunchConfiguration('use_mock_hardware'),
            ' serial_port:=', LaunchConfiguration('serial_port'),
            ' baudrate:=', LaunchConfiguration('baudrate'),
        ]),
        value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('sim_mode', default_value='false',
                              description='true: Gazebo eklentileri ve gz_ros2_control'),
        DeclareLaunchArgument('use_lidar', default_value='false'),
        DeclareLaunchArgument('use_mock_hardware', default_value='false',
                              description='true: ESP32 yerine mock_components (donanimsiz test)'),
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyAMA0',
                              description='ESP32 UART portu (Pi 5 GPIO 14/15)'),
        DeclareLaunchArgument('baudrate', default_value='115200'),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }]
        ),
    ])
