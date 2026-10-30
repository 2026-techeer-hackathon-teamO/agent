"""watchdog 기반 파일 감시.

감시 경로에서 기밀 파일의 생성/수정/이동(복사)을 포착해 event_bus로 발행.
이동식 드라이브로의 복사는 usb_copy, 그 외는 file_access 로 분류.
알려진 디코이(해시 일치)는 파일명 분류와 무관하게 보고한다.
"""
import os
import threading
import time
from collections.abc import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import classifier
import decoy_state
from config import settings
from event_bus import publish
from user_session import interactive_user
from watchers.drive import is_removable, removable_drives


class _Handler(FileSystemEventHandler):
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__()
        self._clock = clock
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def _debounced(self, path: str) -> bool:
        now = self._clock()
        with self._lock:
            last = self._last_seen.get(path)
            if last is not None and now - last < settings.event_debounce_seconds:
                return True
            self._last_seen[path] = now
            if len(self._last_seen) > 10000:  # 오래된 항목 정리
                cutoff = now - settings.event_debounce_seconds
                self._last_seen = {p: t for p, t in self._last_seen.items() if t >= cutoff}
            return False

    def _handle(self, path: str) -> None:
        if not path or decoy_state.is_suppressed(path):
            return  # 비었거나 deployer 자신의 배치 이벤트
        if self._debounced(path):
            return

        classification = classifier.classify(path)
        digest, hash_skipped = None, None
        is_decoy = False
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        if size is not None and decoy_state.is_known_size(size):
            digest, hash_skipped = classifier.hash_file(path)
            is_decoy = decoy_state.is_known_hash(digest)

        if classification is None and not is_decoy:
            return  # 기밀도 디코이도 아님 → 무시
        if digest is None and hash_skipped is None:
            digest, hash_skipped = classifier.hash_file(path)

        on_usb = is_removable(path)
        event = {
            "host": settings.host_name,
            "user": interactive_user(),
            "event_type": "usb_copy" if on_usb else "file_access",
            "file_name": path,
            "file_hash": digest,
            "classification": classification,
            "channel": f"usb:{path[:2]}" if on_usb else "filesystem",
            "blocked": False,  # 차단 정책 연동 시 True 로 (TODO)
            "detail": {"hash_skipped": hash_skipped} if hash_skipped else {},
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


class FileWatcher:
    def __init__(self) -> None:
        self._observer = Observer()
        self._handler = _Handler()
        self._watched: set[str] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        for path in settings.watch_path_list:
            self.add_path(path)
        # 이미 꽂혀 있는 USB 도 감시 (usb_copy 는 드라이브 경로를 감시해야 탐지됨)
        for drive in removable_drives():
            self.add_path(drive)
        self._observer.start()
        print(f"[file_watcher] 감시 시작: {sorted(self._watched)}")

    def add_path(self, path: str) -> None:
        """감시 경로 추가 (USB 연결 시 usb_watcher 가 호출)."""
        with self._lock:
            if path in self._watched:
                return
            try:
                self._observer.schedule(self._handler, path, recursive=True)
                self._watched.add(path)
            except (FileNotFoundError, OSError) as exc:
                print(f"[file_watcher] 감시 불가 {path}: {exc}")

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=3)
