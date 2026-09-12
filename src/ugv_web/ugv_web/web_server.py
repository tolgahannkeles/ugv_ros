#!/usr/bin/env python3
import http.server
import socketserver
import os
from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
import threading

class WebServerNode(Node):
    def __init__(self):
        super().__init__('web_server_node')
        self.declare_parameter('port', 8000)
        port = self.get_parameter('port').value

        # Kurulum dizinindeki www klasörünü bul
        pkg_share = get_package_share_directory('ugv_web')
        www_dir = os.path.join(pkg_share, 'www')

        os.chdir(www_dir)
        handler = http.server.SimpleHTTPRequestHandler

        self.get_logger().info(f"Web Arayuzu baslatiliyor: http://0.0.0.0:{port} (Dizin: {www_dir})")
        
        # HTTP sunucusunu bloke etmemesi için ayrı iş parçacığında açıyoruz
        self.httpd = socketserver.TCPServer(("", port), handler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

    def destroy_node(self):
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = WebServerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()