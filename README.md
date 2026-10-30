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
├── decoy_deployer.py    # backend 디코이를 받아 PC에 배치
└── watchers/
    ├── file_watcher.py  # watchdog 기반 파일 생성/수정/복사 감시 (USB 복사 포함)
    ├── usb_watcher.py   # 이동식 저장소 연결 감시 (Windows WMI, 그 외 비활성)
    └── email_watcher.py # 메일 첨부 유출 감시 (Outlook/SMTP 스텁)
```

| 기능 | 구현 지점 | 상태 |
|---|---|---|
| 기밀 파일 접근/복사 감시 | `watchers/file_watcher.py` | ✅ watchdog (크로스플랫폼) |
| USB 복사 탐지 | `file_watcher.py`(이동식 드라이브 판별) + `usb_watcher.py`(연결 감지) | ✅ / Windows 전용 |
| 메일 유출 감시 | `watchers/email_watcher.py` | 🚧 스텁 (Outlook COM/SMTP 후크 TODO) |
| 로그 서버 전송 | `sender.py` → backend `POST /api/logs` | ✅ |
| 디코이 배치 | `decoy_deployer.py` → backend `GET /api/decoys` | 🚧 스텁 (파일 배치까지, 비콘 임베드 TODO) |

> Windows 네이티브 감시(USB 연결/메일 COM)는 `pywin32`·`WMI`가 있어야 하며, 그 외 OS에서는 자동 비활성(로그만 남김)됩니다. 파일 감시와 전송은 어느 OS에서든 동작합니다.

## 실행

```bash
cd agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # BACKEND_URL, WATCH_PATHS 등 설정
python main.py                  # Ctrl+C 로 종료

# 연결 점검용: 합성 이벤트 1건을 backend로 보내고 종료
python main.py --selftest
```

## 연동

- 로그 전송: `backend` 의 `POST /api/logs`
- 디코이 수신/배치: `backend` 의 `GET /api/decoys`

## 관련 레포

- [`backend`](../backend) — 로그 수집 / AI 분석 / 카나리토큰 서버
- [`frontend`](../frontend) — 보안 담당자 대시보드
