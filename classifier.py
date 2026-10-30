"""파일이 기밀/내부용인지 분류.

경로·파일명 키워드와 확장자 규칙 기반의 스캐폴드입니다.
TODO: 문서 내용 스캔(DLP 패턴: 주민번호/카드번호 등), 조직의 분류 태그 연동.
"""
import hashlib
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


def file_hash(path: str) -> str | None:
    """기밀 파일 식별용 SHA-256. 실패 시 None."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None
