# coding: utf-8
"""ConfigPilot 应用元数据与更新配置加载。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


_VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)+(?:-[0-9A-Za-z.-]+)?$")
_REPOSITORY_PATTERN = re.compile(r"^[^\s/]+/[^\s/]+$")


@dataclass(frozen=True)
class UpdateSettings:
    """应用更新所需的可配置参数。"""

    repository: str
    asset_keyword: str
    auto_check: bool
    startup_delay_ms: int
    windows_installer_args: str


@dataclass(frozen=True)
class AppSettings:
    """应用运行时元数据。"""

    version: str
    updates: UpdateSettings


def _required_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"配置项 {key!r} 必须是非空字符串")
    return value.strip()


def _required_bool(data: dict, key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"配置项 {key!r} 必须是布尔值")
    return value


def _startup_delay(data: dict) -> int:
    value = data.get("startup_delay_ms")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("配置项 'startup_delay_ms' 必须是整数")
    if not 0 <= value <= 60_000:
        raise ValueError("配置项 'startup_delay_ms' 必须位于 0 到 60000 之间")
    return value


def _validate_version(value: str) -> str:
    if not _VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"应用版本号格式无效: {value!r}")
    return value


def _validate_repository(value: str) -> str:
    if not _REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError(f"更新仓库必须使用 owner/repo 格式: {value!r}")
    return value


def _parse_updates(data: object) -> UpdateSettings:
    if not isinstance(data, dict):
        raise ValueError("配置项 'updates' 必须是对象")
    return UpdateSettings(
        repository=_validate_repository(_required_string(data, "repository")),
        asset_keyword=_required_string(data, "asset_keyword"),
        auto_check=_required_bool(data, "auto_check"),
        startup_delay_ms=_startup_delay(data),
        windows_installer_args=_required_string(data, "windows_installer_args"),
    )


def load_app_settings(path: str | Path) -> AppSettings:
    """读取并校验应用配置，配置损坏时显式失败。"""
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("应用配置根节点必须是对象")
    return AppSettings(
        version=_validate_version(_required_string(data, "version")),
        updates=_parse_updates(data.get("updates")),
    )
