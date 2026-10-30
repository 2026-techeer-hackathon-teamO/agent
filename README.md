# agent — Windows 기밀 유출 방지 백그라운드 에이전트 (Python)

사내(인가된 관리 대상) Windows PC에서 백그라운드로 동작하며, **기밀 데이터의 외부 유출을 탐지·차단**하고 관련 로그를 수집해 `backend`로 전송하는 방어 보안(DLP) 에이전트입니다.

> ⚠️ 이 에이전트는 **조직이 소유·관리하는 기기에, 사용자(직원) 고지 및 조직 정책 하에 배포**되는 것을 전제로 합니다. 동의 없는 개인 기기 감시 용도가 아닙니다.

## 구성

```
agent/
├── main.py              # 진입점: 워처들 + 전송 스레드 기동
├── config.py            # .env 기반 설정
├── classifier.py        # 기밀 여부 분류 (경로/파일명/확장자 규칙)
├── sender.py            # 이벤트를 backend /api/logs 로 전송
├── event_bus.py         # 워처 → 전송기 사이의 큐
├── decoy_deployer.py    # backend 디코이를 받아 사용자 Downloads 에 배치
├── decoy_state.py       # 배치 기록 / 자기 배치 이벤트 억제 / 알려진 디코이 해시
├── user_session.py      # 로그인 사용자·Downloads 폴더 해석 (SYSTEM 서비스 대응)
└── watchers/
    ├── file_watcher.py  # watchdog 기반 파일 생성/수정/복사 감시 (USB 복사 포함)
    ├── usb_watcher.py   # 이동식 저장소 연결 감시 (Windows WMI, 그 외 비활성)
    ├── email_watcher.py # Outlook 발신 메일 기밀 첨부 차단 (ItemSend 후킹)
    └── email_policy.py  # 첨부 검사 정책 (기밀 분류 + 디코이 해시)
```

| 기능 | 구현 지점 | 상태 |
|---|---|---|
| 기밀 파일 접근/복사 감시 | `watchers/file_watcher.py` | ✅ watchdog (크로스플랫폼) |
| USB 복사 탐지 | `file_watcher.py`(이동식 드라이브 판별) + `usb_watcher.py`(연결 감지) | ✅ / Windows 전용 |
| 메일 기밀 첨부 차단 | `watchers/email_watcher.py` + `email_policy.py` | ✅ Outlook 데스크톱 (Windows 전용) |
| 로그 서버 전송 | `sender.py` → backend `POST /api/logs` | ✅ |
| 디코이 배치 | `decoy_deployer.py` → backend `GET /api/agent/decoys` | ✅ 원본 바이트 + sha256 검증 후 Downloads 배치 |
| 디코이 유출 탐지 | `file_watcher.py` 가 알려진 디코이 해시를 `file_hash` 로 보고 → backend 가 HIGH 알림 | ✅ |

> Windows 네이티브 감시(USB 연결/메일 COM)는 `pywin32`·`WMI`가 있어야 하며, 그 외 OS에서는 자동 비활성(로그만 남김)됩니다. 파일 감시와 전송은 어느 OS에서든 동작합니다.

## 실행

```bash
cd agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # BACKEND_URL, AGENT_API_KEY, WATCH_PATHS 등 설정
python main.py                  # Ctrl+C 로 종료

# 연결 점검용: 합성 이벤트 1건을 backend로 보내고 종료
python main.py --selftest
```

## 테스트

```bash
pip install pytest
pytest -q
```

## 연동

- 로그 전송: `backend` 의 `POST /api/logs` (구체적 파일 이벤트에는 `file_hash` = 소문자 hex SHA-256)
- 디코이 수신/배치: `backend` 의 `GET /api/agent/decoys`, `GET /api/agent/decoys/{id}/file` (헤더 `X-Agent-Key`)

### 메일 차단 동작

- Outlook `ItemSend` 에서 첨부를 임시 저장해 SHA-256 계산 → 파일명/확장자가 기밀이거나 디코이 해시면 발송 취소
- 첨부마다 `email_send` 이벤트 1건(`blocked=true`, `file_hash`, `detail.to/subject`) → backend 가 판단 후 담당자 알림
- 발신자에게 차단 안내 창 표시. `EMAIL_BLOCK=false` 면 차단 없이 보고만
- 검사 중 오류가 나면 발송 허용(fail-open)하고 로그만 남김
- Outlook 이 실행 중일 때만 붙고(새로 띄우지 않음), 종료/재시작 시 다시 연결
- agent 는 **로그인 사용자 세션**에서 실행해야 함 (SYSTEM 서비스는 사용자 Outlook 에 접근 불가)
- 웹메일(Gmail 웹 등)·Outlook 외 클라이언트는 대상 아님

### 디코이 배치 동작

- 받은 바이트를 그대로 저장 (sha256 + `X-Decoy-SHA256` 검증, 불일치 시 폐기). Mark-of-the-Web 미부착
- 같은 이름의 파일이 있으면 건너뜀 (사용자 파일 보호), 파일명의 경로 구분자 제거
- 배치 기록(`DECOY_STATE_FILE`)에 있으면 재배치하지 않음 — 사용자가 삭제한 디코이도 다시 만들지 않음
- 수정/접근/생성 시각을 2~7일 전으로 설정
- 배치 직후 10초간 해당 경로 이벤트를 file_watcher 가 무시 (배치 자체가 알림이 되지 않도록)
- 로그인 사용자가 없어 Downloads 를 찾지 못하면 다음 주기에 재시도
- 한 PC에 여러 사용자가 있으면 현재 활성 콘솔 사용자에게만 배치

## 관련 레포

- [`backend`](../backend) — 로그 수집 / AI 분석 / 카나리토큰 서버
- [`frontend`](../frontend) — 보안 담당자 대시보드
