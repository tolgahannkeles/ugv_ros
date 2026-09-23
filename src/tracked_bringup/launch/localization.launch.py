import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_bringup = get_package_share_directory('tracked_bringup')
    ekf_config_path = os.path.join(pkg_bringup, 'config', 'ekf.yaml')

    # Statik TF 1: base_link -> imu_link (Sensör gövde merkezinde kabul edilsin)
    static_tf_imu = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0.1', '0', '0', '0', 'base_link', 'imu_link']
    )

    # Statik TF 2: base_link -> gps_link (GPS anteninin robottaki konumu)
    static_tf_gps = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0.2', '0', '0', '0', 'base_link', 'gps_link']
    )

    # 1. Madgwick Filtresi
    madgwick_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter',
        output='screen',
        parameters=[{
            'use_mag': False,
            'publish_tf': False,
            'world_frame': 'enu',
            'fixed_frame': 'odom',
            'gain': 0.01,           # Kazancı düşürerek gyro gürültüsünü sönümleyin (varsayılan: 0.1)
            'do_bias_estimation': True  # Robot dururken gyro kaymasını otomatik hesaplar ve sıfırlar
        }],
        remappings=[
            ('imu/data_raw', '/imu/data_raw'),
            ('imu/data', '/imu/data')
        ]
    )

    # 2. navsat_transform_node
    navsat_transform_node = Node(
        package='robot_localization',
        executable='navsat_transform_node',
        name='navsat_transform',
        output='screen',
        parameters=[ekf_config_path],
        remappings=[
            ('imu/data', '/imu/data'),
            ('gps/fix', '/gps/fix'),
            ('odometry/filtered', '/odometry/filtered'),
            ('odometry/gps', '/odometry/gps')
        ]
    )

    # 3. EKF Füzyon Düğümü
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_config_path],
        remappings=[
            ('odometry/filtered', '/odometry/filtered')
        ]
    )

    return LaunchDescription([
        static_tf_imu,
        static_tf_gps,
        madgwick_node,
        navsat_transform_node,
        ekf_node
    ])