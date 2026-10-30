import hashlib

import classifier


def test_hash_file_returns_lowercase_sha256(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello")
    digest, skipped = classifier.hash_file(str(p))
    assert digest == hashlib.sha256(b"hello").hexdigest()
    assert skipped is None


def test_hash_file_skips_too_large(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(b"x" * 100)
    digest, skipped = classifier.hash_file(str(p), max_bytes=10)
    assert digest is None
    assert skipped == "too_large"


def test_hash_file_retries_locked_file(monkeypatch, tmp_path):
    p = tmp_path / "locked.bin"
    p.write_bytes(b"data")
    real_open = open
    calls = {"n": 0}

    def flaky_open(path, mode="r", *a, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("in use")
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr("builtins.open", flaky_open)
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    digest, skipped = classifier.hash_file(str(p))
    assert digest == hashlib.sha256(b"data").hexdigest()
    assert calls["n"] == 3


def test_hash_file_gives_up_after_retries(monkeypatch, tmp_path):
    p = tmp_path / "locked.bin"
    p.write_bytes(b"data")

    def always_locked(*a, **kw):
        raise PermissionError("in use")

    monkeypatch.setattr("builtins.open", always_locked)
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    digest, skipped = classifier.hash_file(str(p))
    assert digest is None
    assert skipped == "locked"
