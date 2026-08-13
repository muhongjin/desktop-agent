from __future__ import annotations

import argparse
import asyncio
import ctypes
import sys
from collections.abc import Sequence
from pathlib import Path

import qasync
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

_single_instance_handle = None


def acquire_single_instance() -> bool:
    global _single_instance_handle
    if sys.platform != "win32":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.GetLastError.restype = ctypes.c_ulong
    handle = kernel32.CreateMutexW(None, False, "Local\\DesktopAgent.SingleInstance")
    if not handle:
        return True
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return False
    _single_instance_handle = handle
    return True


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="desktop-agent")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Start without active tool execution.",
    )
    return parser


async def build_application(*, safe_mode: bool = False) -> QQmlApplicationEngine:
    from desktop_agent.app import build_application as compose_application

    return await compose_application(safe_mode=safe_mode)


def main(argv: Sequence[str] | None = None) -> int:
    if not acquire_single_instance():
        return 0
    args = build_argument_parser().parse_args(argv)
    application = QApplication.instance() or QApplication(
        [sys.argv[0], *(argv if argv is not None else sys.argv[1:])]
    )
    application.setWindowIcon(
        QIcon(str(Path(__file__).parent / "resources" / "app-icon.ico"))
    )
    event_loop = qasync.QEventLoop(application)
    asyncio.set_event_loop(event_loop)
    with event_loop:
        _application_engine = event_loop.run_until_complete(
            build_application(safe_mode=args.safe_mode)
        )
        event_loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
