"""대화형(로그인) 사용자 기준 정보: 사용자명, 프로필, Downloads 폴더, 파일 생성 시각.

agent가 SYSTEM 서비스로 돌면 Path.home()/getpass 는 로그인 사용자가 아니므로,
Windows 에서는 활성 콘솔 세션의 사용자 토큰으로 조회한다.
Windows 외(개발 환경)에서는 현재 프로세스 사용자 기준으로 폴백.
"""
import getpass
import os
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
    _FOLDERID_DOWNLOADS = _GUID(
        0x374DE290, 0x123F, 0x4565,
        (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B),
    )


def _process_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _running_as_system() -> bool:
    return IS_WINDOWS and _process_user().upper() in ("SYSTEM", f"{os.environ.get('COMPUTERNAME', '')}$".upper())


def _active_session_id() -> int | None:
    fn = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId
    fn.restype = wintypes.DWORD
    sid = fn()
    return None if sid == 0xFFFFFFFF else sid


def _session_user_token():
    """SYSTEM 일 때 활성 콘솔 세션 사용자 토큰(HANDLE). 사용자 없음/실패 시 None."""
    sid = _active_session_id()
    if sid is None:
        return None
    token = wintypes.HANDLE()
    if not ctypes.windll.wtsapi32.WTSQueryUserToken(wintypes.ULONG(sid), ctypes.byref(token)):
        return None
    return token


def interactive_user() -> str:
    """로그에 남길 사용자명. SYSTEM 서비스라면 활성 콘솔 세션 사용자."""
    if not _running_as_system():
        return _process_user()
    try:
        sid = _active_session_id()
        if sid is None:
            return "unknown"
        buf = wintypes.LPWSTR()
        size = wintypes.DWORD()
        WTS_USER_NAME = 5
        if not ctypes.windll.wtsapi32.WTSQuerySessionInformationW(
            None, sid, WTS_USER_NAME, ctypes.byref(buf), ctypes.byref(size)
        ):
            return "unknown"
        try:
            return buf.value or "unknown"
        finally:
            ctypes.windll.wtsapi32.WTSFreeMemory(buf)
    except Exception:
        return "unknown"


def _with_token(fn):
    """SYSTEM 이면 사용자 토큰을 열어 fn(token) 호출 후 닫음. 일반 사용자면 fn(None)."""
    token = None
    if _running_as_system():
        token = _session_user_token()
        if token is None:
            return None
    try:
        return fn(token)
    finally:
        if token is not None:
            ctypes.windll.kernel32.CloseHandle(token)


def _known_folder_downloads(token) -> Path | None:
    ppath = ctypes.c_wchar_p()
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(_FOLDERID_DOWNLOADS), 0, token, ctypes.byref(ppath)
    )
    try:
        return Path(ppath.value) if hr == 0 and ppath.value else None
    finally:
        ctypes.windll.ole32.CoTaskMemFree(ppath)


def _profile_dir_from_token(token) -> Path | None:
    if token is None:
        return Path(os.environ["USERPROFILE"]) if os.environ.get("USERPROFILE") else None
    size = wintypes.DWORD(260)
    buf = ctypes.create_unicode_buffer(size.value)
    if not ctypes.windll.userenv.GetUserProfileDirectoryW(token, buf, ctypes.byref(size)):
        return None
    return Path(buf.value)


def profile_dir() -> Path | None:
    """대화형 사용자 프로필 폴더. 로그인 사용자가 없으면 None."""
    if not IS_WINDOWS:
        return Path.home()
    try:
        return _with_token(_profile_dir_from_token)
    except Exception as exc:
        print(f"[user_session] 프로필 경로 조회 실패: {exc}")
        return None


def downloads_dir() -> Path | None:
    """대화형 사용자 Downloads. Known Folder 우선(리디렉션 반영), 실패 시 <프로필>\\Downloads.

    로그인 사용자가 없어 해석할 수 없으면 None (호출자가 다음 주기에 재시도).
    """
    if not IS_WINDOWS:
        return Path.home() / "Downloads"
    try:
        found = _with_token(_known_folder_downloads)
        if found:
            return found
    except Exception as exc:
        print(f"[user_session] Known Folder 조회 실패, 프로필 폴백: {exc}")
    profile = profile_dir()
    return profile / "Downloads" if profile else None


def set_creation_time(path: str, timestamp: float) -> None:
    """Windows 파일 생성 시각 설정 (os.utime 은 생성 시각을 못 바꿈). 그 외 OS는 무시."""
    if not IS_WINDOWS:
        return
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_ALL = 0x7
    OPEN_EXISTING = 3
    INVALID_HANDLE = wintypes.HANDLE(-1).value
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = wintypes.HANDLE
    handle = k32.CreateFileW(str(path), GENERIC_WRITE, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None)
    if handle == INVALID_HANDLE:
        raise OSError(ctypes.GetLastError(), "CreateFileW 실패", path)
    try:
        # FILETIME: 1601-01-01 기준 100ns 단위
        ft = int((timestamp + 11644473600) * 10_000_000)
        ctime = wintypes.FILETIME(ft & 0xFFFFFFFF, ft >> 32)
        if not k32.SetFileTime(wintypes.HANDLE(handle), ctypes.byref(ctime), None, None):
            raise OSError(ctypes.GetLastError(), "SetFileTime 실패", path)
    finally:
        k32.CloseHandle(wintypes.HANDLE(handle))
