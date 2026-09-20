import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Int32MultiArray


class CollisionGuardNode(Node):
    def __init__(self):
        super().__init__('collision_guard')

        self.declare_parameter('obstacle_timeout_sec', 1.0)
        self.obstacle_timeout = self.get_parameter('obstacle_timeout_sec').value

        self.assist_enabled = False
        self.zones = [0, 0, 0]  # sol, orta, sag
        self.last_zones_stamp = None

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_teleop', 10)
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

        self.cmd_pub.publish(out)
        self.blocking_pub.publish(Bool(data=blocking))


def main(args=None):
    rclpy.init(args=args)
    node = CollisionGuardNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
