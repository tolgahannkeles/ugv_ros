// Giriş noktası: vendor/ altındaki kütüphaneler yüklendiyse uygulamayı başlatır.
// Yüklenmediyse (ör. eksik kurulum) boş/bozuk sayfa yerine açık bir hata gösterir.
import { showFatal } from './ui.js';

const REQUIRED_GLOBALS = [['ROSLIB', 'roslib'], ['L', 'Leaflet']];

const missing = REQUIRED_GLOBALS
  .filter(([globalName]) => !(globalName in window))
  .map(([, libName]) => libName);

if (missing.length > 0) {
  showFatal(`Yüklenemeyen kütüphane: ${missing.join(', ')}. `
    + 'ugv_web paketini yeniden derleyip (colcon build) sayfayı yenileyin.');
} else {
  import('./app.js');
}
