"""경로가 이동식(USB) 드라이브인지 판별. Windows 외에서는 항상 False."""
import string
import sys

DRIVE_REMOVABLE = 2


def is_removable(path: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        # 경로의 드라이브 루트(C:\ 등) 추출
        drive = f"{path[0]}:\\" if len(path) >= 2 and path[1] == ":" else path
        return ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOVABLE
    except Exception:
        return False


def removable_drives() -> list[str]:
    """현재 연결된 이동식 드라이브 루트 목록 (예: ['E:\\']). Windows 외에서는 []."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return []
    return [
        f"{letter}:\\"
        for i, letter in enumerate(string.ascii_uppercase)
        if mask & (1 << i) and is_removable(f"{letter}:\\")
    ]
