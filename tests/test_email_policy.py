import hashlib

import pytest

import decoy_state
from watchers import email_policy


class FakeAttachment:
    def __init__(self, name, data, fail_save=False):
        self.FileName = name
        self.Type = 1  # olByValue
        self._data = data
        self._fail = fail_save
        self.saved_to = None

    def SaveAsFile(self, path):
        if self._fail:
            raise OSError("cannot save")
        self.saved_to = path
        with open(path, "wb") as f:
            f.write(self._data)


class FakeAttachments:
    def __init__(self, items):
        self._items = items
        self.Count = len(items)

    def Item(self, i):  # Outlook 컬렉션은 1부터
        return self._items[i - 1]


class FakeMail:
    def __init__(self, attachments, subject="분기 보고", to="ext@partner.com"):
        self.Subject = subject
        self.To = to
        self.Attachments = FakeAttachments(attachments)


@pytest.fixture
def block_on(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "email_block", True)


def test_blocks_confidential_attachment(tmp_path, block_on):
    data = b"secret numbers"
    mail = FakeMail([FakeAttachment("기밀_재무.xlsx", data)])

    verdict = email_policy.inspect_mail(mail, str(tmp_path))

    assert verdict.block
    [ev] = verdict.events
    assert ev["event_type"] == "email_send"
    assert ev["blocked"] is True
    assert ev["file_name"] == "기밀_재무.xlsx"
    assert ev["file_hash"] == hashlib.sha256(data).hexdigest()
    assert ev["classification"] == "confidential"
    assert ev["channel"] == "email:outlook"
    assert ev["detail"]["to"] == "ext@partner.com"
    assert ev["detail"]["subject"] == "분기 보고"


def test_allows_plain_attachment(tmp_path, block_on):
    mail = FakeMail([FakeAttachment("lunch_menu.pdf", b"menu")])
    verdict = email_policy.inspect_mail(mail, str(tmp_path))
    assert not verdict.block
    assert verdict.events == []


def test_allows_mail_without_attachments(tmp_path, block_on):
    verdict = email_policy.inspect_mail(FakeMail([]), str(tmp_path))
    assert not verdict.block
    assert verdict.events == []


def test_blocks_renamed_decoy_by_hash(tmp_path, block_on):
    data = b"decoy body"
    decoy_state.register_known(hashlib.sha256(data).hexdigest(), len(data))
    mail = FakeMail([FakeAttachment("notes.txt", data)])

    verdict = email_policy.inspect_mail(mail, str(tmp_path))

    assert verdict.block
    [ev] = verdict.events
    assert ev["file_hash"] == hashlib.sha256(data).hexdigest()
    assert ev["detail"]["decoy"] is True


def test_reports_only_flagged_attachments(tmp_path, block_on):
    mail = FakeMail([
        FakeAttachment("photo.png", b"img"),
        FakeAttachment("대외비_계약서.pdf", b"contract"),
    ])
    verdict = email_policy.inspect_mail(mail, str(tmp_path))
    assert verdict.block
    assert [e["file_name"] for e in verdict.events] == ["대외비_계약서.pdf"]


def test_report_only_mode_does_not_block(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "email_block", False)
    mail = FakeMail([FakeAttachment("기밀.docx", b"x")])
    verdict = email_policy.inspect_mail(mail, str(tmp_path))
    assert not verdict.block
    [ev] = verdict.events
    assert ev["blocked"] is False


def test_unsaveable_confidential_attachment_still_blocked(tmp_path, block_on):
    mail = FakeMail([FakeAttachment("기밀.docx", b"x", fail_save=True)])
    verdict = email_policy.inspect_mail(mail, str(tmp_path))
    assert verdict.block
    [ev] = verdict.events
    assert ev["file_hash"] is None
    assert ev["detail"]["hash_skipped"] == "save_failed"


def test_temp_copies_are_removed(tmp_path, block_on):
    att = FakeAttachment("기밀.docx", b"x")
    email_policy.inspect_mail(FakeMail([att]), str(tmp_path))
    assert att.saved_to is not None
    assert list(tmp_path.iterdir()) == []


def test_attachment_name_cannot_escape_temp_dir(tmp_path, block_on):
    work = tmp_path / "work"
    work.mkdir()
    att = FakeAttachment("..\\..\\기밀.docx", b"x")
    email_policy.inspect_mail(FakeMail([att]), str(work))
    assert att.saved_to.startswith(str(work))


def test_temp_copy_is_hidden_from_file_watcher(tmp_path, block_on):
    seen = {}

    class Probe(FakeAttachment):
        def SaveAsFile(self, path):
            seen["suppressed"] = decoy_state.is_suppressed(path)
            super().SaveAsFile(path)

    email_policy.inspect_mail(FakeMail([Probe("기밀.docx", b"x")]), str(tmp_path))
    assert seen["suppressed"] is True
