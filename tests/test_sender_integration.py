"""Real loopback HTTP delivery, including retry after a temporary server failure."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import settings
from event_bus import bus
from sender import Sender


def test_loopback_delivery_retries_and_preserves_event(monkeypatch):
    received = []
    delivered = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append((self.path, self.headers.get("X-Agent-Key"), payload))
            status = 503 if len(received) == 1 else 201
            self.send_response(status)
            self.end_headers()
            if status == 201:
                delivered.set()

        def log_message(self, *args):
            pass

    while not bus.empty():
        bus.get_nowait()
        bus.task_done()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(settings, "backend_url", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(settings, "agent_api_key", "integration-test-key")
    sender = Sender()
    event = {
        "host": "test-host", "user": "test-user", "event_type": "usb_copy",
        "channel": "usb:policy", "classification": None, "blocked": False,
        "detail": {"action": "usb_write_policy", "status": "configured"},
    }
    try:
        sender.start()
        bus.put(event)
        assert delivered.wait(8), "event did not reach loopback server after retry"
    finally:
        sender.stop()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not sender.is_alive()
    assert received == [("/api/logs", "integration-test-key", event)] * 2
    assert bus.empty()
