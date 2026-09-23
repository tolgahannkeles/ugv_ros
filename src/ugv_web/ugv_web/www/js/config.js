// Arayüzün tüm sabitleri tek yerde

export const HOST = window.location.hostname || 'localhost';

export const ROSBRIDGE_URL = `ws://${HOST}:9090`;
export const ROS_RECONNECT_MS = 2000;

export const CAMERA_TOPIC = '/camera/image_raw';
export const CAMERA_STREAM_URL = `http://${HOST}:8080/stream?topic=${CAMERA_TOPIC}`;
export const CAMERA_RETRY_MS = 5000;

export const TOPICS = {
  // COLLISION_GUARD'A HAM KOMUT OLARAK GİDİYOR, GUARD /cmd_vel_teleop'A YAYINLIYOR
  cmdVel: { name: '/cmd_vel_teleop_raw', messageType: 'geometry_msgs/Twist' },
  imu: { name: '/imu/data', messageType: 'sensor_msgs/Imu' },
  gps: { name: '/gps/fix', messageType: 'sensor_msgs/NavSatFix' },
  assistEnabled: { name: '/assist_enabled', messageType: 'std_msgs/Bool' },
  assistBlocking: { name: '/assist/blocking', messageType: 'std_msgs/Bool' },
  obstacleZones: { name: '/obstacle_zones', messageType: 'std_msgs/Int32MultiArray' },
  // twist_mux kilidi (ugv_control/config/twist_mux.yaml, priority 255, timeout 0)
  eStop: { name: '/e_stop', messageType: 'std_msgs/Bool' },
};

// Bu süre boyunca mesaj gelmeyen sensör "veri yok" sayılır
export const SENSOR_STALE_MS = 2000;
// collision_guard'ın obstacle_timeout_sec parametresiyle aynı tutulmalı
export const OBSTACLE_TIMEOUT_MS = 1000;

// Eğim uyarı eşikleri (derece). Şasinin gerçek devrilme açısı ölçülmedi; tahmini değerlerdir,
// ağırlık merkezi ve palet açıklığı ölçülünce güncellenmeli
export const TILT_CAUTION_DEG = 20;
export const TILT_WARNING_DEG = 30;

export const MAP_CENTER = [39.92077, 32.85411];
export const MAP_ZOOM = 16;
export const MAP_TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

// Motor çalışma eşikleri (Linear: 0.40 - 0.60 m/s, Angular: 3.00 - 5.00 rad/s)
export const VELOCITY = {
  minLin: 0.40,
  maxLin: 0.60,
  minAng: 3.00,
  maxAng: 5.00,
  deadzone: 0.05,
};

export const DEFAULT_POWER = 100;
export const TELEOP_PERIOD_MS = 50;
export const STOP_PACKET_COUNT = 3;
