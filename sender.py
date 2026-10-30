"""event_bus 의 이벤트를 backend /api/logs 로 전송하는 백그라운드 스레드."""
import threading

import httpx

from config import settings
from event_bus import bus


class Sender(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self._client = httpx.Client(base_url=settings.backend_url, timeout=5.0)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                event = bus.get(timeout=0.5)
            except Exception:
                continue
            self._post(event)

    def _post(self, event: dict) -> None:
        try:
            resp = self._client.post("/api/logs", json=event)
            status = "ok" if resp.status_code // 100 == 2 else f"err {resp.status_code}"
        except httpx.HTTPError as exc:
            status = f"전송 실패: {exc}"
        print(f"[sender] {event.get('event_type')} {event.get('file_name')} → {status}")

    def send_now(self, event: dict) -> bool:
        """셀프테스트용 동기 전송."""
        try:
            resp = self._client.post("/api/logs", json=event)
            return resp.status_code // 100 == 2
        except httpx.HTTPError as exc:
            print(f"[sender] 전송 실패: {exc}")
            return False

    def stop(self) -> None:
        self._stop.set()
