# browser-extension — Gmail 웹 기밀 첨부 차단 (Chrome / Edge, MV3)

Gmail 웹에서 파일 첨부(파일 선택, 드래그&드롭, 붙여넣기)를 가로채 기밀 파일이면 막고,
backend `POST /api/logs` 로 `email_send`(`blocked=true`) 를 **직접** 보냅니다.
이후 판단과 보안 담당자 알림은 backend 가 처리합니다. 에이전트(Python)와는 독립적으로 동작합니다.

> 조직 소유 기기에, 사용자 고지 및 조직 정책 하에 배포하는 것을 전제로 합니다.

## 판정

| 조건 | 동작 |
|---|---|
| 파일명에 기밀 키워드 | 즉시 차단 + 안내 + 보고 |
| 크기가 디코이와 같음 | 일단 차단 → SHA-256 확인. 디코이면 보고, 아니면 "다시 첨부" 안내 후 통과 |
| 그 외 | 통과 |

- 디코이 목록은 backend `GET /api/agent/decoys` 에서 1분마다 동기화 (사용자에게 디코이라는 사실은 표시하지 않음)
- backend 가 꺼져 있으면 차단 기록을 확장 저장소에 보관했다가 재전송 (최대 100건)
- 이벤트 `user` 는 Gmail 탭 제목의 계정 이메일, `host` 는 설정값

## 설치 (개발)

1. `chrome://extensions` → 우측 상단 **개발자 모드** 켜기
2. **압축해제된 확장 프로그램을 로드합니다** → 이 `browser-extension/` 폴더 선택
3. 확장 **세부정보 → 확장 프로그램 옵션** 에서 서버 주소 / PC 식별자 확인 후 저장
   (저장하면 디코이 동기화 결과가 표시됨)

회사 배포 시에는 Chrome 정책 `ExtensionInstallForcelist` 로 강제 설치합니다.

## 테스트

```bash
node --test tests/*.test.js
```

## 한계

- Chrome/Edge 의 Gmail 웹만 대상. 다른 브라우저, 확장 비활성화, Gmail 앱은 우회 가능
- 본문에 내용 붙여넣기(텍스트) 유출은 대상 아님
- 이미 드롭된 여러 파일 중 하나라도 걸리면 그 첨부 동작 전체를 막음
- backend 가 localhost 가 아니면 `manifest.json` 의 `host_permissions` 에 주소 추가 필요
