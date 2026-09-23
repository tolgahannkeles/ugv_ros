// Giriş noktası: CDN kütüphaneleri yüklendiyse uygulamayı başlatır.
// Yüklenmediyse (ör. sahada internet yok) boş/bozuk sayfa yerine açık bir hata gösterir.
import { showFatal } from './ui.js';

const REQUIRED_GLOBALS = [['ROSLIB', 'roslib'], ['L', 'Leaflet']];

const missing = REQUIRED_GLOBALS
  .filter(([globalName]) => !(globalName in window))
  .map(([, libName]) => libName);

if (missing.length > 0) {
  showFatal(`Yüklenemeyen kütüphane: ${missing.join(', ')}. `
    + 'Bu cihazın internete erişimi olduğundan emin olup sayfayı yenileyin.');
} else {
  import('./app.js');
}
