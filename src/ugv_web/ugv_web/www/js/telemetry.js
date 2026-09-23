// IMU ve GPS aboneliklerinin arayüze yansıtılması, veri tazeliği ve eğim uyarısı
import { TOPICS, SENSOR_STALE_MS } from './config.js';
import { subscribe } from './ros.js';
import { setAnnunciator, logEvent } from './ui.js';
import { tiltLevel } from './instruments.js';

const RAD_TO_DEG = 180 / Math.PI;
// sensor_msgs/NavSatStatus: -1 NO_FIX, 0 FIX, 1 SBAS_FIX, 2 GBAS_FIX
const GPS_FIX_LABELS = { 0: 'FIX', 1: 'SBAS', 2: 'GBAS' };
const TILT_TEXT = { normal: 'NORMAL', caution: 'DİK', warning: 'TEHLİKE' };
const LEVEL_RANK = { normal: 0, caution: 1, warning: 2 };

let yawDeg = 0.0;        // REP-103: z ekseni etrafında saat yönünün tersi pozitif
let yawOffsetDeg = 0.0;  // "Yönü sıfırla" ile ayarlanır
let lastImuTime = null;
let lastImuAt = 0;
let lastGpsAt = 0;
let gpsFixLabel = null;
let tiltState = null;

function wrap360(deg) {
  return ((deg % 360) + 360) % 360;
}

// Başlangıçta aracın kuzeye baktığı varsayılır (ugv_bringup localization_real.yaml ile aynı)
function currentHeading() {
  return wrap360(-(yawDeg - yawOffsetDeg));
}

// Madgwick/Gazebo oryantasyon verirse onu kullan; covariance[0] == -1 "oryantasyon yok" demek
function hasOrientation(msg) {
  const q = msg.orientation;
  return Boolean(q) && msg.orientation_covariance?.[0] !== -1
    && (q.w !== 0 || q.x !== 0 || q.y !== 0 || q.z !== 0);
}

function attitudeFromQuaternion({ x, y, z, w }) {
  const roll = Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y));
  const pitch = Math.asin(Math.max(-1, Math.min(1, 2 * (w * y - z * x))));
  const yaw = Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z));
  // REP-103'te pitch burun aşağı pozitif; göstergede burun yukarı pozitif kullanılır
  return { roll: roll * RAD_TO_DEG, pitch: -pitch * RAD_TO_DEG, yaw: yaw * RAD_TO_DEG };
}

// Boyuna/yanal eğimden kötü olanı uyarı paneline yansıt; seviye değişince günlüğe yaz
function updateTilt(pitch, roll) {
  const pl = tiltLevel(pitch);
  const rl = tiltLevel(roll);
  const level = LEVEL_RANK[pl] >= LEVEL_RANK[rl] ? pl : rl;
  if (level === tiltState) return;

  if (tiltState !== null && level !== 'normal') {
    const axis = LEVEL_RANK[pl] >= LEVEL_RANK[rl]
      ? `boyuna ${pitch.toFixed(0)}°`
      : `yanal ${roll.toFixed(0)}°`;
    logEvent(`${level === 'warning' ? 'Devrilme riski' : 'Dik eğim'}: ${axis}`, level);
  }
  tiltState = level;
  setAnnunciator('annTilt', level, TILT_TEXT[level]);
}

function initImu(hud, instruments, tacticalMap) {
  const el = {
    ax: document.getElementById('valAx'),
    az: document.getElementById('valAz'),
  };

  subscribe(TOPICS.imu, (msg) => {
    const { x: ax, y: ay, z: az } = msg.linear_acceleration;
    const now = performance.now();
    let roll;
    let pitch;

    if (hasOrientation(msg)) {
      ({ roll, pitch, yaw: yawDeg } = attitudeFromQuaternion(msg.orientation));
    } else {
      // Oryantasyon yoksa: roll/pitch ivmeölçerden, yaw jiroskop entegrasyonundan (zamanla kayar)
      roll = Math.atan2(ay, az) * RAD_TO_DEG;
      pitch = Math.atan2(ax, Math.sqrt(ay * ay + az * az)) * RAD_TO_DEG;
      if (lastImuTime) {
        yawDeg += msg.angular_velocity.z * RAD_TO_DEG * ((now - lastImuTime) / 1000.0);
      }
    }
    lastImuTime = now;
    lastImuAt = now;

    const heading = currentHeading();
    el.ax.textContent = ax.toFixed(2);
    el.az.textContent = az.toFixed(2);

    hud.setAttitude(pitch, roll);
    hud.setHeading(heading);
    instruments.setAttitude(pitch, roll);
    instruments.setHeading(heading);
    tacticalMap.setHeading(heading);
    updateTilt(pitch, roll);
  });
}

function initGps(tacticalMap) {
  const hudCoords = document.getElementById('hudCoords');
  const latEl = document.getElementById('valLat');
  const lonEl = document.getElementById('valLon');

  subscribe(TOPICS.gps, (msg) => {
    const { latitude: lat, longitude: lon } = msg;
    lastGpsAt = performance.now();

    const hasFix = msg.status.status >= 0 && Number.isFinite(lat) && Number.isFinite(lon);
    gpsFixLabel = hasFix ? (GPS_FIX_LABELS[msg.status.status] ?? 'FIX') : null;
    // Fix yokken gelen koordinat anlamsız (genelde 0,0); haritayı oraya zıplatma
    if (!hasFix) return;

    latEl.textContent = lat.toFixed(6);
    lonEl.textContent = lon.toFixed(6);
    hudCoords.textContent = `ENL ${lat.toFixed(5)}  BOY ${lon.toFixed(5)}`;
    tacticalMap.updatePosition(lat, lon);
  });
}

function updateSensorAnnunciators(instruments) {
  const now = performance.now();
  const imuStale = !lastImuAt || now - lastImuAt > SENSOR_STALE_MS;

  if (imuStale) {
    setAnnunciator('annImu', 'caution', 'VERİ YOK');
    // Bayat açıyla "normal" göstermek yanıltıcı olur
    setAnnunciator('annTilt', 'off', '—');
    tiltState = null;
  } else {
    setAnnunciator('annImu', 'normal', 'AKTİF');
  }
  instruments.setStale(imuStale);

  if (!lastGpsAt || now - lastGpsAt > SENSOR_STALE_MS) setAnnunciator('annGps', 'caution', 'VERİ YOK');
  else if (!gpsFixLabel) setAnnunciator('annGps', 'caution', 'FIX YOK');
  else setAnnunciator('annGps', 'normal', gpsFixLabel);
}

export function initTelemetry(hud, instruments, tacticalMap) {
  initImu(hud, instruments, tacticalMap);
  initGps(tacticalMap);

  document.getElementById('yawResetBtn').addEventListener('click', () => {
    yawOffsetDeg = yawDeg;
    hud.setHeading(0);
    instruments.setHeading(0);
    tacticalMap.setHeading(0);
    logEvent('Yön sıfırlandı (mevcut yön = 0°)');
  });

  hud.setHeading(0);
  hud.setAttitude(0, 0);
  instruments.setHeading(0);
  instruments.setAttitude(0, 0);
  updateSensorAnnunciators(instruments);
  setInterval(() => updateSensorAnnunciators(instruments), 500);
}
