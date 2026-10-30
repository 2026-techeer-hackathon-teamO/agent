"""watchdog 기반 파일 감시.

감시 경로에서 기밀 파일의 생성/수정/이동(복사)을 포착해 event_bus로 발행.
이동식 드라이브로의 복사는 usb_copy, 그 외는 file_access 로 분류.
"""
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import classifier
from config import settings
from event_bus import publish
from watchers.drive import is_removable


class _Handler(FileSystemEventHandler):
    def _handle(self, path: str) -> None:
        if not path:
            return
        classification = classifier.classify(path)
        if classification is None:
            return  # 기밀 아님 → 무시

        on_usb = is_removable(path)
        event = {
            "host": settings.host_name,
            "user": _current_user(),
            "event_type": "usb_copy" if on_usb else "file_access",
            "file_name": path,
            "file_hash": classifier.file_hash(path),
            "classification": classification,
            "channel": f"usb:{path[:2]}" if on_usb else "filesystem",
            "blocked": False,  # 차단 정책 연동 시 True 로 (TODO)
            "detail": {},
        }
        publish(event)

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._handle(event.src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event) -> None:
        if not event.is_directory:
            self._handle(getattr(event, "dest_path", "") or event.src_path)


def _current_user() -> str:
    import getpass

    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


class FileWatcher:
    def __init__(self) -> None:
        self._observer = Observer()

    def start(self) -> None:
        handler = _Handler()
        started = []
        for path in settings.watch_path_list:
            try:
                self._observer.schedule(handler, path, recursive=True)
                started.append(path)
            except (FileNotFoundError, OSError) as exc:
                print(f"[file_watcher] 감시 불가 {path}: {exc}")
        self._observer.start()
        print(f"[file_watcher] 감시 시작: {started}")

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=3)
