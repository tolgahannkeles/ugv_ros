// Grafik göstergeler: pusula (yön), yandan silüetli boyuna eğim (pitch) ve
// arkadan silüetli yanal eğim (roll). Kara aracı eğim göstergelerinde olduğu gibi
// silüet gerçek açıyla yatar; skaladaki amber/kırmızı bölgeler devrilme riskini gösterir.
import { TILT_CAUTION_DEG, TILT_WARNING_DEG } from './config.js';

const SVG_NS = 'http://www.w3.org/2000/svg';
const SCALE_MAX_DEG = 45;
const COMPASS_POINTS = ['K', 'KD', 'D', 'GD', 'G', 'GB', 'B', 'KB'];

function svgEl(name, attrs, parent) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  parent.append(node);
  return node;
}

// deg: dikeyden saat yönünde açı
function polar(cx, cy, r, deg) {
  const a = (deg * Math.PI) / 180;
  return [cx + r * Math.sin(a), cy - r * Math.cos(a)];
}

function arcPath(cx, cy, r, from, to) {
  const [x1, y1] = polar(cx, cy, r, from);
  const [x2, y2] = polar(cx, cy, r, to);
  return `M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

export function tiltLevel(deg) {
  const abs = Math.abs(deg);
  if (abs >= TILT_WARNING_DEG) return 'warning';
  if (abs >= TILT_CAUTION_DEG) return 'caution';
  return 'normal';
}

// Yandan görünüş: paletli şasi, ön taraf sağda (kamera direği önde)
function drawSideView(g, cx, cy) {
  svgEl('rect', { class: 'inst-body', x: cx - 22, y: cy + 1, width: 44, height: 12, rx: 6 }, g);
  [-14, 0, 14].forEach((dx) => svgEl('circle', { class: 'inst-detail', cx: cx + dx, cy: cy + 7, r: 3.2 }, g));
  svgEl('path', { class: 'inst-body', d: `M${cx - 18} ${cy + 1} V${cy - 7} H${cx + 12} L${cx + 19} ${cy + 1} Z` }, g);
  svgEl('rect', { class: 'inst-body', x: cx + 8, y: cy - 14, width: 3, height: 7 }, g);
  svgEl('rect', { class: 'inst-body', x: cx + 6, y: cy - 17, width: 8, height: 4 }, g);
}

// Arkadan görünüş: iki palet ve arada gövde
function drawRearView(g, cx, cy) {
  svgEl('rect', { class: 'inst-body', x: cx - 22, y: cy - 5, width: 10, height: 18, rx: 2 }, g);
  svgEl('rect', { class: 'inst-body', x: cx + 12, y: cy - 5, width: 10, height: 18, rx: 2 }, g);
  svgEl('rect', { class: 'inst-body', x: cx - 13, y: cy - 8, width: 26, height: 16 }, g);
  svgEl('rect', { class: 'inst-body', x: cx - 1.5, y: cy - 15, width: 3, height: 7 }, g);
  svgEl('rect', { class: 'inst-body', x: cx - 4, y: cy - 18, width: 8, height: 4 }, g);
}

function buildTiltGauge(svg, drawVehicle) {
  const cx = 50;
  const cy = 54;
  const r = 40;

  svgEl('path', { class: 'inst-scale', d: arcPath(cx, cy, r, -SCALE_MAX_DEG, SCALE_MAX_DEG) }, svg);
  [[TILT_CAUTION_DEG, TILT_WARNING_DEG, 'inst-zone-caution'], [TILT_WARNING_DEG, SCALE_MAX_DEG, 'inst-zone-warning']]
    .forEach(([from, to, cls]) => {
      svgEl('path', { class: cls, d: arcPath(cx, cy, r, from, to) }, svg);
      svgEl('path', { class: cls, d: arcPath(cx, cy, r, -to, -from) }, svg);
    });

  for (let d = -40; d <= 40; d += 10) {
    const len = d % 30 === 0 ? 7 : 4;
    const [x1, y1] = polar(cx, cy, r, d);
    const [x2, y2] = polar(cx, cy, r - len, d);
    svgEl('line', { class: 'inst-tick', x1, y1, x2, y2 }, svg);
  }
  [-30, 0, 30].forEach((d) => {
    const [x, y] = polar(cx, cy, r + 6, d);
    svgEl('text', { class: 'inst-label', x, y: y + 2.5 }, svg).textContent = String(Math.abs(d));
  });

  // Yatay referans (düz zemin)
  svgEl('line', { class: 'inst-ref', x1: 12, y1: cy, x2: 88, y2: cy }, svg);

  const g = svgEl('g', {}, svg);
  svgEl('line', { class: 'inst-needle', x1: cx, y1: cy - 20, x2: cx, y2: cy - r + 8 }, g);
  svgEl('path', { class: 'inst-needle-tip', d: `M${cx} ${cy - r + 2} L${cx - 3} ${cy - r + 8} L${cx + 3} ${cy - r + 8} Z` }, g);
  drawVehicle(g, cx, cy);
  return { g, cx, cy };
}

function buildCompass(svg) {
  const cx = 50;
  const cy = 47;
  const r = 38;

  svgEl('circle', { class: 'inst-scale', cx, cy, r }, svg);
  for (let d = 0; d < 360; d += 10) {
    const len = d % 30 === 0 ? 6 : 3;
    const [x1, y1] = polar(cx, cy, r, d);
    const [x2, y2] = polar(cx, cy, r - len, d);
    svgEl('line', { class: 'inst-tick', x1, y1, x2, y2 }, svg);
  }
  [[0, 'K'], [90, 'D'], [180, 'G'], [270, 'B']].forEach(([d, label]) => {
    const [x, y] = polar(cx, cy, r - 12, d);
    const cls = d === 0 ? 'inst-label inst-label-north' : 'inst-label';
    svgEl('text', { class: cls, x, y: y + 3 }, svg).textContent = label;
  });

  // Üstten görünüş araç; kuzey yukarıda sabit, araç yönüne göre döner (harita ile aynı)
  const g = svgEl('g', {}, svg);
  svgEl('line', { class: 'inst-needle', x1: cx, y1: cy - 16, x2: cx, y2: cy - r + 7 }, g);
  svgEl('rect', { class: 'inst-body', x: cx - 9, y: cy - 10, width: 4, height: 20, rx: 1 }, g);
  svgEl('rect', { class: 'inst-body', x: cx + 5, y: cy - 10, width: 4, height: 20, rx: 1 }, g);
  svgEl('rect', { class: 'inst-body', x: cx - 5, y: cy - 8, width: 10, height: 16 }, g);
  svgEl('path', { class: 'inst-needle-tip', d: `M${cx} ${cy - 17} L${cx - 4} ${cy - 11} L${cx + 4} ${cy - 11} Z` }, g);
  return { g, cx, cy };
}

function clampScale(deg) {
  return Math.max(-SCALE_MAX_DEG, Math.min(SCALE_MAX_DEG, deg));
}

// Yuvarlama sonrası -0.0 yerine +0.0 göster
function formatSigned(value) {
  const rounded = Math.round(value * 10) / 10 || 0;
  return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}`;
}

