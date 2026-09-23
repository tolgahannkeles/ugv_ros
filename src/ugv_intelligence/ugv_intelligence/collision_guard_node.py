import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from std_msgs.msg import Bool, Int32MultiArray


class CollisionGuardNode(Node):
    def __init__(self):
        super().__init__('collision_guard')

        self.declare_parameter('obstacle_timeout_sec', 1.0)
        self.obstacle_timeout = self.get_parameter('obstacle_timeout_sec').value
        # true: /cmd_vel_teleop TwistStamped yayinlanir (twist_mux use_stamped + ros2_control)
        self.declare_parameter('use_stamped', False)
        self.use_stamped = self.get_parameter('use_stamped').value

        self.assist_enabled = False
        self.zones = [0, 0, 0]  # sol, orta, sag
        self.last_zones_stamp = None

        out_type = TwistStamped if self.use_stamped else Twist
        self.cmd_pub = self.create_publisher(out_type, '/cmd_vel_teleop', 10)
        self.blocking_pub = self.create_publisher(Bool, '/assist/blocking', 10)

        self.create_subscription(Twist, '/cmd_vel_teleop_raw', self.on_cmd, 10)
        self.create_subscription(Bool, '/assist_enabled', self.on_assist_toggle, 10)
        self.create_subscription(Int32MultiArray, '/obstacle_zones', self.on_zones, 10)

        self.get_logger().info('collision_guard hazir: /cmd_vel_teleop_raw -> /cmd_vel_teleop')

    def on_assist_toggle(self, msg):
        self.assist_enabled = msg.data
        if not self.assist_enabled:
            self.blocking_pub.publish(Bool(data=False))

    def on_zones(self, msg):
        if len(msg.data) >= 3:
            self.zones = list(msg.data[:3])
            self.last_zones_stamp = self.get_clock().now()

    def zones_fresh(self):
        if self.last_zones_stamp is None:
            return False
        age = (self.get_clock().now() - self.last_zones_stamp).nanoseconds / 1e9
        return age < self.obstacle_timeout

    def on_cmd(self, msg):
        # PC tarafindaki tespit yayini kesilirse (age >= timeout) engel yokmus gibi
        # davranilir; surucu joystick ile kontrole devam edebilir.
        blocking = (
            self.assist_enabled
            and msg.linear.x > 0.0
            and self.zones_fresh()
            and any(self.zones)
        )

        out = msg
        if blocking:
            out = Twist()
            out.angular.z = msg.angular.z

        if self.use_stamped:
            stamped = TwistStamped()
            stamped.header.stamp = self.get_clock().now().to_msg()
            stamped.header.frame_id = 'base_link'
            stamped.twist = out
            out = stamped

        self.cmd_pub.publish(out)
        self.blocking_pub.publish(Bool(data=blocking))


def main(args=None):
    rclpy.init(args=args)
    node = CollisionGuardNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
