"""event_bus 의 이벤트를 backend /api/logs 로 전송하는 백그라운드 스레드."""
import threading
import queue

import httpx

from config import settings
from event_bus import bus


class Sender(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        headers = {"X-Agent-Key": settings.agent_api_key} if settings.agent_api_key else {}
        self._client = httpx.Client(base_url=settings.backend_url, timeout=5.0, headers=headers)

    def run(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    event = bus.get(timeout=0.5)
                except queue.Empty:
                    continue
                delay = 1
                while not self._post(event):
                    if self._stop_event.wait(delay):
                        bus.put(event)
                        bus.task_done()
                        return
                    delay = min(delay * 2, 30)
                bus.task_done()
        finally:
            self._client.close()

    def _post(self, event: dict) -> bool:
        try:
            resp = self._client.post("/api/logs", json=event)
            status = "ok" if resp.status_code // 100 == 2 else f"err {resp.status_code}"
            ok = resp.status_code // 100 == 2
        except httpx.HTTPError as exc:
            status = f"전송 실패: {exc}"
            ok = False
        print(f"[sender] {event.get('event_type')} {event.get('file_name')} → {status}")
        return ok

    def send_now(self, event: dict) -> bool:
        """셀프테스트용 동기 전송."""
        try:
            resp = self._client.post("/api/logs", json=event)
            return resp.status_code // 100 == 2
        except httpx.HTTPError as exc:
            print(f"[sender] 전송 실패: {exc}")
            return False

    def stop(self) -> None:
        self._stop_event.set()
        if self.is_alive():
            self.join(timeout=6)
        elif self.ident is None:
            self._client.close()
