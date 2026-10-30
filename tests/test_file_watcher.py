import hashlib

import pytest

import decoy_state
import event_bus
from watchers import file_watcher


@pytest.fixture
def events():
    while not event_bus.bus.empty():
        event_bus.bus.get_nowait()
    out = []
    yield out


def drain(out):
    while not event_bus.bus.empty():
        out.append(event_bus.bus.get_nowait())
    return out


def test_suppressed_path_is_ignored(tmp_path, events):
    p = tmp_path / "기밀.txt"
    p.write_bytes(b"x")
    decoy_state.suppress(str(p))
    file_watcher._Handler()._handle(str(p))
    assert drain(events) == []


def test_known_decoy_reported_without_keyword(tmp_path, events):
    data = b"decoy body"
    sha = hashlib.sha256(data).hexdigest()
    decoy_state.register_known(sha, len(data))
    p = tmp_path / "plain_name.txt"
    p.write_bytes(data)

    file_watcher._Handler()._handle(str(p))
    [ev] = drain(events)
    assert ev["event_type"] == "file_access"
    assert ev["file_hash"] == sha


def test_plain_file_ignored(tmp_path, events):
    p = tmp_path / "plain.txt"
    p.write_bytes(b"hello")
    file_watcher._Handler()._handle(str(p))
    assert drain(events) == []


def test_confidential_file_includes_hash(tmp_path, events):
    p = tmp_path / "기밀_보고서.txt"
    p.write_bytes(b"secret")
    file_watcher._Handler()._handle(str(p))
    [ev] = drain(events)
    assert ev["file_hash"] == hashlib.sha256(b"secret").hexdigest()
    assert ev["classification"] == "confidential"


def test_debounces_repeated_events(tmp_path, events):
    p = tmp_path / "기밀.txt"
    p.write_bytes(b"x")
    now = [100.0]
    h = file_watcher._Handler(clock=lambda: now[0])
    h._handle(str(p))
    h._handle(str(p))
    assert len(drain([])) == 1
    now[0] += 5
    h._handle(str(p))
    assert len(drain([])) == 1


def test_too_large_file_reports_hash_skipped(tmp_path, events, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "hash_max_bytes", 3)
    p = tmp_path / "기밀.bin"
    p.write_bytes(b"0123456789")
    file_watcher._Handler()._handle(str(p))
    [ev] = drain(events)
    assert ev["file_hash"] is None
    assert ev["detail"]["hash_skipped"] == "too_large"
