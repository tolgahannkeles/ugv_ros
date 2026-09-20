# UGV ROS — Paletli Taktik Kara Aracı

ROS 2 tabanlı, paletli (skid-steer) bir insansız kara aracı (UGV) için geliştirilmiş yazılım yığını. Sistem bir **Raspberry Pi 5** üzerinde çalışır, hareket kontrolünü seri hat üzerinden bağlı bir **ESP32** ile paylaşır ve tarayıcı üzerinden çalışan bir **taktik komuta paneli** (canlı kamera görüntüsü, harita, IMU/GPS telemetrisi ve joystick kontrolü) sağlar.

## Mimari Genel Bakış

```
                ┌──────────────────────┐
                │   Web Arayüzü        │  (tarayıcı, roslibjs + Leaflet)
                │   ugv_web / www      │
                └─────────┬────────────┘
                    WS 9090 │ MJPEG 8080
                ┌─────────▼────────────┐
                │ rosbridge_websocket  │
                │ web_video_server     │
                │ ugv_web/web_server   │
                └─────────┬────────────┘
                          │  /cmd_vel_teleop, /imu, /gps, /camera
                ┌─────────▼────────────┐
                │      twist_mux       │  (/cmd_vel_teleop, /cmd_vel_auto, /e_stop)
                └─────────┬────────────┘
                          │ /cmd_vel
                ┌─────────▼────────────┐
                │  tracked_hardware     │  UART (binary protokol)
                │  esp32_bridge (C++)   │◄────────────► ESP32 (motor sürücü)
                └───────────────────────┘
```

`tracked_intelligence` paketi (derinlik tahmini + engelden kaçınma) kod olarak mevcuttur ancak ana launch dosyasında şu an **devre dışı** bırakılmıştır.

## Paketler (`src/`)

