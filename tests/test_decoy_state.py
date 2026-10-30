import json

import decoy_state


def test_suppress_expires(monkeypatch, tmp_path):
    now = [1000.0]
    monkeypatch.setattr(decoy_state.time, "monotonic", lambda: now[0])
    p = tmp_path / "a.txt"

    decoy_state.suppress(str(p), seconds=10)
    assert decoy_state.is_suppressed(str(p))

    now[0] += 11
    assert not decoy_state.is_suppressed(str(p))


def test_suppress_normalizes_path(tmp_path):
    p = tmp_path / "a.txt"
    decoy_state.suppress(str(p))
    assert decoy_state.is_suppressed(str(tmp_path / "." / "a.txt"))


def test_known_decoys_by_size_and_hash():
    decoy_state.register_known("ab" * 32, 17)
    assert decoy_state.is_known_size(17)
    assert not decoy_state.is_known_size(18)
    assert decoy_state.is_known_hash("ab" * 32)
    assert not decoy_state.is_known_hash("cd" * 32)


def test_store_persists_entries(tmp_path):
    f = tmp_path / "state.json"
    store = decoy_state.DecoyStateStore(f)
    store.record("id1", "/x/a.txt", "ab" * 32, 17)

    reloaded = decoy_state.DecoyStateStore(f)
    assert reloaded.has("id1")
    assert reloaded.entries()["id1"]["sha256"] == "ab" * 32
    assert json.loads(f.read_text(encoding="utf-8"))["deployed"]["id1"]["path"] == "/x/a.txt"


def test_store_tolerates_corrupt_file(tmp_path):
    f = tmp_path / "state.json"
    f.write_text("{not json", encoding="utf-8")
    store = decoy_state.DecoyStateStore(f)
    assert store.entries() == {}
