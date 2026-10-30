import socket
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    backend_url: str = "http://localhost:8000"
    host: str = ""
    watch_paths: str = ""
    confidential_keywords: str = "기밀,대외비,confidential,secret"
    confidential_extensions: str = ""
    decoy_dir: str = "./decoys"
    decoy_poll_interval: int = 60

    @property
    def host_name(self) -> str:
        return self.host or socket.gethostname()

    @property
    def watch_path_list(self) -> list[str]:
        if self.watch_paths.strip():
            return [p.strip() for p in self.watch_paths.split(",") if p.strip()]
        return [str(Path.home())]

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
