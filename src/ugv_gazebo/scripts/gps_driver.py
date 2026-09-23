#!/usr/bin/env python3
"""Simüle GPS sürücüsü: /gps/fix_raw -> /gps/fix (kovaryanslı).

ros_gz_bridge NavSat mesajını çevirirken position_covariance'ı boş bırakıyor
(COVARIANCE_TYPE_UNKNOWN). Gerçek GPS sürücüleri bu alanı doldurur; bu düğüm aynı
işi Gazebo sensörünün gürültü değerleriyle yapar. Sıfır kovaryans EKF'ye "kusursuz
ölçüm" demek olacağından navsat_transform/EKF zinciri bunsuz sağlıklı çalışmaz.
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix


class GpsDriver(Node):
    def __init__(self):
        super().__init__('gps_driver')
        # ugv_description/urdf/gazebo.xacro'daki navsat gürültüsüyle aynı
        self.declare_parameter('horizontal_stddev', 0.8)
        self.declare_parameter('vertical_stddev', 1.5)
        h = self.get_parameter('horizontal_stddev').value ** 2
        v = self.get_parameter('vertical_stddev').value ** 2
        self.covariance = [h, 0.0, 0.0,
                           0.0, h, 0.0,
                           0.0, 0.0, v]

        self.pub = self.create_publisher(NavSatFix, '/gps/fix', 10)
        self.create_subscription(NavSatFix, '/gps/fix_raw', self.on_fix, 10)

    def on_fix(self, msg):
        msg.position_covariance = self.covariance
        msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = GpsDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
