// Kamera yayını (web_video_server MJPEG): kopunca uyarı gösterir ve yeniden dener
import { CAMERA_STREAM_URL, CAMERA_TOPIC, CAMERA_RETRY_MS } from './config.js';
import { setAnnunciator, logEvent } from './ui.js';

export function initCamera() {
  const img = document.getElementById('cameraStream');
  const offline = document.getElementById('cameraOffline');
  const viewport = document.getElementById('viewport');
  let retryTimer = null;
  let isOffline = null;

  function setOffline(value) {
    if (isOffline === value) return;
    if (isOffline !== null) logEvent(value ? 'Video yayını kesildi' : 'Video yayını geldi', value ? 'caution' : 'info');
    isOffline = value;
    offline.hidden = !value;
    viewport.classList.toggle('no-camera', value);
    setAnnunciator('annCam', value ? 'caution' : 'normal', value ? 'YOK' : 'AKTİF');
  }

  function connect() {
    clearTimeout(retryTimer);
    // Tarayıcı önbelleğindeki hatalı yanıtı kullanmasın diye her denemede farklı URL
    img.src = `${CAMERA_STREAM_URL}&_=${Date.now()}`;
  }

  img.addEventListener('error', () => {
    setOffline(true);
    retryTimer = setTimeout(connect, CAMERA_RETRY_MS);
  });
  // MJPEG akışında 'load' olayı tarayıcıya göre gelmeyebilir; ilk kare çözülünce
  // naturalWidth dolduğu için onu da kontrol et
  img.addEventListener('load', () => setOffline(false));
  setInterval(() => {
    if (isOffline !== false && img.naturalWidth > 0) setOffline(false);
  }, 1000);

  document.getElementById('cameraRetryBtn').addEventListener('click', connect);
  document.getElementById('hudSource').textContent = `KAYNAK ${CAMERA_TOPIC}`;

  connect();
}
