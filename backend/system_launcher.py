# coding: utf-8
"""在工作线程调用的跨平台系统目标启动器。"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


LOGGER = logging.getLogger(__name__)


def is_http_url(value: object) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def open_external_target(target: object) -> bool:
    """启动目录、文件或 URL；本函数可能阻塞，只能从工作线程调用。"""
    text = str(target or "").strip()
    if not text:
        return False
    try:
        if sys.platform == "win32":
            os.startfile(text)
            return True
        command_name = "open" if sys.platform == "darwin" else "xdg-open"
        command = shutil.which(command_name)
        if not command:
            return False
        subprocess.Popen(
            [command, text],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        LOGGER.exception("系统无法打开目标: %s", text)
        return False
