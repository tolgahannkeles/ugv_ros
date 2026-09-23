// OTONOM DESTEK (ÇARPMA ÖNLEYİCİ) — açıksa collision_guard, PC'deki YOLO'nun
// /obstacle_zones sinyaline bakıp ileri hareketi keser
import { TOPICS, OBSTACLE_TIMEOUT_MS } from './config.js';
import { advertise, subscribe } from './ros.js';
import { setAnnunciator, showBanner, logEvent } from './ui.js';

const assistPub = advertise(TOPICS.assistEnabled);

let assistEnabled = false;
let blocking = false;
let zones = null; // [sol, orta, sağ]
let zonesAt = 0;
const el = {};

export function publishAssistState() {
  assistPub.publish({ data: assistEnabled });
}

function renderAnnunciator() {
  if (!assistEnabled) setAnnunciator('annAssist', 'off', 'KAPALI');
  else if (blocking) setAnnunciator('annAssist', 'caution', 'KESİYOR');
  else setAnnunciator('annAssist', 'active', 'AÇIK');
}

function renderZones() {
  const fresh = zones !== null && performance.now() - zonesAt < OBSTACLE_TIMEOUT_MS;
  // Panel ve video üstündeki bantlar aynı veriyi gösterir
  [el.zones, el.bands].forEach((cells) => {
    cells.forEach((cell, i) => {
      if (!fresh) cell.dataset.state = 'unknown';
      else cell.dataset.state = zones[i] ? 'blocked' : 'clear';
    });
  });

  if (!fresh) {
    el.status.textContent = 'Engel verisi yok (PC tarafındaki tespit çalışmıyor olabilir)';
  } else if (zones.some(Boolean)) {
    el.status.textContent = assistEnabled
      ? 'Engel var — ileri hareket kesilir'
      : 'Engel var — destek kapalı, müdahale edilmiyor';
  } else {
    el.status.textContent = 'Yol açık';
  }
}

export function setBlocking(value) {
  blocking = assistEnabled && value;
  showBanner('bannerBlocking', blocking);
  renderAnnunciator();
}

function setAssist(value) {
  assistEnabled = value;
  publishAssistState();
  el.switch.setAttribute('aria-checked', String(value));
  setBlocking(false);
  renderZones();
}

export function initAssist() {
  el.switch = document.getElementById('assistSwitch');
  el.zones = [...document.querySelectorAll('.zone')];
  el.bands = [...document.querySelectorAll('.band')];
  el.status = document.getElementById('zonesStatus');

  el.switch.addEventListener('click', () => {
    setAssist(!assistEnabled);
    logEvent(`Çarpışma önleme desteği ${assistEnabled ? 'açıldı' : 'kapatıldı'}`, assistEnabled ? 'active' : 'info');
  });

  subscribe(TOPICS.assistBlocking, (msg) => setBlocking(msg.data === true));

  subscribe(TOPICS.obstacleZones, (msg) => {
    if (msg.data.length < 3) return;
    zones = msg.data.slice(0, 3);
    zonesAt = performance.now();
    renderZones();
  });

  renderAnnunciator();
  renderZones();
  setInterval(renderZones, 500);
}
