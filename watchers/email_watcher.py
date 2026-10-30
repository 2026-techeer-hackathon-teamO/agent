"""Outlook 발신 메일의 기밀 첨부 차단.

Outlook COM 의 Application.ItemSend 이벤트를 받아 첨부를 email_policy 로 검사하고,
기밀/디코이 첨부가 있으면 발송을 취소(Cancel=True)한 뒤 email_send(blocked=True) 를
첨부마다 1건씩 event_bus 로 발행한다 (→ sender → backend /api/logs → AI 판단 → 담당자 알림).

- Windows + pywin32 + Outlook 데스크톱에서만 활성. 그 외에는 비활성 로그만 남김.
- Outlook 은 사용자 세션에서 돌기 때문에 agent 도 로그인 사용자 세션에서 실행되어야 함
  (SYSTEM 서비스에서는 사용자의 Outlook 에 붙을 수 없음).
- Outlook 이 꺼져 있으면 새로 띄우지 않고, 켜질 때까지 주기적으로 다시 붙는다.
- 검사 중 예외가 나면 업무 메일을 막지 않도록 발송을 허용(fail-open)하고 로그만 남긴다.
"""
import sys
import tempfile
import threading

from event_bus import publish
from watchers import email_policy

# Outlook 이 꺼질 때 OnQuit 이 설정 → 다시 붙기 시도
_outlook_quit = threading.Event()
RETRY_SECONDS = 10


class _OutlookEvents:
    """win32com DispatchWithEvents 핸들러."""

    def OnItemSend(self, item, cancel):
        # Cancel 은 ByRef 인자라 pywin32 에서는 반환값이 Cancel 의 새 값이 된다
        try:
            with tempfile.TemporaryDirectory(prefix="dlp-mail-") as tmp:
                verdict = email_policy.inspect_mail(item, tmp)
        except Exception as exc:  # noqa: BLE001
            print(f"[email_watcher] 메일 검사 실패, 발송 허용: {exc}")
            return cancel

        for event in verdict.events:
            publish(event)
        if verdict.block:
            names = ", ".join(e["file_name"] for e in verdict.events)
            print(f"[email_watcher] 기밀 첨부 메일 발송 차단: {names}")
            _warn_user(names)
            return True
        return cancel

    def OnQuit(self):
        _outlook_quit.set()


def _warn_user(names: str) -> None:
    """발신자에게 차단 사유 안내 (메시지 루프를 막지 않도록 별도 스레드)."""

    def show() -> None:
        import ctypes

        MB_ICONWARNING, MB_TOPMOST, MB_SETFOREGROUND = 0x30, 0x40000, 0x10000
        ctypes.windll.user32.MessageBoxW(
            None,
            f"기밀 파일이 첨부되어 메일 발송이 차단되었습니다.\n\n{names}\n\n"
            "회사 보안 정책에 따라 이 시도는 보안 담당자에게 보고됩니다.",
            "보안 정책 - 메일 발송 차단",
            MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND,
        )

    threading.Thread(target=show, daemon=True).start()


class EmailWatcher(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()

    def run(self) -> None:
        if sys.platform != "win32":
            print("[email_watcher] 비활성 (Windows 아님)")
            return
        try:
            import pythoncom
            import pywintypes
            import win32com.client
        except ImportError:
            print("[email_watcher] 비활성 (pywin32 미설치)")
            return

        pythoncom.CoInitialize()
        try:
            while not self._stop_event.is_set():
                try:
                    # 실행 중인 Outlook 에만 붙음 (없으면 com_error → 대기 후 재시도)
                    win32com.client.GetActiveObject("Outlook.Application")
                    outlook = win32com.client.DispatchWithEvents(
                        "Outlook.Application", _OutlookEvents
                    )
                except pywintypes.com_error:
                    self._stop_event.wait(RETRY_SECONDS)
                    continue

                _outlook_quit.clear()
                print("[email_watcher] Outlook 발신 메일 감시 시작")
                # COM 이벤트는 이 스레드의 메시지 펌프로 전달됨
                while not self._stop_event.is_set() and not _outlook_quit.is_set():
                    pythoncom.PumpWaitingMessages()
                    self._stop_event.wait(0.1)
                del outlook
                if _outlook_quit.is_set():
                    print("[email_watcher] Outlook 종료 감지, 재연결 대기")
        finally:
            pythoncom.CoUninitialize()

    def stop(self) -> None:
        self._stop_event.set()
