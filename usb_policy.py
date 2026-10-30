"""Machine-wide removable-disk write policy; never claims per-file interception.

Policy changes persist after exit and may require a Windows restart.
"""
import sys

from config import settings
from event_bus import publish
from user_session import interactive_user

POLICY_KEY = (
    r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices"
    r"\{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}"
)


def configure_usb_policy() -> bool:
    """Configure write denial before watchers start. False means not configured."""
    if not settings.usb_block_writes:
        return False  # Never remove a policy owned by an administrator.
    detail = {"action": "usb_write_policy", "scope": "all_removable_disks"}
    configured = False
    try:
        if sys.platform != "win32":
            raise OSError("USB write policy requires Windows")
        import winreg

        access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, POLICY_KEY, 0, access) as key:
            winreg.SetValueEx(key, "Deny_Write", 0, winreg.REG_DWORD, 1)
            value, kind = winreg.QueryValueEx(key, "Deny_Write")
            if value != 1 or kind != winreg.REG_DWORD:
                raise OSError("USB policy read-back failed")
        configured = True
        detail.update(status="configured", restart_required=True)
    except OSError as exc:
        detail.update(status="failed", error=str(exc))
    publish({
        "host": settings.host_name,
        "user": interactive_user(),
        "event_type": "usb_copy",  # Existing backend event vocabulary.
        "channel": "usb:policy",
        "classification": None,
        "blocked": False,  # A policy configuration is not a blocked copy attempt.
        "detail": detail,
    })
    print(f"[usb_policy] {detail}")
    return configured
