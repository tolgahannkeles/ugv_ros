#!/usr/bin/env python3
"""
PC uzerinde calisir, robotun colcon workspace'ine dahil degildir.

Robotun kamerasindan gelen /camera/image_raw goruntusunu YOLO ile isler,
goruntuyu sol/orta/sag olarak 3 bolgeye ayirir ve her bolgede "yakin" bir
engel olup olmadigini /obstacle_zones (std_msgs/Int32MultiArray, [sol, orta, sag],
her biri 0 veya 1) olarak yayinlar. tracked_intelligence icindeki
collision_guard node'u bu sinyali okuyup, otonom destek acikken ve robot
ileri hareket ederken carpmayi onlemek icin komutu keser.

Calistirmadan once ROS 2 ortamini source edip robotla ayni ROS_DOMAIN_ID'de
oldugunuzdan emin olun. Bagimliliklar: ultralytics, opencv-python, cv_bridge,
rclpy (ROS 2 kurulumuyla gelir).

Kullanim:
    python3 pc_obstacle_detector.py --host <robot-ip-degil-ros-domain>
    python3 pc_obstacle_detector.py --model yolov8n.pt --conf 0.45 --near-ratio 0.65
"""
import argparse

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Int32MultiArray
from ultralytics import YOLO


class PcObstacleDetector(Node):
    def __init__(self, args):
        super().__init__('pc_obstacle_detector')

        self.model = YOLO(args.model)
        self.conf = args.conf
        self.near_ratio = args.near_ratio
        self.classes = args.classes
        self.bridge = CvBridge()

        self.zones_pub = self.create_publisher(Int32MultiArray, '/obstacle_zones', 10)
        self.create_subscription(Image, args.image_topic, self.on_image, 10)

        self.get_logger().info(f"YOLO modeli yuklendi: {args.model}, dinlenen topic: {args.image_topic}")

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        height, width = frame.shape[:2]

        results = self.model.predict(
            frame, conf=self.conf, classes=self.classes, verbose=False
        )[0]

        zones = [0, 0, 0]  # sol, orta, sag
        third = width / 3.0

        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # Kutunun alt kenari goruntunun alt kismina yakinsa (buyuk/yakin nesne) say
            if (y2 / height) < self.near_ratio:
                continue

            center_x = (x1 + x2) / 2.0
            if center_x < third:
                zones[0] = 1
            elif center_x < 2 * third:
                zones[1] = 1
            else:
                zones[2] = 1

        self.zones_pub.publish(Int32MultiArray(data=zones))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='yolov8n.pt')
    parser.add_argument('--image-topic', default='/camera/image_raw')
    parser.add_argument('--conf', type=float, default=0.4)
    parser.add_argument('--near-ratio', type=float, default=0.65,
                         help="Kutunun alt kenari bu orandan asagidaysa 'yakin' sayilir (0-1)")
    parser.add_argument('--classes', type=int, nargs='*', default=None,
                         help='YOLO sinif id filtresi (bos birakilirsa tum siniflar)')
    return parser.parse_args()


def main():
    args = parse_args()
    rclpy.init()
    node = PcObstacleDetector(args)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
