"""워처 → 전송기 사이의 스레드 안전 큐."""
import queue

# LogIn 형태의 dict 를 주고받는다 (backend/app/models.py:LogIn 참고).
bus: "queue.Queue[dict]" = queue.Queue()


def publish(event: dict) -> None:
    bus.put(event)
