"""Modeli RViz'de incelemek için: robot_state_publisher + joint_state_publisher_gui + RViz."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_desc = get_package_share_directory('ugv_description')

    rsp = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_desc, 'launch', 'rsp.launch.py')),
        launch_arguments={'use_lidar': LaunchConfiguration('use_lidar')}.items()
    )

    joint_state_pub_gui = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        output='screen'
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(pkg_desc, 'rviz', 'ugv.rviz')]
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_lidar', default_value='false'),
        rsp,
        joint_state_pub_gui,
        rviz_node
    ])
