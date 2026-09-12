#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu, NavSatFix, NavSatStatus
import serial
import struct
import threading

FRAME_HEADER1  = 0xAA
FRAME_HEADER2  = 0x55
PKT_ID_CMD_VEL = 0x01
PKT_ID_IMU     = 0x10
PKT_ID_GPS     = 0x11  # ESP32 GPS Paket ID

class ESP32Bridge(Node):
    def __init__(self):
        super().__init__('esp32_bridge')

        self.declare_parameter('port', '/dev/ttyAMA0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('track_width', 0.22)
        self.declare_parameter('slip_factor', 1.25)
        self.declare_parameter('imu_frame_id', 'imu_link')
        self.declare_parameter('gps_frame_id', 'gps_link')

        port = self.get_parameter('port').value
        baud = self.get_parameter('baudrate').value
        self.effective_width = self.get_parameter('track_width').value * self.get_parameter('slip_factor').value
        self.imu_frame_id = self.get_parameter('imu_frame_id').value
        self.gps_frame_id = self.get_parameter('gps_frame_id').value

        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.get_logger().info(f"ESP32 UART acildi: {port} @ {baud}")
        except Exception as e:
            self.get_logger().fatal(f"Seri port acilamadi: {e}")
            raise e

        # ROS 2 Arayüzleri
        self.sub_cmd_vel = self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_cb, 10)
        self.pub_imu = self.create_publisher(Imu, '/imu/data_raw', 10)
        self.pub_gps = self.create_publisher(NavSatFix, '/gps/fix', 10)

        self.running = True
        self.rx_thread = threading.Thread(target=self.rx_loop, daemon=True)
        self.rx_thread.start()

    def calc_crc(self, pkt_id, length, payload):
        crc = pkt_id ^ length
        for b in payload:
            crc ^= b
        return crc

    def cmd_vel_cb(self, msg: Twist):
        vx = msg.linear.x
        wz = msg.angular.z
        v_left = vx - (wz * self.effective_width / 2.0)
        v_right = vx + (wz * self.effective_width / 2.0)

        payload = struct.pack('<ff', float(v_left), float(v_right))
        length = len(payload)
        crc = self.calc_crc(PKT_ID_CMD_VEL, length, payload)

        packet = bytearray([FRAME_HEADER1, FRAME_HEADER2, PKT_ID_CMD_VEL, length]) + bytearray(payload) + bytearray([crc])
        try:
            self.ser.write(packet)
        except Exception as e:
            self.get_logger().warn(f"TX Hatasi: {e}")

    def rx_loop(self):
        state = 'H1'
        pkt_id, pkt_len = 0, 0
        payload = bytearray()

        while self.running and rclpy.ok():
            try:
                byte_in = self.ser.read(1)
                if not byte_in:
                    continue
                b = byte_in[0]

                if state == 'H1':
                    if b == FRAME_HEADER1: state = 'H2'
                elif state == 'H2':
                    state = 'ID' if b == FRAME_HEADER2 else 'H1'
                elif state == 'ID':
                    pkt_id = b
                    state = 'LEN'
                elif state == 'LEN':
                    pkt_len = b
                    payload.clear()
                    state = 'PAYLOAD' if pkt_len > 0 else 'CRC'
                elif state == 'PAYLOAD':
                    payload.append(b)
                    if len(payload) >= pkt_len:
                        state = 'CRC'
                elif state == 'CRC':
                    if self.calc_crc(pkt_id, pkt_len, payload) == b:
                        self.process_packet(pkt_id, payload)
                    state = 'H1'
            except Exception:
                state = 'H1'

    def process_packet(self, pkt_id, payload):
        stamp = self.get_clock().now().to_msg()

        # IMU (24 Bayt: 6x float32)
        if pkt_id == PKT_ID_IMU and len(payload) == 24:
            ax, ay, az, gx, gy, gz = struct.unpack('<ffffff', payload)

            msg = Imu()
            msg.header.stamp = stamp
            msg.header.frame_id = self.imu_frame_id
            msg.linear_acceleration.x = ax
            msg.linear_acceleration.y = ay
            msg.linear_acceleration.z = az
            msg.angular_velocity.x = gx
            msg.angular_velocity.y = gy
            msg.angular_velocity.z = gz
            msg.orientation_covariance[0] = -1.0
            self.pub_imu.publish(msg)

        # GPS (17 Bayt: double lat, double lon, uint8 fix)
        elif pkt_id == PKT_ID_GPS and len(payload) == 17:
            lat, lon, fix = struct.unpack('<ddB', payload)

            gps_msg = NavSatFix()
            gps_msg.header.stamp = stamp
            gps_msg.header.frame_id = self.gps_frame_id
            gps_msg.status.status = NavSatStatus.STATUS_FIX if fix > 0 else NavSatStatus.STATUS_NO_FIX
            gps_msg.status.service = NavSatStatus.SERVICE_GPS
            gps_msg.latitude = lat
            gps_msg.longitude = lon
            gps_msg.altitude = 0.0
            self.pub_gps.publish(gps_msg)

    def destroy_node(self):
        self.running = False
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = ESP32Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()