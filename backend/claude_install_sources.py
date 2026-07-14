# coding: utf-8
"""Claude 官方安装入口与跨平台安装检测。"""

from __future__ import annotations

import json
import logging
import os
import platform
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse


INSTALL_SOURCES_FILE_NAME = "claude_install_sources.json"
LOGGER = logging.getLogger(__name__)


def _install_sources_path() -> Path:
    override = os.environ.get("CONFIGPILOT_CLAUDE_INSTALL_SOURCES")
    if override:
        return Path(override).expanduser()
    return (
        Path(__file__).resolve().parents[1]
        / "resources"
        / INSTALL_SOURCES_FILE_NAME
    )


def _read_install_sources() -> dict:
    with _install_sources_path().open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Claude 安装源配置必须是 JSON 对象")
    return value


def claude_install_target() -> Path | None:
    override = os.environ.get("CONFIGPILOT_CLAUDE_EXECUTABLE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "AnthropicClaude" / "claude.exe"
    if sys.platform == "darwin":
        return Path("/Applications/Claude.app")
    return None


def claude_desktop_installed(install_target: Path | None) -> bool:
    if install_target is not None:
        return install_target.exists()
    if not sys.platform.startswith("linux"):
        return False
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", "claude-desktop"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        return result.returncode == 0 and result.stdout.strip() == "install ok installed"
    except (OSError, subprocess.SubprocessError):
        LOGGER.debug("查询 Claude Desktop Linux 软件包失败", exc_info=True)
        return False


def _validate_install_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("官方安装入口必须是完整的 HTTPS URL")
    return url


def _desktop_install_key() -> str:
    machine = platform.machine().strip().lower().replace("_", "-")
    is_arm64 = machine in {"arm64", "aarch64"}
    if sys.platform == "win32":
        return "windows-arm64" if is_arm64 else "windows-x64"
    if sys.platform == "darwin":
        return "macos-universal"
    if sys.platform.startswith("linux"):
        return "linux"
    return "fallback"


def official_install_url(product: str) -> str:
    sources = _read_install_sources()
    if product == "claude-code":
        code_sources = sources.get("claudeCode", {})
        if not isinstance(code_sources, dict):
            raise ValueError("Claude Code 安装源配置无效")
        return _validate_install_url(code_sources.get("all"))
    if product == "claude-desktop":
        desktop_sources = sources.get("claudeDesktop", {})
        if not isinstance(desktop_sources, dict):
            raise ValueError("Claude Desktop 安装源配置无效")
        return _validate_install_url(
            desktop_sources.get(
                _desktop_install_key(), desktop_sources.get("fallback")
            )
        )
    raise ValueError("未知的 Claude 安装项")
