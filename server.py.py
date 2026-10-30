import os
import json
import httpx
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# 환경 변수 로드 (.env 파일 또는 시스템 환경변수)
load_dotenv()

app = FastAPI(title="DLP Security Server - Requirement 3", version="1.0")

# OpenAI 및 Slack 설정
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

class LogIn(BaseModel):
    host: str
    user: str = "unknown"
    event_type: str
    file_name: Optional[str] = None
    classification: Optional[str] = None
    channel: Optional[str] = None
    blocked: bool = False
    detail: Optional[Dict[str, Any]] = None


def analyze_log_with_ai(log_data: dict) -> tuple[bool, str]:
    """
    [해킹 패턴 담당 AI] 로그를 분석하여 실제 해킹 시도나 유출 징후인지 판단
    Returns:
        (is_suspicious: bool, reason: str)
    """
    event_type = log_data.get("event_type", "")
    classification = log_data.get("classification", "")
    blocked = log_data.get("blocked", False)

    # 기밀 파일 관련 이벤트이거나 차단된 경우 AI 정밀 분석 수행
    if classification == "confidential" or blocked or event_type in ["usb_copy", "email_send"]:
        prompt = f"""
        당신은 기업 보안 관제 AI 시스템입니다. 다음 에이전트 로그를 분석하여 실제 해킹 시도나 고의적인 기밀 유출 행위로 판단되는지 평가해주세요.

        로그 정보:
        - 호스트: {log_data.get('host')}
        - 사용자: {log_data.get('user')}
        - 이벤트 유형: {event_type}
        - 파일명: {log_data.get('file_name')}
        - 분류 등급: {classification}
        - 차단 여부: {blocked}
        - 상세 내용: {log_data.get('detail')}

        판단 기준:
        1. 단순 업무 행위인지, 비정상적인 외부 유출/우회 시도인지 평가하세요.
        2. JSON 형식으로만 응답해주세요. (키: `is_suspicious` (boolean), `reason` (string, 한국어로 작성))
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result.get("is_suspicious", False), result.get("reason", "AI 분석 완료")
        except Exception as e:
            print(f"[ai_analyzer] OpenAI API 호출 오류: {e}")
            return True, f"규칙 기반 탐지 (AI 분석 중 오류 발생: {e})"

    return False, "정상 범위의 로그"


def notify_security_officer(alert_message: str, log_data: dict) -> bool:
    """[보안 담당자 알림] 해킹 의심 시 슬랙(Slack) 웹훅으로 경고 전송"""
    if not SLACK_WEBHOOK_URL:
        print(f"[notifier] ⚠️ 슬랙 웹훅 URL 미설정. 알림 내용:\n{alert_message}")
        return False

    payload = {
        "text": f"🚨 *[보안 경고] 해킹 및 기밀 유출 의심 징후 포착!*\n\n"
                f"> *AI 분석 결과:* {alert_message}\n"
                f"> *발생 호스트:* `{log_data.get('host', 'unknown')}`\n"
                f"> *사용자:* `{log_data.get('user', 'unknown')}`\n"
                f"> *이벤트 유형:* `{log_data.get('event_type', 'unknown')}`\n"
                f"> *대상 파일:* `{log_data.get('file_name', 'N/A')}`"
    }

    try:
        with httpx.Client(timeout=5.0) as http_client:
            response = http_client.post(SLACK_WEBHOOK_URL, json=payload)
            if response.status_code == 200:
                print("[notifier] 보안 담당자에게 슬랙 알림 전송 성공")
                return True
            else:
                print(f"[notifier] 슬랙 전송 실패 (코드: {response.status_code})")
                return False
    except Exception as e:
        print(f"[notifier] 슬랙 전송 중 예외 발생: {e}")
        return False


def process_log_background(log_data: dict):
    """백그라운드 스레드에서 AI 분석 수행 및 필요시 슬랙 알림 발송"""
    print(f"[server] 로그 수신 완료 및 AI 분석 시작: {log_data.get('event_type')} ({log_data.get('file_name')})")
    
    is_suspicious, reason = analyze_log_with_ai(log_data)
    
    if is_suspicious:
        print(f"[server] ⚠️ 해킹/유출 의심 감지! 보안 담당자 알림 전송 중... 사유: {reason}")
        notify_security_officer(reason, log_data)
    else:
        print("[server] ✅ 정상 로그로 판독됨.")


@app.post("/api/logs")
def receive_log(log: LogIn, background_tasks: BackgroundTasks):
    """에이전트가 로그를 전송하는 엔드포인트 (즉시 응답 후 백그라운드 처리)"""
    log_dict = log.model_dump()
    background_tasks.add_task(process_log_background, log_dict)
    return {"status": "received", "message": "로그가 접수되어 AI 분석이 진행됩니다."}


@app.get("/health")
def health_check():
    return {"status": "ok"}