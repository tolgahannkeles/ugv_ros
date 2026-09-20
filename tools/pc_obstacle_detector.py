#!/usr/bin/env python3
import argparse
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Int32MultiArray
from ultralytics import YOLO


class PcObstacleDetector(Node):
    def __init__(self, args):
        super().__init__('pc_obstacle_detector')

        self.model = YOLO(args.model)
        self.imgsz = args.imgsz
        self.near_distance = args.near_distance
        self.near_percentile = args.near_percentile
        self.show = args.show
        self.is_compressed = 'compressed' in args.image_topic

        self.zones_pub = self.create_publisher(Int32MultiArray, '/obstacle_zones', 10)

        # Topic türüne göre dinamik subscription
        if self.is_compressed:
            self.create_subscription(CompressedImage, args.image_topic, self.on_compressed_image, 10)
        else:
            self.create_subscription(Image, args.image_topic, self.on_raw_image, 10)

        self.get_logger().info(f"YOLO26 depth modeli yuklendi: {args.model}, topic: {args.image_topic}")

    def on_compressed_image(self, msg):
        if not msg.data:
            self.get_logger().warning(
                f"Bos CompressedImage alindi (format={msg.format!r}); atlaniyor",
                throttle_duration_sec=5.0
            )
            return
        np_arr = np.frombuffer(msg.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is not None:
            self.process_frame(frame)

    def on_raw_image(self, msg):
        # cv_bridge yerine saf numpy ile donusturme (ABI hatasi vermez)
        if msg.encoding in ['bgr8', 'rgb8']:
            frame = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            if msg.encoding == 'rgb8':
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            self.process_frame(frame)

    def process_frame(self, frame):
        result = self.model.predict(frame, imgsz=self.imgsz, verbose=False)[0]
        depth_map = result.depth.data.cpu().numpy()  # (H, W), metre cinsinden mutlak derinlik

        _, width = depth_map.shape
        third = width // 3
        bounds = [(0, third), (third, 2 * third), (2 * third, width)]

        # Her bolgede en yakin (dusuk persentil) derinlik esigin altindaysa engel say
        distances = [float(np.percentile(depth_map[:, x0:x1], self.near_percentile)) for x0, x1 in bounds]
        zones = [int(d < self.near_distance) for d in distances]

        self.zones_pub.publish(Int32MultiArray(data=zones))

        if self.show:
            self.visualize(frame, distances, zones)

    def visualize(self, frame, distances, zones):
        vis = frame.copy()
        h, w = vis.shape[:2]
        third = w // 3
        bounds = [(0, third), (third, 2 * third), (2 * third, w)]
        labels = ['SOL', 'ORTA', 'SAG']

        for (x0, x1), blocked in zip(bounds, zones):
            color = (0, 0, 255) if blocked else (0, 200, 0)
            overlay = vis.copy()
            cv2.rectangle(overlay, (x0, 0), (x1, h), color, -1)
            vis = cv2.addWeighted(overlay, 0.25, vis, 0.75, 0)
            cv2.line(vis, (x1, 0), (x1, h), (255, 255, 255), 1)

        for label, (x0, x1), dist, blocked in zip(labels, bounds, distances, zones):
            color = (0, 0, 255) if blocked else (0, 200, 0)
            text = f"{label}: {dist:.2f}m {'ENGEL' if blocked else 'TEMIZ'}"
            cv2.putText(vis, text, (x0 + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        cv2.imshow('collision_guard - obstacle zones', vis)
        cv2.waitKey(1)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='yolo26n-depth.pt')
    parser.add_argument('--image-topic', default='/camera/image_raw/compressed')
    parser.add_argument('--imgsz', type=int, default=768)
    parser.add_argument('--near-distance', type=float, default=0.3,
                        help='Bu mesafeden (metre) daha yakin bolgeler engel sayilir')
    parser.add_argument('--near-percentile', type=float, default=10.0,
                        help='Her bolgede karsilastirilacak en yakin persentil (0-100)')
    parser.add_argument('--show', action=argparse.BooleanOptionalAction, default=True,
                        help='Kamera goruntusunu ve bolge/engel durumunu bir pencerede goster')
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
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
