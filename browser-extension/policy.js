// Gmail 첨부 차단 판정 (DOM/크롬 API 없음 → content script 와 node 테스트가 함께 사용).
//
// 첨부 이벤트는 동기적으로 막아야 하므로 1차 판정은 파일명 키워드 + 디코이 크기로 즉시 한다.
// 디코이 해시는 비동기로 계산해 로그에 싣고, 크기만 같았던 일반 파일이면 allowOnce 로 풀어준다.
(function (root) {
  const CHANNEL = "email:gmail-web";

  function parseKeywords(text) {
    return String(text || "")
      .split(",")
      .map((k) => k.trim().toLowerCase())
      .filter(Boolean);
  }

  function classifyName(name, keywords) {
    const lower = String(name || "").toLowerCase();
    return keywords.some((kw) => lower.includes(kw)) ? "confidential" : null;
  }

  function fileKey(file) {
    return `${file.name}|${file.size}|${file.lastModified}`;
  }

  function quickVerdict(file, cfg) {
    if (classifyName(file.name, cfg.keywords)) {
      return { block: true, reason: "keyword", classification: "confidential" };
    }
    const sameSize = cfg.decoys.some((d) => d.size === file.size);
    if (sameSize && !cfg.allowOnce.has(fileKey(file))) {
      return { block: true, reason: "decoy_size", classification: null };
    }
    return { block: false, reason: null, classification: null };
  }

  function isDecoyHash(hash, cfg) {
    if (!hash) return false;
    const h = hash.toLowerCase();
    return cfg.decoys.some((d) => String(d.sha256).toLowerCase() === h);
  }

  // backend app/models.py:LogIn 형식
  function buildEvent({ file, hash, hashSkipped, classification, isDecoy, trigger, account, cfg }) {
    const detail = { source: "chrome-extension", trigger };
    if (isDecoy) detail.decoy = true;
    if (hashSkipped) detail.hash_skipped = hashSkipped;
    return {
      host: cfg.host || "unknown-host",
      user: account || "unknown",
      event_type: "email_send",
      file_name: file.name,
      file_hash: hash || null,
      classification: classification || "confidential",
      channel: CHANNEL,
      blocked: true,
      detail,
    };
  }

  // Gmail 탭 제목: "받은편지함 (3) - kim@corp.com - Gmail"
  function parseAccount(title) {
    const m = String(title || "").match(/[\w.+-]+@[\w-]+(\.[\w-]+)+/);
    return m ? m[0] : "";
  }

  const api = { parseKeywords, classifyName, fileKey, quickVerdict, isDecoyHash, buildEvent, parseAccount };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DlpPolicy = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
