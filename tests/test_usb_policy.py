import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import usb_policy


def test_policy_writes_and_verifies_machine_setting(monkeypatch):
    registry = MagicMock()
    registry.KEY_SET_VALUE = 2
    registry.KEY_QUERY_VALUE = 1
    registry.KEY_WOW64_64KEY = 256
    registry.REG_DWORD = 4
    registry.QueryValueEx.return_value = (1, 4)
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(usb_policy, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(usb_policy.settings, "usb_block_writes", True)
    events = []
    monkeypatch.setattr(usb_policy, "publish", events.append)
    assert usb_policy.configure_usb_policy()
    registry.SetValueEx.assert_called_once()
    assert events[0]["detail"]["status"] == "configured"
    assert events[0]["blocked"] is False


def test_permission_failure_reported(monkeypatch):
    registry = MagicMock()
    registry.CreateKeyEx.side_effect = PermissionError("administrator required")
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(usb_policy, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(usb_policy.settings, "usb_block_writes", True)
    events = []
    monkeypatch.setattr(usb_policy, "publish", events.append)
    assert not usb_policy.configure_usb_policy()
    assert events[0]["detail"]["status"] == "failed"
    assert events[0]["blocked"] is False


def test_disabled_does_not_mutate_policy(monkeypatch):
    monkeypatch.setattr(usb_policy.settings, "usb_block_writes", False)
    publish = MagicMock()
    monkeypatch.setattr(usb_policy, "publish", publish)
    assert not usb_policy.configure_usb_policy()
    publish.assert_not_called()
