const FIELDS = ["backendUrl", "host", "keywords", "agentKey"];
const $ = (id) => document.getElementById(id);

async function render() {
  const s = await chrome.storage.local.get([...FIELDS, "enabled", "lastSync", "pending"]);
  for (const f of FIELDS) $(f).value = s[f] || "";
  $("enabled").checked = s.enabled !== false;

  const sync = s.lastSync;
  const lines = [];
  if (sync) {
    const at = new Date(sync.at).toLocaleString();
    lines.push(sync.ok ? `디코이 동기화: ${sync.count}개 (${at})` : `디코이 동기화 실패: ${sync.error} (${at})`);
  }
  if (s.pending && s.pending.length) lines.push(`전송 대기 중인 차단 기록: ${s.pending.length}건`);
  $("status").textContent = lines.join("\n");
}

$("save").addEventListener("click", async () => {
  const data = { enabled: $("enabled").checked };
  for (const f of FIELDS) data[f] = $(f).value.trim();
  data.backendUrl = data.backendUrl.replace(/\/+$/, "") || "http://localhost:8000";
  await chrome.storage.local.set(data);
  await chrome.runtime.sendMessage({ type: "dlp-sync-now" });
  await render();
});

render();
