// 서비스 워커: 디코이 목록 동기화 + 차단 이벤트를 backend /api/logs 로 직접 전송.
// 확장 권한(host_permissions)으로 요청하므로 backend CORS 설정과 무관하다.
const DEFAULTS = {
  enabled: true,
  backendUrl: "http://localhost:8000",
  host: "",
  keywords: "기밀,대외비,confidential,secret",
  agentKey: "",
  decoys: [],
  pending: [],
};
const MAX_PENDING = 100;

async function settings() {
  return chrome.storage.local.get(DEFAULTS);
}

function headers(s, extra = {}) {
  const h = { ...extra };
  if (s.agentKey) h["X-Agent-Key"] = s.agentKey;
  return h;
}

async function syncDecoys() {
  const s = await settings();
  try {
    const resp = await fetch(`${s.backendUrl}/api/agent/decoys`, { headers: headers(s) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const list = await resp.json();
    const decoys = list.map((d) => ({ sha256: d.sha256, size: d.size, file_name: d.file_name }));
    await chrome.storage.local.set({ decoys, lastSync: { ok: true, at: Date.now(), count: decoys.length } });
  } catch (e) {
    await chrome.storage.local.set({ lastSync: { ok: false, at: Date.now(), error: String(e) } });
  }
}

async function post(s, event) {
  const resp = await fetch(`${s.backendUrl}/api/logs`, {
    method: "POST",
    headers: headers(s, { "Content-Type": "application/json" }),
    body: JSON.stringify(event),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
}

async function report(event) {
  const s = await settings();
  try {
    await post(s, event);
  } catch (e) {
    // 서버가 내려가 있어도 차단 기록이 사라지지 않도록 보관 후 재전송
    const pending = [...s.pending, event].slice(-MAX_PENDING);
    await chrome.storage.local.set({ pending });
  }
}

async function flushPending() {
  const s = await settings();
  if (!s.pending.length) return;
  const left = [];
  for (const event of s.pending) {
    try {
      await post(s, event);
    } catch (e) {
      left.push(event);
    }
  }
  await chrome.storage.local.set({ pending: left });
}

chrome.runtime.onInstalled.addListener(async () => {
  const s = await settings();
  await chrome.storage.local.set(s); // 기본값 기록
  chrome.alarms.create("dlp-sync", { periodInMinutes: 1 });
  syncDecoys();
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("dlp-sync", { periodInMinutes: 1 });
  syncDecoys();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== "dlp-sync") return;
  syncDecoys();
  flushPending();
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "dlp-report" && msg.event) {
    report(msg.event).then(() => sendResponse({ ok: true }));
    return true; // 비동기 응답
  }
  if (msg && msg.type === "dlp-sync-now") {
    syncDecoys().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});
