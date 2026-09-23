#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import onnxruntime as ort
import numpy as np
import cv2
import os
from ament_index_python.packages import get_package_share_directory

class DepthNode(Node):
    def __init__(self):
        super().__init__('depth_node')

        self.declare_parameter('input_width', 256)
        self.declare_parameter('input_height', 256)
        self.declare_parameter('skip_frames', 1)

        self.in_w = self.get_parameter('input_width').value
        self.in_h = self.get_parameter('input_height').value
        self.skip_frames = self.get_parameter('skip_frames').value
        self.frame_count = 0

        # ONNX: Locate and load the optimized model
        pkg_share = get_package_share_directory('ugv_intelligence')
        model_path = os.path.join(pkg_share, 'models', 'depth_model.onnx')

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2  # Pi 5 has 4 cores; use 2 for inference, keep 2 for ROS
        self.session = ort.InferenceSession(model_path, opts, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name

        self.bridge = CvBridge()

        # PUBS & SUBS
        self.sub_image = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 1)
        self.pub_depth = self.create_publisher(Image, '/depth/image_raw', 1)

        self.get_logger().info(f"DepthNode initialized with ONNX: {model_path}")

    def image_callback(self, msg: Image):
        # OPTIMIZATION: Frame drop logic
        self.frame_count += 1
        if self.frame_count % (self.skip_frames + 1) != 0:
            return

        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f"cv_bridge conversion error: {e}")
            return

        orig_h, orig_w = cv_img.shape[:2]

        # PRE-PROCESSING: Resize and normalize for MiDaS
        img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.in_w, self.in_h), interpolation=cv2.INTER_AREA)
        img = img.astype(np.float32) / 255.0
        
        # Standard ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std

        # Shape to (1, 3, H, W)
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        # INFERENCE: Execute on CPU
        outputs = self.session.run(None, {self.input_name: img})
        prediction = outputs[0][0]  # (H, W)

        # POST-PROCESSING: Resize back and normalize to 0-255 uint8 (Higher = Closer)
        depth_min = prediction.min()
        depth_max = prediction.max()
        if depth_max - depth_min > 1e-6:
            depth_norm = (prediction - depth_min) / (depth_max - depth_min)
        else:
            depth_norm = np.zeros_like(prediction)

        depth_uint8 = (depth_norm * 255.0).astype(np.uint8)
        depth_resized = cv2.resize(depth_uint8, (orig_w // 2, orig_h // 2), interpolation=cv2.INTER_NEAREST)

        # PUBLISH
        depth_msg = self.bridge.cv2_to_imgmsg(depth_resized, encoding='mono8')
        depth_msg.header = msg.header
        self.pub_depth.publish(depth_msg)

def main(args=None):
    rclpy.init(args=args)
    node = DepthNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()