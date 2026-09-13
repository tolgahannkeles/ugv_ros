#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge
import numpy as np

class AvoidanceNode(Node):
    def __init__(self):
        super().__init__('avoidance_node')

        self.declare_parameter('safe_threshold', 0.60)
        self.declare_parameter('forward_speed', 0.25)
        self.declare_parameter('turn_speed', 0.70)

        self.safe_threshold = self.get_parameter('safe_threshold').value
        self.forward_speed = self.get_parameter('forward_speed').value
        self.turn_speed = self.get_parameter('turn_speed').value

        self.bridge = CvBridge()

        self.sub_depth = self.create_subscription(
            Image, '/depth/image_raw', self.depth_callback, 1)
        
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel_auto', 10)
        self.get_logger().info("AvoidanceNode: Standart Twist formatında aktif.")

    def depth_callback(self, msg: Image):
        try:
            depth_map = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        except Exception as e:
            self.get_logger().error(f"cv_bridge hatası: {e}")
            return

        h, w = depth_map.shape[:2]

        roi_top = int(h * 0.35)
        roi_bottom = int(h * 0.75)
        roi = depth_map[roi_top:roi_bottom, :]

        col_w = w // 3
        left_zone = roi[:, :col_w]
        center_zone = roi[:, col_w:2*col_w]
        right_zone = roi[:, 2*col_w:]

        left_score = float(np.percentile(left_zone, 85)) / 255.0
        center_score = float(np.percentile(center_zone, 85)) / 255.0
        right_score = float(np.percentile(right_zone, 85)) / 255.0

        cmd = Twist()

        if center_score > self.safe_threshold:
            cmd.linear.x = 0.0
            if left_score < right_score:
                cmd.angular.z = self.turn_speed
            else:
                cmd.angular.z = -self.turn_speed
        else:
            cmd.linear.x = self.forward_speed
            if left_score > self.safe_threshold * 0.8:
                cmd.angular.z = -self.turn_speed * 0.5
            elif right_score > self.safe_threshold * 0.8:
                cmd.angular.z = self.turn_speed * 0.5
            else:
                cmd.angular.z = 0.0

        self.pub_cmd.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = AvoidanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop_cmd = Twist()
        node.pub_cmd.publish(stop_cmd)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()