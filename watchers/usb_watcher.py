"""이동식 저장소(USB) 연결 감지. Windows WMI 기반.

Windows가 아니거나 WMI 미설치 시 자동 비활성(아무 것도 하지 않음).
실제 복사 차단/탐지는 file_watcher가 이동식 드라이브 경로를 감시하며 처리.
"""
import sys
import threading

from config import settings
from event_bus import publish


class UsbWatcher(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self._available = sys.platform == "win32"

    def run(self) -> None:
        if not self._available:
            print("[usb_watcher] 비활성 (Windows 아님)")
            return
        try:
            import pythoncom  # pywin32
            import wmi
        except ImportError:
            print("[usb_watcher] 비활성 (pywin32/WMI 미설치)")
            return

        pythoncom.CoInitialize()
        c = wmi.WMI()
        # 이동식 디스크(DriveType=2) 연결 이벤트 감시
        watcher = c.Win32_VolumeChangeEvent.watch_for(EventType=2)
        print("[usb_watcher] USB 연결 감시 시작")
        while not self._stop.is_set():
            try:
                evt = watcher(timeout_ms=1000)
            except wmi.x_wmi_timed_out:
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"[usb_watcher] 오류: {exc}")
                continue
            publish({
                "host": settings.host_name,
                "user": "",
                "event_type": "usb_copy",
                "channel": f"usb:{getattr(evt, 'DriveName', '?')}",
                "classification": None,
                "blocked": False,
                "detail": {"note": "이동식 저장소 연결 감지"},
            })

    def stop(self) -> None:
        self._stop.set()
