"""발신 메일 첨부 검사 정책 (플랫폼 무관, Outlook MailItem 과 같은 모양의 객체를 받음).

첨부마다 임시 폴더에 저장해 SHA-256 을 계산하고,
파일명/확장자가 기밀이거나 알려진 디코이 해시면 email_send 이벤트를 만든다.
EMAIL_BLOCK 이 켜져 있으면 발송 차단(block=True)을 지시한다.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import classifier
import decoy_state
from config import settings
from user_session import interactive_user

CHANNEL = "email:outlook"


@dataclass
class MailVerdict:
    block: bool = False
    events: list[dict] = field(default_factory=list)


def inspect_mail(mail, tmp_dir: str) -> MailVerdict:
    verdict = MailVerdict()
    subject = _safe_get(mail, "Subject")
    to = _safe_get(mail, "To")
    attachments = mail.Attachments

    for i in range(1, attachments.Count + 1):
        att = attachments.Item(i)
        name = str(att.FileName or f"attachment_{i}")
        digest, skipped = _hash_attachment(att, name, i, tmp_dir)

        classification = classifier.classify(name)
        is_decoy = decoy_state.is_known_hash(digest)
        if classification is None and not is_decoy:
            continue

        detail: dict = {"subject": subject, "to": to}
        if is_decoy:
            detail["decoy"] = True
        if skipped:
            detail["hash_skipped"] = skipped

        verdict.events.append({
            "host": settings.host_name,
            "user": interactive_user(),
            "event_type": "email_send",
            "file_name": name,
            "file_hash": digest,
            "classification": classification or "confidential",
            "channel": CHANNEL,
            "blocked": settings.email_block,
            "detail": detail,
        })

    verdict.block = settings.email_block and bool(verdict.events)
    return verdict


def _hash_attachment(att, name: str, index: int, tmp_dir: str) -> tuple[str | None, str | None]:
    safe = Path(name.replace("\\", "/")).name or "attachment"
    path = os.path.join(tmp_dir, f"{index}_{safe}")
    # 임시 사본이 감시 경로(%TEMP%)에 생겨도 file_watcher 가 보고하지 않도록
    decoy_state.suppress(path, seconds=30)
    try:
        att.SaveAsFile(path)
    except Exception:  # noqa: BLE001  (COM 오류 포함: 링크 첨부, 권한 등)
        return None, "save_failed"
    try:
        return classifier.hash_file(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _safe_get(mail, attr: str) -> str:
    try:
        return str(getattr(mail, attr) or "")
    except Exception:  # noqa: BLE001  (Outlook 보안 프롬프트 거부 등)
        return ""
