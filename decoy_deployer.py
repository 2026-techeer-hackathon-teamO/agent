"""backend가 보관한 디코이(허니팟) 파일을 받아 사용자 Downloads 에 조용히 배치.

GET /api/agent/decoys → GET /api/agent/decoys/{id}/file (X-Agent-Key) 로 원본 바이트를 받아
sha256 검증 후 그대로 저장한다. 내용/인코딩/메타데이터를 건드리면 해시와 카나리 비콘이 깨진다.
Mark-of-the-Web(Zone.Identifier)은 붙이지 않는다 (보호된 보기에서 비콘이 막힘).
"""
import hashlib
import os
import random
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx

import decoy_state
import user_session
from config import settings

# 배치 직후 file_watcher 가 받는 created/modified 이벤트를 무시할 시간(초)
SUPPRESS_SECONDS = 10


class DecoyDeployer(threading.Thread):
    def __init__(
        self,
        client: httpx.Client | None = None,
        target_dir_fn: Callable[[], Path | None] | None = None,
        state: decoy_state.DecoyStateStore | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self.enabled = client is not None or bool(settings.agent_api_key)
        self._client = client or httpx.Client(
            base_url=settings.backend_url,
            timeout=10.0,
            headers={"X-Agent-Key": settings.agent_api_key},
            transport=transport,
        )
        self._target_dir_fn = target_dir_fn or _default_target_dir
        self.state = state or decoy_state.DecoyStateStore(settings.decoy_state_path)
        # 이미 배치한 디코이도 유출 탐지 대상이므로 재시작 시 해시를 복원
        for entry in self.state.entries().values():
            decoy_state.register_known(entry["sha256"], entry["size"])

    def run(self) -> None:
        if not self.enabled:
            print("[decoy_deployer] AGENT_API_KEY 미설정 → 디코이 배치 비활성")
            return
        while not self._stop_event.is_set():
            self.sync_once()
            self._stop_event.wait(settings.decoy_poll_interval)

    def sync_once(self) -> None:
        target_dir = self._target_dir_fn()
        if target_dir is None or not target_dir.is_dir():
            print("[decoy_deployer] 배치 폴더를 찾을 수 없음(로그인 사용자 없음?) → 다음 주기에 재시도")
            return

        try:
            resp = self._client.get("/api/agent/decoys")
            resp.raise_for_status()
            decoys = resp.json()
        except httpx.HTTPStatusError as exc:
            print(f"[decoy_deployer] 목록 조회 거부 {exc.response.status_code} → 다음 주기에 재시도")
            return
        except (httpx.HTTPError, ValueError) as exc:
            print(f"[decoy_deployer] 목록 조회 실패: {exc}")
            return

        for d in decoys:
            # 상태에 있으면 파일이 지워졌어도 다시 만들지 않음 (사용자 삭제 존중)
            if self.state.has(d["id"]):
                continue
            self._deploy(d, target_dir)

    def _deploy(self, d: dict, target_dir: Path) -> None:
        name = Path(d["file_name"].replace("\\", "/")).name  # 디렉터리 이탈 방지
        if not name or name in (".", ".."):
            print(f"[decoy_deployer] 잘못된 파일명, 건너뜀: {d['id']}")
            return
        target = target_dir / name
        if target.exists():
            print(f"[decoy_deployer] 같은 이름 파일 존재 → 덮어쓰지 않음: {name}")
            return

        try:
            resp = self._client.get(f"/api/agent/decoys/{d['id']}/file")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"[decoy_deployer] 파일 다운로드 실패 {d['id']}: {exc}")
            return

        content = resp.content
        actual = hashlib.sha256(content).hexdigest()
        expected = d["sha256"].lower()
        header = resp.headers.get("X-Decoy-SHA256", "").lower()
        if actual != expected or header != expected:
            print(f"[decoy_deployer] sha256 불일치, 폐기: {d['id']}")
            return

        decoy_state.register_known(expected, len(content))
        tmp = target_dir / f".{name}.{os.getpid()}.tmp"
        decoy_state.suppress(str(tmp), SUPPRESS_SECONDS)
        decoy_state.suppress(str(target), SUPPRESS_SECONDS)
        try:
            with open(tmp, "wb") as f:
                f.write(content)
            if target.exists():  # 다운로드 중 사용자가 같은 이름을 만든 경우
                tmp.unlink()
                print(f"[decoy_deployer] 같은 이름 파일 존재 → 덮어쓰지 않음: {name}")
                return
            os.replace(tmp, target)
            _backdate(target)
        except OSError as exc:
            print(f"[decoy_deployer] 배치 실패 {target}: {exc}")
            tmp.unlink(missing_ok=True)
            return

        self.state.record(d["id"], str(target), expected, len(content))
        print(f"[decoy_deployer] 배치: {name}")

    def stop(self) -> None:
        self._stop_event.set()


def _default_target_dir() -> Path | None:
    if settings.decoy_dir.strip():
        return Path(settings.decoy_dir)
    return user_session.downloads_dir()


def _backdate(path: Path) -> None:
    """수정/접근/생성 시각을 2~7일 전 임의 시각으로."""
    t = time.time() - random.uniform(2 * 86400, 7 * 86400)
    os.utime(path, (t, t))
    try:
        user_session.set_creation_time(str(path), t)
    except OSError as exc:
        print(f"[decoy_deployer] 생성 시각 설정 실패 {path.name}: {exc}")