| Paket | Build tipi | Durum | Açıklama |
|---|---|---|---|
| [tracked_bringup](src/tracked_bringup) | ament_python | Aktif | Sistem genelinde launch dosyaları ve konfigürasyon (`robot.launch.py`, parametre YAML'ları) |
| [tracked_hardware](src/tracked_hardware) | ament_cmake (C++) | Aktif | ESP32 ile UART üzerinden haberleşen donanım köprüsü (`esp32_bridge`) |
| [tracked_intelligence](src/tracked_intelligence) | ament_python | Kod hazır, launch'ta kapalı | ONNX (MiDaS) ile monoküler derinlik tahmini ve engelden kaçınma |
| [ugv_web](src/ugv_web) | ament_python | Aktif | Web arayüzü sunucusu ve statik dosyalar (kontrol paneli) |

### tracked_bringup

Robotu tek komutla ayağa kaldıran launch dosyasını ve ortak parametre dosyalarını barındırır.

- **`launch/robot.launch.py`** şu node'ları başlatır:
  - `esp32_bridge` (tracked_hardware) — donanım köprüsü
  - `twist_mux` — hız komutu arbitrajı
  - `camera_ros` — kamera sürücüsü
  - `web_video_server` — kameradan MJPEG akışı
  - `rosbridge_websocket` — web arayüzü için WebSocket köprüsü
  - `ugv_web` `web_server` — statik arayüz sunucusu
  - *(kapalı)* `depth_node`, `avoidance_node` — otonom engelden kaçınma
- **`config/robot_params.yaml`** — seri port (`/dev/ttyAMA0`), baudrate (115200), palet genişliği (0.22 m), kayma katsayısı (slip_factor 1.25), IMU/GPS frame id'leri.
- **`config/twist_mux.yaml`** — `/cmd_vel_teleop` (öncelik 100), `/cmd_vel_auto` (öncelik 50), `/e_stop` kilidi (öncelik 255); çıkış `/cmd_vel`'e yönlendirilir.

### tracked_hardware

C++ ile yazılmış, Raspberry Pi ↔ ESP32 arasındaki UART haberleşmesini yöneten `esp32_bridge` node'u.

- `/cmd_vel` (Twist) mesajlarını skid-steer kinematiğiyle sol/sağ palet hızlarına çevirip ESP32'ye özel bir binary protokolle gönderir.
- ESP32'den gelen verilerden `/imu/data_raw` (sensor_msgs/Imu) ve `/gps/fix` (sensor_msgs/NavSatFix) mesajlarını yayınlar.
- `include/tracked_hardware/protocol.hpp` — checksum'lı, state-machine tabanlı basit bir çerçeve (frame) protokolü.
- `include/tracked_hardware/uart_driver.hpp` — POSIX `termios` tabanlı seri port sürücüsü. **Yalnızca Linux'ta** (Raspberry Pi OS) derlenir/çalışır.

### tracked_intelligence

Kameradan gelen görüntüyle monoküler derinlik tahmini yapan ve buna göre engelden kaçınma kararı üreten paket.

- `depth_node` — `/camera/image_raw` görüntüsünü, gömülü ONNX modeli (`models/depth_model.onnx`, MiDaS v2.1 Small) ile CPU üzerinde işleyip `/depth/image_raw` olarak yayınlar.
- `avoidance_node` — derinlik görüntüsünü sol/orta/sağ bölgelere ayırıp `/cmd_vel_auto` üzerinden dönüş/ilerleme kararı üretir.
- Şu an `robot.launch.py` içinde yorum satırı olarak kapalı; etkinleştirmek için ilgili satırların açılması yeterlidir.

### ugv_web

Tarayıcı tabanlı **"UGV Tactical Command Station"** kontrol panelini sunan paket.

- `web_server` node'u, `www/` klasörünü basit bir HTTP sunucusuyla (varsayılan port `8000`) servis eder.
- `www/index.html` tek sayfalık, koyu temalı bir taktik arayüzdür:
  - `web_video_server`'dan canlı MJPEG kamera görüntüsü
  - `rosbridge` (roslibjs) üzerinden ROS'a WebSocket bağlantısı
  - IMU verisiyle yapay ufuk göstergesi ve yaw/heading tahmini
  - GPS verisiyle Leaflet tabanlı canlı mini harita ve iz (trail) çizimi
  - Ekran joystick'i + WASD klavye kontrolü, güç yüzdesi ayarlanabilir, `/cmd_vel_teleop`'a 50 ms periyotla yayın yapar
  - Acil durdurma butonu / SPACE tuşu (**not:** şu an yalnızca hız komutlarını sıfırlar; `twist_mux`'un `/e_stop` kilidini tetiklemez — bkz. [Bilinen Eksikler](#bilinen-eksikler-ve-yapılacaklar))

## Gereksinimler

- ROS 2 (colcon workspace yapısı)
- Python 3, `onnxruntime`, `cv_bridge`
- Sistem genelinde kurulu olması gereken ROS 2 paketleri (bu depoya dahil değildir): `twist_mux`, `camera_ros`, `web_video_server`, `rosbridge_server`
- `tracked_hardware` yalnızca Linux (POSIX `termios`) üzerinde derlenir — geliştirme/test için bir Raspberry Pi veya Linux makinesi gerekir.

## Kurulum ve Çalıştırma

```bash
# Workspace kökünde
colcon build
source install/setup.bash

# Tüm sistemi başlat
ros2 launch tracked_bringup robot.launch.py
```

Web arayüzüne erişim: `http://<robot-ip>:8000`

## Bilinen Eksikler ve Yapılacaklar

- Web arayüzündeki acil durdurma butonu `/e_stop` topic'ine yayın yapmıyor; `twist_mux` kilidiyle entegre edilmesi gerekiyor.
- `tracked_intelligence` içindeki derinlik tahmini ve engelden kaçınma node'ları test amaçlı launch dosyasında kapalı tutuluyor.
- Robotun URDF/mesh modeli ve görüntü işleme (vision) paketleri henüz projede yok.
