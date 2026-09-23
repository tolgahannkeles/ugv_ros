// Video üstü göstergeler: yön şeridi (heading tape) ve yapay ufuk çizgisi

const PX_PER_DEG = 4;
const TICK_STEP_DEG = 5;
const LABEL_STEP_DEG = 30;
const CARDINALS = { 0: 'K', 90: 'D', 180: 'G', 270: 'B' };
const PITCH_PX_PER_DEG = 3;
const PITCH_LIMIT_PX = 80;

// Yuvarlama sonrası -0.0 yerine +0.0 göster
function formatSigned(value) {
  const rounded = Math.round(value * 10) / 10 || 0;
  return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}`;
}

// Şerit -360..720° aralığında çizilir; ortadaki tur görünür tutulur, böylece
// 359° -> 0° geçişinde atlama olmaz
function buildTape(strip) {
  const frag = document.createDocumentFragment();
  for (let deg = -360; deg <= 720; deg += TICK_STEP_DEG) {
    const x = (deg + 360) * PX_PER_DEG;
    const norm = ((deg % 360) + 360) % 360;

    const tick = document.createElement('div');
    tick.className = `tick ${deg % 10 === 0 ? 'major' : 'minor'}`;
    tick.style.left = `${x}px`;
    frag.append(tick);

    if (deg % LABEL_STEP_DEG === 0) {
      const label = document.createElement('span');
      label.className = `tick-label${norm in CARDINALS ? ' cardinal' : ''}`;
      label.textContent = CARDINALS[norm] ?? String(norm / 10).padStart(2, '0');
      label.style.left = `${x}px`;
      frag.append(label);
    }
  }
  strip.append(frag);
}

export function initHud() {
  const strip = document.getElementById('tapeStrip');
  const windowEl = strip.parentElement;
  const readout = document.getElementById('hdgReadout');
  const horizon = document.getElementById('hudHorizon');
  const pitchEl = document.getElementById('hudPitch');
  const rollEl = document.getElementById('hudRoll');

  buildTape(strip);

  return {
    // heading: pusula yönü, saat yönünde artan 0..360
    setHeading(heading) {
      const offset = (heading + 360) * PX_PER_DEG - windowEl.clientWidth / 2;
      strip.style.transform = `translateX(${-offset}px)`;
      readout.textContent = String(Math.round(heading) % 360).padStart(3, '0');
    },
    // pitch: burun yukarı pozitif, roll: sağ taraf aşağı pozitif (derece)
    setAttitude(pitch, roll) {
      const offset = Math.max(-PITCH_LIMIT_PX, Math.min(PITCH_LIMIT_PX, pitch * PITCH_PX_PER_DEG));
      horizon.style.transform = `translate(-50%, ${offset}px) rotate(${-roll}deg)`;
      pitchEl.textContent = formatSigned(pitch);
      rollEl.textContent = formatSigned(roll);
    },
  };
}
