// Acil durdurma: twist_mux'ın /e_stop kilidini kullanır. Kilidin timeout'u 0
// olduğundan "true" yayınlandıktan sonra "false" gelene kadar robot tüm hız
// kaynaklarını (teleop + otonom) yok sayar; sayfa kapansa bile kilit kalır.
import { TOPICS } from './config.js';
import { advertise, subscribe } from './ros.js';

const eStopPub = advertise(TOPICS.eStop);
const listeners = new Set();
let active = false;

function setActive(value) {
  if (active === value) return;
  active = value;
  listeners.forEach((cb) => cb(active));
}

export function isEStopActive() {
  return active;
}

export function onEStopChange(callback) {
  listeners.add(callback);
}

// Bağlantı yokken de yerel olarak kilitlenir; bağlanınca syncEStop() ile gönderilir
export function engageEStop() {
  eStopPub.publish({ data: true });
  setActive(true);
}

// Robota ulaşamıyorsak kilidi yerelde kaldırmak yanıltıcı olur
export function releaseEStop() {
  if (!eStopPub.publish({ data: false })) return false;
  setActive(false);
  return true;
}

export function syncEStop() {
  if (active) eStopPub.publish({ data: true });
}

export function initEStop({ onReleaseFailed }) {
  const btn = document.getElementById('estopBtn');
  const latched = document.getElementById('estopLatched');

  btn.addEventListener('click', engageEStop);
  document.getElementById('estopReleaseBtn').addEventListener('click', () => {
    if (!releaseEStop()) onReleaseFailed();
  });

  onEStopChange((value) => {
    btn.hidden = value;
    latched.hidden = !value;
  });

  // Başka bir istemcinin (veya terminalden) kilitlemesini/açmasını da yansıt
  subscribe(TOPICS.eStop, (msg) => setActive(msg.data === true));
}
