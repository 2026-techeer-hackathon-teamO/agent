// Gmail 페이지에서 파일 첨부(파일 선택, 드래그&드롭, 붙여넣기)를 캡처 단계에서 가로챈다.
// 차단 여부는 동기적으로 정해야 하므로 policy.quickVerdict 로 즉시 판단하고,
// SHA-256 계산과 서버 보고는 비동기로 background 에 맡긴다.
(() => {
  const P = globalThis.DlpPolicy;
  const MAX_HASH_BYTES = 100 * 1024 * 1024;
  const DEFAULT_KEYWORDS = "기밀,대외비,confidential,secret";

  const cfg = {
    enabled: true,
    keywords: P.parseKeywords(DEFAULT_KEYWORDS),
    decoys: [],
    host: "",
    allowOnce: new Set(),
  };

  function applySettings(s) {
    if (s.enabled !== undefined) cfg.enabled = s.enabled;
    if (s.keywords !== undefined) cfg.keywords = P.parseKeywords(s.keywords);
    if (s.decoys !== undefined) cfg.decoys = s.decoys || [];
    if (s.host !== undefined) cfg.host = s.host;
  }

  chrome.storage.local.get(["enabled", "keywords", "decoys", "host"], applySettings);
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    const s = {};
    for (const [k, v] of Object.entries(changes)) s[k] = v.newValue;
    applySettings(s);
  });

  // 하나라도 걸리면 이번 첨부 동작 전체를 막는다 (드롭된 FileList 는 일부만 뺄 수 없음)
  function inspect(fileList, trigger) {
    if (!cfg.enabled || !fileList || !fileList.length) return false;
    const flagged = [];
    for (const file of Array.from(fileList)) {
      const v = P.quickVerdict(file, cfg);
      if (v.block) flagged.push({ file, verdict: v });
    }
    if (!flagged.length) return false;

    const confirmed = flagged.filter((f) => f.verdict.reason === "keyword");
    if (confirmed.length) {
      toast(
        "기밀 파일 첨부가 차단되었습니다",
        `${confirmed.map((f) => f.file.name).join(", ")}\n회사 보안 정책에 따라 이 시도는 보안 담당자에게 보고됩니다.`
      );
    } else {
      // 디코이 여부는 사용자에게 드러내지 않는다
      toast("첨부 파일을 보안 검사 중입니다", "잠시 후 안내에 따라 다시 시도해 주세요.");
    }
    for (const f of flagged) report(f.file, f.verdict, trigger);
    return true;
  }

  async function report(file, verdict, trigger) {
    let hash = null;
    let hashSkipped = null;
    if (file.size > MAX_HASH_BYTES) {
      hashSkipped = "too_large";
    } else {
      try {
        const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
        hash = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
      } catch (e) {
        hashSkipped = "read_failed";
      }
    }
    const isDecoy = P.isDecoyHash(hash, cfg);

    // 크기만 디코이와 같았던 일반 파일 → 이번 한 번 통과시키고 다시 첨부하도록 안내
    if (verdict.reason === "decoy_size" && hash && !isDecoy) {
      cfg.allowOnce.add(P.fileKey(file));
      toast("보안 검사 완료", `${file.name}: 다시 첨부해 주세요.`);
      return;
    }
    if (verdict.reason === "decoy_size") {
      toast("첨부가 차단되었습니다", `${file.name}\n회사 보안 정책에 따라 이 파일은 외부로 보낼 수 없습니다.`);
    }

    const event = P.buildEvent({
      file,
      hash,
      hashSkipped,
      classification: verdict.classification,
      isDecoy,
      trigger,
      account: P.parseAccount(document.title),
      cfg,
    });
    chrome.runtime.sendMessage({ type: "dlp-report", event }).catch(() => {});
  }

  function block(e) {
    e.preventDefault();
    e.stopImmediatePropagation();
  }

  window.addEventListener(
    "change",
    (e) => {
      const t = e.target;
      if (!(t instanceof HTMLInputElement) || t.type !== "file") return;
      if (inspect(t.files, "file_input")) {
        block(e);
        t.value = "";
      }
    },
    true
  );

  window.addEventListener(
    "drop",
    (e) => {
      if (inspect(e.dataTransfer && e.dataTransfer.files, "drop")) block(e);
    },
    true
  );

  window.addEventListener(
    "paste",
    (e) => {
      if (inspect(e.clipboardData && e.clipboardData.files, "paste")) block(e);
    },
    true
  );

  function toast(title, body) {
    const host = document.createElement("div");
    const shadow = host.attachShadow({ mode: "closed" });
    shadow.innerHTML = `
      <style>
        .box { position: fixed; top: 16px; left: 50%; transform: translateX(-50%);
               z-index: 2147483647; max-width: 420px; padding: 14px 18px; border-radius: 8px;
               background: #b3261e; color: #fff; font: 14px/1.5 system-ui, sans-serif;
               box-shadow: 0 4px 16px rgba(0,0,0,.3); white-space: pre-line; }
        b { display: block; margin-bottom: 4px; }
      </style>
      <div class="box" role="alert"><b></b><span></span></div>`;
    shadow.querySelector("b").textContent = title;
    shadow.querySelector("span").textContent = body;
    (document.body || document.documentElement).appendChild(host);
    setTimeout(() => host.remove(), 6000);
  }
})();
