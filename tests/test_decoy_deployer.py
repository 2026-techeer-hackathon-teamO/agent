import hashlib
import os
import time

import httpx
import pytest

import decoy_state
from decoy_deployer import DecoyDeployer

CONTENT = "가짜 기밀\r\n".encode("utf-8") + bytes(range(256))  # 원본 바이트 보존 확인용
SHA = hashlib.sha256(CONTENT).hexdigest()
DECOY = {
    "id": "d1",
    "token_id": "t1",
    "file_name": "2026_인사평가_기밀.txt",
    "sha256": SHA,
    "size": len(CONTENT),
}


def make_client(decoys, files, seen=None, list_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        path = request.url.path
        if path == "/api/agent/decoys":
            if list_status != 200:
                return httpx.Response(list_status, json={"detail": "invalid agent key"})
            return httpx.Response(200, json=decoys)
        for d in decoys:
            if path == f"/api/agent/decoys/{d['id']}/file":
                body, header_sha = files[d["id"]]
                return httpx.Response(200, content=body, headers={"X-Decoy-SHA256": header_sha})
        return httpx.Response(404, json={"detail": "decoy not found"})

    return httpx.Client(base_url="http://backend", transport=httpx.MockTransport(handler))


@pytest.fixture
def downloads(tmp_path):
    d = tmp_path / "Downloads"
    d.mkdir()
    return d


def deployer(downloads, tmp_path, client):
    return DecoyDeployer(
        client=client,
        target_dir_fn=lambda: downloads,
        state=decoy_state.DecoyStateStore(tmp_path / "state.json"),
    )


def test_deploys_original_bytes(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (CONTENT, SHA)}))
    dep.sync_once()
    target = downloads / DECOY["file_name"]
    assert target.read_bytes() == CONTENT
    assert not list(downloads.glob("*.tmp*"))  # 임시 파일 정리


def test_sends_agent_key_header(downloads, tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "agent_api_key", "k3y")
    seen = []
    client = make_client([DECOY], {"d1": (CONTENT, SHA)}, seen)
    dep = DecoyDeployer(
        client=None,
        target_dir_fn=lambda: downloads,
        state=decoy_state.DecoyStateStore(tmp_path / "state.json"),
        transport=client._transport,
    )
    dep.sync_once()
    assert seen and all(r.headers["X-Agent-Key"] == "k3y" for r in seen)


def test_disabled_without_agent_key(downloads, tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "agent_api_key", "")
    dep = DecoyDeployer(target_dir_fn=lambda: downloads,
                        state=decoy_state.DecoyStateStore(tmp_path / "state.json"))
    assert not dep.enabled


def test_rejects_hash_mismatch(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (b"tampered", SHA)}))
    dep.sync_once()
    assert not (downloads / DECOY["file_name"]).exists()
    assert not dep.state.has("d1")


def test_rejects_header_mismatch(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (CONTENT, "0" * 64)}))
    dep.sync_once()
    assert not (downloads / DECOY["file_name"]).exists()


def test_does_not_overwrite_user_file(downloads, tmp_path):
    user_file = downloads / DECOY["file_name"]
    user_file.write_bytes(b"user data")
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (CONTENT, SHA)}))
    dep.sync_once()
    assert user_file.read_bytes() == b"user data"


def test_strips_path_components(downloads, tmp_path):
    evil = dict(DECOY, file_name="../../evil.txt")
    dep = deployer(downloads, tmp_path, make_client([evil], {"d1": (CONTENT, SHA)}))
    dep.sync_once()
    assert (downloads / "evil.txt").read_bytes() == CONTENT
    assert not (tmp_path / "evil.txt").exists()


def test_does_not_redeploy_deleted_decoy(downloads, tmp_path):
    client = make_client([DECOY], {"d1": (CONTENT, SHA)})
    deployer(downloads, tmp_path, client).sync_once()
    (downloads / DECOY["file_name"]).unlink()

    deployer(downloads, tmp_path, client).sync_once()  # 재시작 시뮬레이션
    assert not (downloads / DECOY["file_name"]).exists()


def test_backdates_timestamps(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (CONTENT, SHA)}))
    dep.sync_once()
    age = time.time() - os.stat(downloads / DECOY["file_name"]).st_mtime
    assert 2 * 86400 <= age <= 7 * 86400 + 60


def test_suppresses_watcher_and_registers_known(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (CONTENT, SHA)}))
    dep.sync_once()
    assert decoy_state.is_suppressed(str(downloads / DECOY["file_name"]))
    assert decoy_state.is_known_hash(SHA)
    assert decoy_state.is_known_size(len(CONTENT))


def test_known_hashes_loaded_from_state_on_start(downloads, tmp_path):
    store = decoy_state.DecoyStateStore(tmp_path / "state.json")
    store.record("d1", str(downloads / "x"), SHA, len(CONTENT))
    DecoyDeployer(client=make_client([], {}), target_dir_fn=lambda: downloads, state=store)
    assert decoy_state.is_known_hash(SHA)


def test_auth_error_is_retried_next_cycle(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([DECOY], {"d1": (CONTENT, SHA)}, list_status=401))
    dep.sync_once()  # 예외 없이 로그만
    assert not (downloads / DECOY["file_name"]).exists()


def test_skips_cycle_when_downloads_unresolved(tmp_path):
    dep = DecoyDeployer(
        client=make_client([DECOY], {"d1": (CONTENT, SHA)}),
        target_dir_fn=lambda: None,
        state=decoy_state.DecoyStateStore(tmp_path / "state.json"),
    )
    dep.sync_once()
    assert not dep.state.has("d1")


def test_stop_then_join_does_not_raise(downloads, tmp_path):
    dep = deployer(downloads, tmp_path, make_client([], {}))
    dep.start()
    dep.stop()
    dep.join(timeout=2)
    assert not dep.is_alive()
