import os
import socket
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    backend_url: str = "http://localhost:8000"
    host: str = ""
    watch_paths: str = ""
    confidential_keywords: str = "기밀,대외비,confidential,secret"
    confidential_extensions: str = ""
    # backend X-Agent-Key (backend .env 와 같은 값). 비어 있으면 디코이 배치 비활성
    agent_api_key: str = ""
    # 비어 있으면 대화형 사용자의 Downloads 폴더
    decoy_dir: str = ""
    decoy_poll_interval: int = 60
    # 비어 있으면 Windows: %ProgramData%\dlp-agent\decoy_state.json, 그 외: ./decoy_state.json
    decoy_state_file: str = ""
    # 이보다 큰 파일은 해시를 건너뛰고 detail.hash_skipped="too_large"
    hash_max_bytes: int = 500 * 1024 * 1024
    # 같은 경로의 연속 이벤트(on_modified 다발)를 묶는 시간(초)
    event_debounce_seconds: float = 2.0

    @property
    def host_name(self) -> str:
        return self.host or socket.gethostname()

    @property
    def watch_path_list(self) -> list[str]:
        if self.watch_paths.strip():
            return [p.strip() for p in self.watch_paths.split(",") if p.strip()]
        from user_session import profile_dir

        profile = profile_dir()
        return [str(profile)] if profile else []

    @property
    def decoy_state_path(self) -> Path:
        if self.decoy_state_file.strip():
            return Path(self.decoy_state_file)
        if sys.platform == "win32" and os.environ.get("ProgramData"):
            return Path(os.environ["ProgramData"]) / "dlp-agent" / "decoy_state.json"
        return Path("decoy_state.json")

    @property
    def keyword_list(self) -> list[str]:
        return [k.strip().lower() for k in self.confidential_keywords.split(",") if k.strip()]

    @property
    def extension_list(self) -> list[str]:
        return [
            e.strip().lower().lstrip(".")
            for e in self.confidential_extensions.split(",")
            if e.strip()
        ]


settings = Settings()
