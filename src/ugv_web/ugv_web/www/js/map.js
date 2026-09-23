// Taktik harita (Leaflet): araç konumu, yönü, iz çizgisi ve takip modu
import { MAP_CENTER, MAP_ZOOM, MAP_TILE_URL } from './config.js';

const TILE_ERRORS_BEFORE_NOTICE = 3;

export function initMap() {
  // Tile'lar solarak belirmesin; kontrol arayüzünde gereksiz hareket dikkat dağıtır
  const map = L.map('mapView', { zoomControl: false, fadeAnimation: false }).setView(MAP_CENTER, MAP_ZOOM);
  const tiles = L.tileLayer(MAP_TILE_URL, {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);

  // Sahada internet yoksa altlık gelmez; kullanıcı boş haritayı arıza sanmasın
  const notice = document.getElementById('mapNotice');
  let tileErrors = 0;
  tiles.on('tileerror', () => {
    tileErrors++;
    if (tileErrors >= TILE_ERRORS_BEFORE_NOTICE) notice.hidden = false;
  });
  tiles.on('tileload', () => {
    tileErrors = 0;
    notice.hidden = true;
  });

  setTimeout(() => map.invalidateSize(), 300);

  // Yönü gösteren ok (chevron); kare simgeden aracın nereye baktığı anlaşılmıyordu
  const ugvIcon = L.divIcon({
    className: 'ugv-marker',
    html: '<svg viewBox="0 0 22 22"><path d="M11 1 L20 20 L11 15 L2 20 Z" fill="#fff" stroke="#000" stroke-width="1.5" stroke-linejoin="round"/></svg>',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
  const marker = L.marker(MAP_CENTER, { icon: ugvIcon }).addTo(map);
  // Katedilen iz: haritacılıkta rota/iz için yaygın kullanılan macenta
  const trailLine = L.polyline([], { color: '#d63fd6', weight: 2, opacity: 0.9 }).addTo(map);

  let lastPos = null;
  let follow = true;
  const followBtn = document.getElementById('followBtn');

  function setFollow(value) {
    follow = value;
    followBtn.setAttribute('aria-pressed', String(value));
    if (follow && lastPos) map.panTo(lastPos);
  }

  followBtn.addEventListener('click', () => setFollow(!follow));
  // Kullanıcı haritayı elle kaydırınca takibi bırak, yoksa harita geri zıplar
  map.on('dragstart', () => setFollow(false));
  document.getElementById('clearTrailBtn').addEventListener('click', () => {
    trailLine.setLatLngs(lastPos ? [lastPos] : []);
  });

  return {
    updatePosition(lat, lon) {
      const pos = [lat, lon];
      marker.setLatLng(pos);
      trailLine.addLatLng(pos);
      if (!lastPos) map.setView(pos, map.getZoom(), { animate: false });
      else if (follow) map.panTo(pos);
      lastPos = pos;
    },
    // heading: pusula yönü (saat yönünde, 0 = kuzey)
    setHeading(heading) {
      const svg = marker.getElement()?.querySelector('svg');
      if (svg) svg.style.transform = `rotate(${heading}deg)`;
    },
    // Harita kutusunun boyutu değişince (büyüt/küçült) Leaflet'e bildir
    invalidate() {
      map.invalidateSize();
      if (follow && lastPos) map.panTo(lastPos, { animate: false });
    },
  };
}
