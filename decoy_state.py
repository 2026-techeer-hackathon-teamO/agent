"""디코이 배치 상태 공유 모듈.

- 시간 제한 억제: deployer가 쓰는 순간의 created/modified 이벤트를 file_watcher가 무시하도록.
- 알려진 디코이(sha256, size): 파일명이 기밀처럼 보이지 않아도 해시로 유출을 보고하도록.
- DecoyStateStore: 배치한 디코이 id 를 디스크에 기록 (재시작/사용자 삭제 후 재배치 방지).
"""
import json
import os
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_suppressed: dict[str, float] = {}
_known_hashes: set[str] = set()
_known_sizes: set[int] = set()


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def suppress(path: str, seconds: float = 10) -> None:
    with _lock:
        _suppressed[_norm(path)] = time.monotonic() + seconds


def is_suppressed(path: str) -> bool:
    key = _norm(path)
    with _lock:
        until = _suppressed.get(key)
        if until is None:
            return False
        if time.monotonic() >= until:
            del _suppressed[key]
            return False
        return True


def register_known(sha256: str, size: int) -> None:
    with _lock:
        _known_hashes.add(sha256.lower())
        _known_sizes.add(size)


def is_known_size(size: int) -> bool:
    with _lock:
        return size in _known_sizes


def is_known_hash(sha256: str | None) -> bool:
    if not sha256:
        return False
    with _lock:
        return sha256.lower() in _known_hashes


def reset() -> None:
    """테스트용 초기화."""
    with _lock:
        _suppressed.clear()
        _known_hashes.clear()
        _known_sizes.clear()


class DecoyStateStore:
    """배치한 디코이 기록: {"deployed": {id: {path, sha256, size}}}."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._deployed: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return dict(data.get("deployed", {}))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, AttributeError) as exc:
            print(f"[decoy_state] 상태 파일 읽기 실패, 빈 상태로 시작: {exc}")
            return {}

    def has(self, decoy_id: str) -> bool:
        with self._lock:
            return decoy_id in self._deployed

    def entries(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._deployed)

    def record(self, decoy_id: str, path: str, sha256: str, size: int) -> None:
        with self._lock:
            self._deployed[decoy_id] = {"path": path, "sha256": sha256, "size": size}
            self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(
            json.dumps({"deployed": self._deployed}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)
