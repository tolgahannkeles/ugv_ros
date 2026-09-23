// Sürüş konsolu: joystick, klavye (WASD / oklar), hız sınırı ve cmd_vel döngüsü
import {
  TOPICS, VELOCITY, DEFAULT_POWER, TELEOP_PERIOD_MS, STOP_PACKET_COUNT,
} from './config.js';
import { advertise, isConnected } from './ros.js';
import { shouldIgnoreKey, isDialogOpen } from './ui.js';

const DRIVE_KEYS = {
  w: 'fwd', arrowup: 'fwd',
  s: 'back', arrowdown: 'back',
  a: 'left', arrowleft: 'left',
  d: 'right', arrowright: 'right',
};

const cmdVel = advertise(TOPICS.cmdVel);

const pressed = { fwd: false, back: false, left: false, right: false };
let powerScale = DEFAULT_POWER / 100;
let targetLin = 0.0;
let targetAng = 0.0;
let stopPacketsSent = 0; // Sürekli sıfır basılmasını engelleyen sayaç
let enabled = true;
let dragPointerId = null;
let onInputReleased = () => {};
const el = {};

// Normalize değeri motorun ölü bölgesini aşacak şekilde ölçekle
function mapVelocity(norm, minVal, maxVal) {
  if (Math.abs(norm) < VELOCITY.deadzone) return 0.0;
  const sign = norm > 0 ? 1.0 : -1.0;
  const ratio = Math.min(Math.abs(norm), 1.0);
  return sign * (minVal + ratio * (maxVal - minVal)) * powerScale;
}

function showCommand(lin, ang) {
  el.hudSpeed.textContent = Math.abs(lin).toFixed(2);
  el.cmdLin.textContent = lin.toFixed(2);
  el.cmdAng.textContent = ang.toFixed(2);
}

function publishTwist(lin, ang) {
  cmdVel.publish({
    linear: { x: lin, y: 0.0, z: 0.0 },
    angular: { x: 0.0, y: 0.0, z: ang },
  });
  showCommand(lin, ang);
}

function sendTwist() {
  if (!isConnected()) return;

  const isCommandActive = enabled
    && (Math.abs(targetLin) > VELOCITY.deadzone || Math.abs(targetAng) > VELOCITY.deadzone);

  if (isCommandActive) {
    stopPacketsSent = 0;
    publishTwist(
      mapVelocity(targetLin, VELOCITY.minLin, VELOCITY.maxLin),
      mapVelocity(targetAng, VELOCITY.minAng, VELOCITY.maxAng),
    );
  } else if (stopPacketsSent < STOP_PACKET_COUNT) {
    // Kontrol bırakıldığında aracı durdurmak için birkaç kez sıfır bas ve sus;
    // hat boş kalınca twist_mux otonom kaçınmaya geçebilir
    publishTwist(0.0, 0.0);
    stopPacketsSent++;
  }
}

// nx, ny: ekran eksenlerinde [-1, 1] (sağ ve aşağı pozitif)
function setKnob(nx, ny) {
  const radius = (el.stick.clientWidth - el.knob.offsetWidth) / 2;
  el.knob.style.transform = `translate(${nx * radius}px, ${ny * radius}px)`;
}

function isDriving() {
  return targetLin !== 0 || targetAng !== 0;
}

function releaseInputs() {
  const wasDriving = isDriving();
  Object.keys(pressed).forEach((k) => { pressed[k] = false; });
  dragPointerId = null;
  el.stick.classList.remove('active');
  targetLin = 0.0;
  targetAng = 0.0;
  setKnob(0, 0);
  if (wasDriving) {
    stopPacketsSent = 0;
    sendTwist();
  }
  return wasDriving;
}

function initJoystick() {
  const { stick } = el;

  function handleJoy(e) {
    const rect = stick.getBoundingClientRect();
    const radius = (stick.clientWidth - el.knob.offsetWidth) / 2;
    const dx = e.clientX - (rect.left + rect.width / 2);
    const dy = e.clientY - (rect.top + rect.height / 2);
    const dist = Math.min(radius, Math.hypot(dx, dy));
    const angle = Math.atan2(dy, dx);

    const nx = (dist * Math.cos(angle)) / radius;
    const ny = (dist * Math.sin(angle)) / radius;
    setKnob(nx, ny);

    // Normalleştirilmiş sürüş oranları [-1.0, 1.0]
    targetAng = -nx;
    targetLin = -ny;
  }

  function endDrag(e) {
    if (e.pointerId !== dragPointerId) return;
    dragPointerId = null;
    stick.classList.remove('active');
    targetLin = 0.0;
    targetAng = 0.0;
    setKnob(0, 0);
  }

  stick.addEventListener('pointerdown', (e) => {
    if (!enabled || dragPointerId !== null) return;
    dragPointerId = e.pointerId;
    // Parmak/fare joystick dışına çıksa da olaylar bu elemana gelsin
    stick.setPointerCapture(e.pointerId);
    stick.classList.add('active');
    handleJoy(e);
  });
  stick.addEventListener('pointermove', (e) => {
    if (e.pointerId === dragPointerId) handleJoy(e);
  });
  // pointercancel: dokunmatikte sistem hareketi araya girerse robot gitmeye devam etmesin
  stick.addEventListener('pointerup', endDrag);
  stick.addEventListener('pointercancel', endDrag);
  stick.addEventListener('lostpointercapture', endDrag);
}

