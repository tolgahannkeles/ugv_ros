// Giriş noktası: vendor/ altındaki kütüphaneler yüklendiyse araç tanımını
// (/vehicle.json: hız sınırları) alıp uygulamayı başlatır.
// Biri eksikse (ör. eksik kurulum) boş/bozuk sayfa yerine açık bir hata gösterir.
import { showFatal } from './ui.js';
import { applyVehicleLimits } from './config.js';

const REQUIRED_GLOBALS = [['ROSLIB', 'roslib'], ['L', 'Leaflet']];

const missing = REQUIRED_GLOBALS
  .filter(([globalName]) => !(globalName in window))
  .map(([, libName]) => libName);

if (missing.length > 0) {
  showFatal(`Yüklenemeyen kütüphane: ${missing.join(', ')}. `
    + 'ugv_web paketini yeniden derleyip (colcon build) sayfayı yenileyin.');
} else {
  fetch('vehicle.json')
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then(
      (drive) => {
        applyVehicleLimits(drive);
        import('./app.js');
      },
      (err) => showFatal(`Araç tanımı (vehicle.json) okunamadı: ${err.message}. `
        + 'Web sunucusunu (ugv_web) yeniden başlatıp sayfayı yenileyin.'),
    );
}
