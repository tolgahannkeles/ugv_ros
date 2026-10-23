#!/usr/bin/env python3
import functools
import http.server
import socketserver
import os
from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
import threading


class ThreadingHTTPServer(socketserver.ThreadingTCPServer):
    # Her istek ayrı iş parçacığında: tarayıcının boşta açık tuttuğu (preconnect/keep-alive)
    # tek bir bağlantı, tek iş parçacıklı sunucuyu kilitleyip sayfanın açılmasını engelliyordu
    daemon_threads = True
    allow_reuse_address = True


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    # Tarayıcı her açılışta dosyanın değişip değişmediğini sorsun: yoksa güncellenen
    # JS modülleri (ör. config.js) eski haliyle önbellekten yükleniyordu. Değişmediyse
    # sunucu 304 döner, dosya yeniden indirilmez.
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


class WebServerNode(Node):
    def __init__(self):
        super().__init__('web_server_node')
        self.declare_parameter('port', 8000)
        port = self.get_parameter('port').value

        # Kurulum dizinindeki www klasörünü bul
        pkg_share = get_package_share_directory('ugv_web')
        www_dir = os.path.join(pkg_share, 'www')

        handler = functools.partial(NoCacheHandler, directory=www_dir)

        self.get_logger().info(f"Web Arayuzu baslatiliyor: http://0.0.0.0:{port} (Dizin: {www_dir})")

        # HTTP sunucusunu bloke etmemesi için ayrı iş parçacığında açıyoruz
        self.httpd = ThreadingHTTPServer(("", port), handler)
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
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()