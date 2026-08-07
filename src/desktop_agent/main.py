from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

import qasync
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="desktop-agent")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Start without active tool execution.",
    )
    return parser


async def build_application() -> QQmlApplicationEngine:
    return QQmlApplicationEngine()


def main(argv: Sequence[str] | None = None) -> int:
    build_argument_parser().parse_args(argv)
    application = QApplication.instance() or QApplication(
        [sys.argv[0], *(argv if argv is not None else sys.argv[1:])]
    )
    event_loop = qasync.QEventLoop(application)
    asyncio.set_event_loop(event_loop)
    with event_loop:
        _application_engine = event_loop.run_until_complete(build_application())
        event_loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
