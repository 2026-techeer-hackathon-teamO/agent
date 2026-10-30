const test = require("node:test");
const assert = require("node:assert/strict");
const policy = require("../policy.js");

const SHA = "ab".repeat(32);
const cfg = (over = {}) => ({
  keywords: ["기밀", "대외비", "confidential", "secret"],
  decoys: [{ sha256: SHA, size: 18, file_name: "2026_인사평가_기밀.txt" }],
  host: "PC-01",
  allowOnce: new Set(),
  ...over,
});
const file = (name, size = 10, lastModified = 1) => ({ name, size, lastModified });

test("키워드가 들어간 파일명은 기밀 (대소문자 무시)", () => {
  assert.equal(policy.classifyName("Q3_CONFIDENTIAL.pdf", cfg().keywords), "confidential");
  assert.equal(policy.classifyName("2026_기밀_보고.xlsx", cfg().keywords), "confidential");
  assert.equal(policy.classifyName("lunch.png", cfg().keywords), null);
});

test("기밀 파일명은 즉시 차단", () => {
  const v = policy.quickVerdict(file("대외비_계약서.pdf"), cfg());
  assert.equal(v.block, true);
  assert.equal(v.reason, "keyword");
});

test("디코이와 크기가 같으면 이름이 달라도 일단 차단 (해시는 비동기 확인)", () => {
  const v = policy.quickVerdict(file("notes.txt", 18), cfg());
  assert.equal(v.block, true);
  assert.equal(v.reason, "decoy_size");
});

test("일반 파일은 통과", () => {
  assert.equal(policy.quickVerdict(file("photo.png", 99), cfg()).block, false);
});

test("해시 확인으로 디코이가 아니라고 풀린 파일은 다시 첨부 시 통과", () => {
  const f = file("notes.txt", 18, 42);
  const c = cfg({ allowOnce: new Set([policy.fileKey(f)]) });
  assert.equal(policy.quickVerdict(f, c).block, false);
});

test("allowOnce 는 키워드 파일을 풀어주지 않음", () => {
  const f = file("기밀.txt", 18, 42);
  const c = cfg({ allowOnce: new Set([policy.fileKey(f)]) });
  assert.equal(policy.quickVerdict(f, c).block, true);
});

test("디코이 해시 판정은 소문자 무관", () => {
  assert.equal(policy.isDecoyHash(SHA.toUpperCase(), cfg()), true);
  assert.equal(policy.isDecoyHash("cd".repeat(32), cfg()), false);
  assert.equal(policy.isDecoyHash(null, cfg()), false);
});

test("backend LogIn 형식의 차단 이벤트 생성", () => {
  const ev = policy.buildEvent({
    file: file("기밀.docx"),
    hash: SHA,
    classification: "confidential",
    isDecoy: true,
    trigger: "drop",
    account: "kim@corp.com",
    cfg: cfg(),
  });
  assert.deepEqual(ev, {
    host: "PC-01",
    user: "kim@corp.com",
    event_type: "email_send",
    file_name: "기밀.docx",
    file_hash: SHA,
    classification: "confidential",
    channel: "email:gmail-web",
    blocked: true,
    detail: { source: "chrome-extension", trigger: "drop", decoy: true },
  });
});

test("해시를 못 구하면 사유를 detail 에 남김", () => {
  const ev = policy.buildEvent({
    file: file("기밀.zip"),
    hash: null,
    hashSkipped: "too_large",
    classification: "confidential",
    isDecoy: false,
    trigger: "file_input",
    account: "",
    cfg: cfg({ host: "" }),
  });
  assert.equal(ev.file_hash, null);
  assert.equal(ev.detail.hash_skipped, "too_large");
  assert.equal(ev.host, "unknown-host");
  assert.equal(ev.user, "unknown");
});

test("Gmail 탭 제목에서 계정 이메일 추출", () => {
  assert.equal(policy.parseAccount("받은편지함 (3) - kim@corp.com - Gmail"), "kim@corp.com");
  assert.equal(policy.parseAccount("Gmail"), "");
});

test("키워드 문자열 파싱", () => {
  assert.deepEqual(policy.parseKeywords(" 기밀, Secret ,,"), ["기밀", "secret"]);
});
