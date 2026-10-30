"""경로가 이동식(USB) 드라이브인지 판별. Windows 외에서는 항상 False."""
import sys


def is_removable(path: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        # 경로의 드라이브 루트(C:\ 등) 추출
        drive = f"{path[0]}:\\" if len(path) >= 2 and path[1] == ":" else path
        DRIVE_REMOVABLE = 2
        return ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOVABLE
    except Exception:
        return False
