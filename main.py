"""DLP 에이전트 진입점.

사용법:
  python main.py            # 감시 시작 (Ctrl+C 로 종료)
  python main.py --selftest # backend 연결 점검용 합성 이벤트 1건 전송 후 종료
"""
import sys
import time

from config import settings
from decoy_deployer import DecoyDeployer
from sender import Sender
from watchers.email_watcher import EmailWatcher
from watchers.file_watcher import FileWatcher
from watchers.usb_watcher import UsbWatcher


def selftest() -> int:
    """backend 로 합성 기밀-유출 이벤트 1건을 보내 연결/파이프라인을 점검."""
    sender = Sender()
    event = {
        "host": settings.host_name,
        "user": "selftest",
        "event_type": "email_send",
        "file_name": "기밀_재무보고서.xlsx",
        "classification": "confidential",
        "channel": "selftest",
        "blocked": True,
        "detail": {"note": "agent selftest"},
    }
    ok = sender.send_now(event)
    print(f"[selftest] backend 전송 {'성공' if ok else '실패'} → {settings.backend_url}")
    return 0 if ok else 1


def main() -> int:
    print(f"[agent] host={settings.host_name} backend={settings.backend_url}")
    print(f"[agent] 감시 경로: {settings.watch_path_list}")

    sender = Sender()
    file_watcher = FileWatcher()
    usb_watcher = UsbWatcher(file_watcher)
    email_watcher = EmailWatcher()
    deployer = DecoyDeployer()

    sender.start()
    file_watcher.start()
    usb_watcher.start()
    email_watcher.start()
    deployer.start()

    print("[agent] 실행 중 (Ctrl+C 로 종료)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[agent] 종료 중...")
    finally:
        file_watcher.stop()
        usb_watcher.stop()
        email_watcher.stop()
        deployer.stop()
        sender.stop()
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
