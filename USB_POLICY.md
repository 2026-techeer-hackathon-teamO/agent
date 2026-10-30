# USB 쓰기 차단과 서버 보고

`USB_BLOCK_WRITES=true`(기본값)로 관리자 터미널에서 `python main.py`를 실행하면
Windows 이동식 디스크 쓰기 금지 정책을 설정하고 읽어 확인합니다.
설정 경로는 `HKLM\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices\{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}`의 `Deny_Write=1`입니다.

**기밀 파일을 포함한 모든 파일 쓰기를 차단**합니다. 휴대전화 MTP 및 고정 디스크로
인식되는 USB 장치는 보장 범위가 아닙니다. 초기 설정 후 Windows를 재시작하고 실제
USB로 복사, 이동, 다른 이름으로 저장을 검증하세요. 설정 확인은 실제 차단 검증과 다릅니다.

정책은 에이전트 종료 후에도 유지됩니다. `USB_BLOCK_WRITES=false`는 설정을 건너뛰며
기존 정책을 해제하지 않습니다. 해제는 관리자가 조직 정책에 따라 같은 그룹 정책을
변경하거나 위 값만 제거한 뒤 재시작해야 합니다. 다른 조직 정책도 영향을 줄 수 있습니다.

`BACKEND_URL`의 `POST /api/logs`로 정책 결과와 기존 USB 연결/파일 감지 이벤트를
전송합니다. `AGENT_API_KEY`가 있으면 `X-Agent-Key` 헤더를 보냅니다.
파일 원문은 업로드하지 않습니다.

정책 이벤트는 기존 서버 종류 `usb_copy`를 사용하며 `detail.action=usb_write_policy`,
`detail.status=configured|failed`로 구분합니다. `blocked=false`는 개별 복사 차단을
관측하지 않았다는 뜻입니다. OS가 거절한 쓰기는 watchdog 이벤트가 없을 수 있어
차단된 개별 파일명이나 원본 경로를 보고하지 않습니다.

전송 실패는 1~30초 지수 백오프로 재시도합니다. 큐는 메모리 기반으로 프로세스 종료 시
미전송 로그가 보존되지 않으며 서버 장애가 길면 큐가 증가합니다. 서버 응답이 유실되면
중복 로그가 생길 수 있습니다. 영구적인 서버 오류도 수정될 때까지 재시도합니다.

정책 설정 실패 시 경고와 실패 이벤트를 기록하고 감시를 계속합니다. 해당 단말을
보호 중으로 취급하면 안 됩니다. 실행 중 정책 변경은 자동 복구하지 않습니다.

검증: `python -m pytest -q`. 정책 테스트는 레지스트리를 모의 처리하므로 실제 PC 설정을
변경하지 않습니다. 실제 USB와 서버를 통한 통합 검증은 별도로 수행해야 합니다.

## 개발 환경 (Windows PowerShell)

Python 3.13 설치 후 프로젝트 폴더에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pip check
```

2026-10-31 검증: Python 3.13.16, 전체 35개 테스트 통과, 의존성 충돌 없음.
로컬 HTTP 서버에서 503 응답 후 재시도, 인증 헤더 및 동일 이벤트 수신을 확인했습니다.
샌드박스에서는 임시 폴더와 로컬 통신 접근 제한으로 실패하여 승인된 제한 밖 환경에서
테스트했습니다. 실제 레지스트리 정책 적용, 재시작 후 USB 쓰기 차단 및 운영 서버의
스키마 수용 여부는 이 자동 테스트 결과에 포함되지 않습니다.

참고: [Microsoft 이동식 저장소 정책](https://learn.microsoft.com/en-us/windows/client-management/mdm/policy-csp-admx-removablestorage)
