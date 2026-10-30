"""backend가 생성한 디코이(허니팟) 파일을 주기적으로 받아 PC에 배치 (스텁).

현재: backend GET /api/decoys 목록을 폴링해, 아직 배치되지 않은 디코이를
      DECOY_DIR 에 플레이스홀더 파일로 생성.
TODO: backend에서 실제 파일 바이트/카나리 비콘이 임베드된 문서를 받아
      그대로 배치 (문서를 열면 backend /api/canary/{token_id} 가 호출되도록).
"""
import threading
from pathlib import Path

import httpx

from config import settings


class DecoyDeployer(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self._deployed: set[str] = set()
        self._client = httpx.Client(base_url=settings.backend_url, timeout=5.0)
        self._dir = Path(settings.decoy_dir)

    def run(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        print(f"[decoy_deployer] 디코이 배치 폴더: {self._dir.resolve()}")
        while not self._stop.is_set():
            self._sync_once()
            self._stop.wait(settings.decoy_poll_interval)

    def _sync_once(self) -> None:
        try:
            resp = self._client.get("/api/decoys")
            resp.raise_for_status()
            decoys = resp.json()
        except httpx.HTTPError as exc:
            print(f"[decoy_deployer] 목록 조회 실패: {exc}")
            return

        for d in decoys:
            if d["id"] in self._deployed:
                continue
            target = self._dir / d["file_name"]
            try:
                # TODO: 실제 카나리 비콘이 임베드된 파일로 교체
                target.write_text(
                    f"decoy placeholder (token={d['token_id']})\n", encoding="utf-8"
                )
                self._deployed.add(d["id"])
                print(f"[decoy_deployer] 배치: {target.name}")
            except OSError as exc:
                print(f"[decoy_deployer] 배치 실패 {target}: {exc}")

    def stop(self) -> None:
        self._stop.set()
