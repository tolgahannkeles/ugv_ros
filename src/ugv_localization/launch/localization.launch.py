"""Çift EKF + navsat_transform (robot_localization)."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ekf_config = os.path.join(
        get_package_share_directory('ugv_localization'), 'config', 'ekf.yaml')
    use_sim_time = {'use_sim_time': LaunchConfiguration('use_sim_time')}
    # Ortama özel ayarlar (ör. gerçek robotta navsat yaw ofseti) ortak config'in üstüne yazılır
    overrides = LaunchConfiguration('override_params')

    ekf_local = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_local',
        output='screen',
        parameters=[ekf_config, overrides, use_sim_time],
        remappings=[('odometry/filtered', '/odometry/local')]
    )

    ekf_global = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_global',
        output='screen',
        parameters=[ekf_config, overrides, use_sim_time],
        remappings=[('odometry/filtered', '/odometry/global')]
    )

    navsat_transform = Node(
        package='robot_localization',
        executable='navsat_transform_node',
        name='navsat_transform',
        output='screen',
        parameters=[ekf_config, overrides, use_sim_time],
        remappings=[
            ('imu', '/imu/data'),
            ('gps/fix', '/gps/fix'),
            ('odometry/filtered', '/odometry/global'),
            ('odometry/gps', '/odometry/gps'),
            ('gps/filtered', '/gps/filtered'),
        ]
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'override_params', default_value=ekf_config,
            description='ekf.yaml ustune yazilacak ek parametre dosyasi'),
        ekf_local,
        ekf_global,
        navsat_transform,
    ])
