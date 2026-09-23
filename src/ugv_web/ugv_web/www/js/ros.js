// rosbridge bağlantı yöneticisi.
// roslibjs yeniden bağlanınca abonelikleri kendiliğinden yenilemediği için her
// bağlantıda yeni bir ROSLIB.Ros açılır ve tanımlı tüm topic'ler ona yeniden bağlanır.
import { ROSBRIDGE_URL, ROS_RECONNECT_MS } from './config.js';

const subscriptions = [];
const publishers = [];
const listeners = new Set();
let ros = null;

function bindTopics(r) {
  subscriptions.forEach(({ def, callback }) => {
    new ROSLIB.Topic({ ros: r, ...def }).subscribe(callback);
  });
  publishers.forEach((p) => {
    p.topic = new ROSLIB.Topic({ ros: r, ...p.def });
  });
}

function open() {
  const r = new ROSLIB.Ros();
  r.on('connection', () => {
    ros = r;
    bindTopics(r);
    listeners.forEach((cb) => cb(true));
  });
  r.on('close', () => {
    if (ros === r) {
      ros = null;
      listeners.forEach((cb) => cb(false));
    }
    setTimeout(open, ROS_RECONNECT_MS);
  });
  r.on('error', () => {}); // Ardından 'close' gelir, yeniden deneme orada
  r.connect(ROSBRIDGE_URL);
}

export function isConnected() {
  return ros !== null;
}

export function onConnectionChange(callback) {
  listeners.add(callback);
}

export function subscribe(def, callback) {
  subscriptions.push({ def, callback });
  if (ros) new ROSLIB.Topic({ ros, ...def }).subscribe(callback);
}

// Bağlantı yokken publish() false döner, mesaj kuyruğa alınmaz
export function advertise(def) {
  const p = { def, topic: ros ? new ROSLIB.Topic({ ros, ...def }) : null };
  publishers.push(p);
  return {
    publish(data) {
      if (!ros || !p.topic) return false;
      p.topic.publish(new ROSLIB.Message(data));
      return true;
    },
  };
}

export function connect() {
  open();
}