export function initInstruments() {
  const parts = {
    heading: document.getElementById('instHeading'),
    pitch: document.getElementById('instPitch'),
    roll: document.getElementById('instRoll'),
  };
  const compass = buildCompass(parts.heading.querySelector('svg'));
  const pitchGauge = buildTiltGauge(parts.pitch.querySelector('svg'), drawSideView);
  const rollGauge = buildTiltGauge(parts.roll.querySelector('svg'), drawRearView);

  const value = (part) => part.querySelector('.inst-value span');
  const hint = (part) => part.querySelector('.inst-hint');

  return {
    // heading: pusula yönü, saat yönünde 0..360 (0 = kuzey)
    setHeading(heading) {
      compass.g.setAttribute('transform', `rotate(${heading.toFixed(1)} ${compass.cx} ${compass.cy})`);
      value(parts.heading).textContent = String(Math.round(heading) % 360).padStart(3, '0');
      hint(parts.heading).textContent = COMPASS_POINTS[Math.round(heading / 45) % 8];
    },
    // pitch: burun yukarı pozitif, roll: sağ taraf aşağı pozitif (derece)
    setAttitude(pitch, roll) {
      // Ön taraf sağda: burun yukarı = saat yönünün tersine dönüş
      pitchGauge.g.setAttribute('transform', `rotate(${(-clampScale(pitch)).toFixed(1)} ${pitchGauge.cx} ${pitchGauge.cy})`);
      // Arkadan bakılıyor: sağ taraf aşağı = saat yönünde dönüş
      rollGauge.g.setAttribute('transform', `rotate(${clampScale(roll).toFixed(1)} ${rollGauge.cx} ${rollGauge.cy})`);

      value(parts.pitch).textContent = formatSigned(pitch);
      value(parts.roll).textContent = formatSigned(roll);
      hint(parts.pitch).textContent = Math.abs(pitch) < 1 ? 'DÜZ' : (pitch > 0 ? 'BURUN YUKARI' : 'BURUN AŞAĞI');
      hint(parts.roll).textContent = Math.abs(roll) < 1 ? 'DÜZ' : (roll > 0 ? 'SAĞA YATIK' : 'SOLA YATIK');
      parts.pitch.dataset.level = tiltLevel(pitch);
      parts.roll.dataset.level = tiltLevel(roll);
    },
    setStale(stale) {
      Object.values(parts).forEach((part) => part.classList.toggle('is-stale', stale));
    },
  };
}