function initKeyboard() {
  function applyKeys() {
    targetLin = (pressed.fwd ? 1.0 : 0.0) - (pressed.back ? 1.0 : 0.0);
    targetAng = (pressed.left ? 1.0 : 0.0) - (pressed.right ? 1.0 : 0.0);
    // Joystick topu klavye girdisini de göstersin (çaprazda daireden taşmasın)
    const len = Math.max(1, Math.hypot(targetLin, targetAng));
    setKnob(-targetAng / len, -targetLin / len);
  }

  window.addEventListener('keydown', (e) => {
    const dir = DRIVE_KEYS[e.key.toLowerCase()];
    if (!dir || shouldIgnoreKey(e) || isDialogOpen()) return;
    e.preventDefault(); // Ok tuşları sayfayı kaydırmasın
    if (!enabled || dragPointerId !== null || pressed[dir]) return;
    pressed[dir] = true;
    applyKeys();
  });
  window.addEventListener('keyup', (e) => {
    const dir = DRIVE_KEYS[e.key.toLowerCase()];
    if (!dir || !pressed[dir]) return;
    pressed[dir] = false;
    if (dragPointerId === null) applyKeys();
  });
}

function setPower(percent) {
  powerScale = percent / 100.0;
  el.slider.value = String(percent);
  el.powerLabel.textContent = `${percent}%`;
  el.presets.forEach((b) => {
    b.setAttribute('aria-pressed', String(Number(b.dataset.power) === percent));
  });
}

export function selectPowerPreset(index) {
  const preset = el.presets[index];
  if (preset) setPower(Number(preset.dataset.power));
}

function initPower() {
  el.slider.addEventListener('input', () => setPower(parseInt(el.slider.value, 10)));
  // Odak slider'da kalırsa ok tuşları sürüş yerine slider'ı değiştirir
  el.slider.addEventListener('change', () => el.slider.blur());
  el.presets.forEach((b) => {
    b.addEventListener('click', () => setPower(Number(b.dataset.power)));
  });
  setPower(DEFAULT_POWER);
}

// Bağlantı yokken veya acil durdurma aktifken sürüşü kilitler
export function setDriveEnabled(value, lock = {}) {
  enabled = value;
  if (!value) releaseInputs();
  el.lock.hidden = value;
  el.lockTitle.textContent = lock.title ?? '';
  el.lockHint.textContent = lock.hint ?? '';
  el.state.textContent = value ? 'HAZIR' : 'KİLİTLİ';
}

// Sekme değişince tuşun keyup'ı hiç gelmeyebilir; takılı kalan tuşla robot gitmesin
function initFocusGuard() {
  const stopOnFocusLoss = () => {
    if (releaseInputs()) onInputReleased();
  };
  window.addEventListener('blur', stopOnFocusLoss);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopOnFocusLoss();
  });
}

export function initTeleop({ onFocusLost } = {}) {
  el.stick = document.getElementById('stick');
  el.knob = document.getElementById('stickKnob');
  el.hudSpeed = document.getElementById('hudSpeed');
  el.cmdLin = document.getElementById('cmdLin');
  el.cmdAng = document.getElementById('cmdAng');
  el.slider = document.getElementById('powerSlider');
  el.powerLabel = document.getElementById('powerLabel');
  el.presets = [...document.querySelectorAll('.segmented [data-power]')];
  el.lock = document.getElementById('driveLock');
  el.lockTitle = document.getElementById('driveLockTitle');
  el.lockHint = document.getElementById('driveLockHint');
  el.state = document.getElementById('driveState');
  if (onFocusLost) onInputReleased = onFocusLost;

  initJoystick();
  initKeyboard();
  initPower();
  initFocusGuard();

  setInterval(sendTwist, TELEOP_PERIOD_MS);
}
