"""메일 첨부를 통한 기밀 유출 감시 (스텁).

설계: 기밀 파일이 메일 첨부로 나가는 것을 탐지하고, 정책에 따라 차단한다.
구현 후보:
  - Outlook COM(win32com) 으로 발신 메일의 첨부를 검사 (ItemSend 이벤트 후킹)
  - 로컬 SMTP 프록시로 아웃바운드 메일 가로채기

현재는 플랫폼 가드만: Windows+pywin32 환경에서만 활성화되며,
실제 Outlook 후킹 로직은 TODO 로 비워둔다.
"""
import sys
import threading


class EmailWatcher(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()

    def run(self) -> None:
        if sys.platform != "win32":
            print("[email_watcher] 비활성 (Windows 아님)")
            return
        try:
            import win32com.client  # noqa: F401  (pywin32)
        except ImportError:
            print("[email_watcher] 비활성 (pywin32 미설치)")
            return

        print("[email_watcher] (스텁) Outlook 메일 감시 자리 — ItemSend 후킹 TODO")
        # TODO: Outlook Application 의 ItemSend 이벤트를 받아 첨부를 classifier 로 검사,
        #       기밀이면 event_bus 로 email_send(blocked=True) 발행 + 발송 취소.
        #       첨부 파일마다 이벤트 1건, 각각 file_hash=classifier.hash_file(첨부 임시경로)[0]
        #       포함 (디코이 해시 매칭은 backend 가 수행).
        self._stop_event.wait()

    def stop(self) -> None:
        self._stop_event.set()
