import httpx
import socket

# 백엔드 서버 주소
BACKEND_URL = "http://localhost:8000/api/logs"

def send_security_log(event_type: str, file_name: str, classification: str, blocked: bool, detail: dict = None):
    """
    보안 로그를 백엔드 서버로 전송하는 함수
    """
    # 전송할 로그 페이로드 구성
    log_payload = {
        "host": socket.gethostname(),           # 현재 PC의 호스트 이름
        "user": "current_user",                 # 사용자 계정명
        "event_type": event_type,               # 이벤트 유형 (예: file_access, usb_copy, email_send)
        "file_name": file_name,                 # 대상 파일 경로 또는 이름
        "classification": classification,       # 분류 등급 (예: confidential)
        "channel": "filesystem",                # 유출 경로 (예: usb, email, filesystem)
        "blocked": blocked,                     # 차단 여부 (True / False)
        "detail": detail or {"note": "사용자 정의 탐지 이벤트"}
    }

    try:
        print(f"[sender] 서버로 로그 전송 중... ({event_type}: {file_name})")
        
        # POST 요청 전송 (타임아웃 5초 설정)
        response = httpx.post(BACKEND_URL, json=log_payload, timeout=5.0)
        
        if response.status_code == 200:
            print(f"[sender] ✅ 로그 전송 성공! 서버 응답: {response.json()}")
            return True
        else:
            print(f"[sender] ❌ 로그 전송 실패 (상태 코드: {response.status_code})")
            print(f"서버 응답: {response.text}")
            return False
            
    except httpx.RequestError as e:
        print(f"[sender] 🔌 서버 연결 오류 (서버가 켜져 있는지 확인하세요): {e}")
        return False

if __name__ == "__main__":
    # 테스트용 기밀 파일 유출 의심 로그 전송 예시
    send_security_log(
        event_type="usb_copy",
        file_name="C:\\Users\\Documents\\기밀_재무보고서.xlsx",
        classification="confidential",
        blocked=True,
        detail={"usb_drive": "E:\\", "reason": "이동식 디스크로 기밀 파일 복사 시도 차단"}
    )