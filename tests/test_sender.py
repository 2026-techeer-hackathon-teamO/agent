import httpx

from sender import Sender
from config import settings


def test_server_receives_authenticated_event(monkeypatch):
    monkeypatch.setattr(settings, "agent_api_key", "test-key")
    sender = Sender()
    sender._client.close()
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(201)

    sender._client = httpx.Client(
        base_url="https://backend.test", headers={"X-Agent-Key": settings.agent_api_key},
        transport=httpx.MockTransport(handle),
    )
    try:
        assert sender._post({"event_type": "usb_copy", "blocked": False})
        assert requests[0].url.path == "/api/logs"
        assert requests[0].headers["X-Agent-Key"] == "test-key"
    finally:
        sender.stop()


def test_failed_delivery_is_not_success():
    sender = Sender()
    sender._client.close()
    sender._client = httpx.Client(
        base_url="https://backend.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )
    try:
        assert not sender._post({"event_type": "usb_copy"})
    finally:
        sender.stop()
