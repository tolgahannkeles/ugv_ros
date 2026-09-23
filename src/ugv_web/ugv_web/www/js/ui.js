// Ortak arayüz yardımcıları: uyarı paneli, uyarı bantları, olay günlüğü, kısayol penceresi

const MAX_LOG_ENTRIES = 100;
const LOG_LEVEL_TAGS = {
  info: 'BİLG', active: 'TAMM', caution: 'DKKT', warning: 'UYRI',
};

// level: 'normal' | 'off' | 'active' | 'caution' | 'warning'
export function setAnnunciator(id, level, text) {
  const ann = document.getElementById(id);
  ann.dataset.level = level;
  ann.querySelector('.ann-value').textContent = text;
}

export function showBanner(id, visible) {
  document.getElementById(id).hidden = !visible;
}

export function setBannerText(id, text) {
  document.getElementById(id).textContent = text;
}

// En yeni kayıt en üstte; operatör geçmişe dönüp neyin ne zaman olduğunu görebilir
export function logEvent(message, level = 'info') {
  const log = document.getElementById('eventLog');
  const li = document.createElement('li');
  li.dataset.level = level;

  const time = document.createElement('time');
  time.textContent = new Date().toLocaleTimeString('tr-TR');
  const tag = document.createElement('span');
  tag.className = 'level';
  tag.textContent = LOG_LEVEL_TAGS[level] ?? LOG_LEVEL_TAGS.info;
  const text = document.createElement('span');
  text.textContent = message;

  li.append(time, tag, text);
  log.prepend(li);
  while (log.children.length > MAX_LOG_ENTRIES) log.lastElementChild.remove();
}

// Kısayollar yazı alanlarında ve değiştirici tuşlarla (Ctrl+S vb.) tetiklenmesin
export function shouldIgnoreKey(e) {
  return e.ctrlKey || e.metaKey || e.altKey
    || Boolean(e.target.closest?.('input, textarea, select, [contenteditable]'));
}

export function isDialogOpen() {
  return document.querySelector('dialog[open]') !== null;
}

export function initHelpDialog() {
  const dialog = document.getElementById('helpDialog');
  document.getElementById('helpBtn').addEventListener('click', () => dialog.showModal());
  return {
    toggle() {
      if (dialog.open) dialog.close();
      else dialog.showModal();
    },
  };
}

export function initClock() {
  const clock = document.getElementById('clock');
  const tick = () => { clock.textContent = new Date().toLocaleTimeString('tr-TR'); };
  tick();
  setInterval(tick, 1000);
}

export function showFatal(detail) {
  document.getElementById('fatalDetail').textContent = detail;
  document.getElementById('fatalError').hidden = false;
}
