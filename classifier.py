"""파일이 기밀/내부용인지 분류.

경로·파일명 키워드와 확장자 규칙 기반의 스캐폴드입니다.
TODO: 문서 내용 스캔(DLP 패턴: 주민번호/카드번호 등), 조직의 분류 태그 연동.
"""
import hashlib
import os
import time
from pathlib import Path

from config import settings


def classify(path: str) -> str | None:
    """'confidential' | 'internal' | None 반환."""
    p = Path(path)
    name = p.name.lower()
    full = str(p).lower()

    for kw in settings.keyword_list:
        if kw in name or kw in full:
            return "confidential"

    ext = p.suffix.lower().lstrip(".")
    if ext and ext in settings.extension_list:
        return "confidential"

    return None


def hash_file(
    path: str, max_bytes: int | None = None, retries: int = 3, delay: float = 0.5
) -> tuple[str | None, str | None]:
    """(소문자 hex SHA-256, 건너뛴 사유) 반환. 사유: 'too_large' | 'locked' | 'error'."""
    limit = settings.hash_max_bytes if max_bytes is None else max_bytes
    try:
        if os.path.getsize(path) > limit:
            return None, "too_large"
    except OSError:
        return None, "error"

    for attempt in range(retries):
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest(), None
        except PermissionError:
            # 다른 프로세스가 잠근 파일(복사 중 등) → 잠시 후 재시도
            if attempt < retries - 1:
                time.sleep(delay)
        except OSError:
            return None, "error"
    return None, "locked"


def file_hash(path: str) -> str | None:
    """기밀 파일 식별용 SHA-256. 실패 시 None."""
    return hash_file(path)[0]
