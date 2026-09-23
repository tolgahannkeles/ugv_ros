// Modülleri başlatır ve aralarındaki durumu (bağlantı, acil durdurma) bağlar
import { connect, isConnected, onConnectionChange } from './ros.js';
import {
  initClock, initHelpDialog, setAnnunciator, showBanner, setBannerText, logEvent, shouldIgnoreKey,
} from './ui.js';
import { initCamera } from './camera.js';
import { initMap } from './map.js';
import { initHud } from './hud.js';
import { initInstruments } from './instruments.js';
import { initTelemetry } from './telemetry.js';
import { initAssist, publishAssistState, setBlocking } from './assist.js';
import {
  initEStop, engageEStop, isEStopActive, onEStopChange, syncEStop,
} from './estop.js';
import { initTeleop, setDriveEnabled, selectPowerPreset } from './teleop.js';

function initViewSwap(tacticalMap) {
  const viewport = document.getElementById('viewport');
  const cameraPane = document.getElementById('cameraPane');
  const mapPane = document.getElementById('mapPane');
  const btn = document.getElementById('swapBtn');
  let mapMain = false;

  function toggle() {
    mapMain = !mapMain;
    viewport.classList.toggle('map-main', mapMain);
    cameraPane.classList.toggle('pane-main', !mapMain);
    cameraPane.classList.toggle('pane-pip', mapMain);
    mapPane.classList.toggle('pane-main', mapMain);
    mapPane.classList.toggle('pane-pip', !mapMain);
    btn.firstChild.textContent = mapMain ? 'VİDEOYU BÜYÜT ' : 'HARİTAYI BÜYÜT ';
    tacticalMap.invalidate();
  }

  btn.addEventListener('click', toggle);
  return toggle;
}

function refreshDriveLock() {
  if (isEStopActive()) {
    setDriveEnabled(false, {
      title: 'ACİL DUR DEVREDE',
      hint: 'Sürmek için yukarıdan kilidi kaldırın.',
    });
  } else if (!isConnected()) {
    setDriveEnabled(false, {
      title: 'BAĞLANTI YOK',
      hint: 'rosbridge (port 9090) bekleniyor, otomatik yeniden bağlanılacak.',
    });
  } else {
    setDriveEnabled(true);
  }
}

function initShortcuts({ toggleView, help }) {
  window.addEventListener('keydown', (e) => {
    // Acil durdurma odak nerede olursa olsun çalışmalı
    if (e.key === ' ') {
      e.preventDefault();
      if (!isEStopActive()) engageEStop();
      return;
    }
    if (shouldIgnoreKey(e) || e.repeat) return;

    switch (e.key.toLowerCase()) {
      case '1':
      case '2':
      case '3':
        selectPowerPreset(Number(e.key) - 1);
        break;
      case 'm':
        toggleView();
        break;
      case 'h':
      case '?':
        help.toggle();
        break;
      default:
    }
  });
  // Odaklı buton boşluk tuşuyla ayrıca tıklanmasın
  window.addEventListener('keyup', (e) => {
    if (e.key === ' ') e.preventDefault();
  });
}

const help = initHelpDialog();
initClock();
logEvent('Arayüz başlatıldı');
initCamera();

const tacticalMap = initMap();
const hud = initHud();
const toggleView = initViewSwap(tacticalMap);
initTelemetry(hud, initInstruments(), tacticalMap);
initAssist();
initEStop({
  onReleaseFailed: () => logEvent('Bağlantı yokken acil dur kilidi kaldırılamaz', 'caution'),
});
initTeleop({
  onFocusLost: () => logEvent('Pencere odağı kaybedildi, araç durduruldu', 'caution'),
});
initShortcuts({ toggleView, help });

onConnectionChange((connected) => {
  if (connected) {
    setAnnunciator('annLink', 'normal', 'BAĞLI');
    // Araç tarafı yeniden başlamış olabilir; arayüzdeki durumu tekrar gönder
    publishAssistState();
    syncEStop();
    logEvent('Araca bağlanıldı');
  } else {
    setAnnunciator('annLink', 'warning', 'KOPTU');
    setBannerText('bannerOffline', 'BAĞLANTI KOPTU — YENİDEN BAĞLANILIYOR…');
    setBlocking(false);
    logEvent('Araç bağlantısı koptu', 'warning');
  }
  showBanner('bannerOffline', !connected);
  refreshDriveLock();
});

onEStopChange((active) => {
  showBanner('bannerEStop', active);
  setAnnunciator('annEStop', active ? 'warning' : 'normal', active ? 'DEVREDE' : 'SERBEST');
  logEvent(active ? 'Acil dur devreye alındı' : 'Acil dur kilidi kaldırıldı', active ? 'warning' : 'info');
  refreshDriveLock();
});

// İlk bağlantı kurulana kadar "bağlanılıyor" durumu
showBanner('bannerOffline', true);
setDriveEnabled(false, {
  title: 'BAĞLANILIYOR',
  hint: 'rosbridge (port 9090) bekleniyor.',
});
connect();
