# coding: utf-8
"""Claude Desktop 开发者模式与第三方推理配置后端。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
import uuid

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from backend.claude_install_sources import (
    claude_desktop_installed,
    claude_install_target,
    official_install_url,
)


LOGGER = logging.getLogger(__name__)

CLAUDE_APP_NAME = "Claude"
CLAUDE_THIRD_PARTY_DIR_NAME = "Claude-3p"
CONFIG_FILE_NAME = "claude_desktop_config.json"
DEVELOPER_SETTINGS_FILE_NAME = "developer_settings.json"
CONFIG_LIBRARY_DIR_NAME = "configLibrary"
CONFIG_LIBRARY_META_FILE_NAME = "_meta.json"
DEFAULT_PROFILE_NAME = "ConfigPilot"
SUPPORTED_AUTH_SCHEMES = {"bearer", "x-api-key"}


def _primary_data_dir() -> Path:
    override = os.environ.get("CONFIGPILOT_CLAUDE_PRIMARY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / CLAUDE_APP_NAME
    return Path.home() / "Library" / "Application Support" / CLAUDE_APP_NAME


def _third_party_data_dir() -> Path:
    override = os.environ.get("CONFIGPILOT_CLAUDE_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / CLAUDE_THIRD_PARTY_DIR_NAME
    return Path.home() / "Library" / "Application Support" / CLAUDE_THIRD_PARTY_DIR_NAME


def _read_json_object(path: Path, *, default: dict | None = None) -> dict:
    if not path.is_file():
        return dict(default or {})
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 顶层必须是 JSON 对象")
    return value


def _backup_file(path: Path) -> None:
    if path.is_file():
        shutil.copy2(path, path.with_name(path.name + ".bak"))


def _atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup_file(path)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            LOGGER.debug("无法调整 Claude 配置文件权限: %s", path, exc_info=True)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning("清理 Claude 临时配置失败: %s", temporary_path, exc_info=True)
        raise


def _valid_profile_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _parse_models(text: str) -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        model = line.strip()
        if model and model not in seen:
            seen.add(model)
            models.append(model)
    return models


def _models_to_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    names: list[str] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            continue
        if name:
            names.append(name)
    return "\n".join(names)


def _parse_headers(text: str) -> dict[str, str]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"额外 Header 不是有效 JSON：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("额外 Header 必须是 JSON 对象")
    headers: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("Header 名称不能为空")
        if not isinstance(raw_value, str):
            raise ValueError(f"Header {key} 的值必须是字符串")
        headers[key] = raw_value
    return headers


def _validate_endpoint(value: str) -> str:
    endpoint = value.strip()
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Gateway endpoint 必须是完整的 http(s) URL")
    return endpoint


class ClaudeDesktopConfig(QObject):
    """读取并安全写入 Claude Desktop 的第三方推理配置库。"""

    changed = Signal()
    notify = Signal(int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._primary_dir = _primary_data_dir()
        self._data_dir = _third_party_data_dir()
        self._install_target = claude_install_target()
        self._config_library_dir = self._data_dir / CONFIG_LIBRARY_DIR_NAME
        self._meta_path = self._config_library_dir / CONFIG_LIBRARY_META_FILE_NAME
        self._desktop_config_path = self._data_dir / CONFIG_FILE_NAME
        self._developer_settings_paths = tuple(
            dict.fromkeys(
                [
                    self._primary_dir / DEVELOPER_SETTINGS_FILE_NAME,
                    self._data_dir / DEVELOPER_SETTINGS_FILE_NAME,
                ]
            )
        )
        self._active_config_path = self._config_library_dir
        self._installed = False
        self._developer_mode_enabled = False
        self._third_party_enabled = False
        self._endpoint = ""
        self._auth_scheme = "bearer"
        self._models_text = ""
        self._has_api_key = False
        self._header_count = 0
        self._profile_name = ""
        self.reload()

    @Property(str, notify=changed)
    def dataDir(self):
        return str(self._data_dir)

    @Property(str, notify=changed)
    def configPath(self):
        return str(self._active_config_path)

    @Property(bool, notify=changed)
    def installed(self):
        return self._installed

    @Property(bool, notify=changed)
    def developerModeEnabled(self):
        return self._developer_mode_enabled

    @Property(bool, notify=changed)
    def thirdPartyEnabled(self):
        return self._third_party_enabled

    @Property(str, notify=changed)
    def endpoint(self):
        return self._endpoint

    @Property(str, notify=changed)
    def authScheme(self):
        return self._auth_scheme

    @Property(str, notify=changed)
    def modelsText(self):
        return self._models_text

    @Property(bool, notify=changed)
    def hasApiKey(self):
        return self._has_api_key

    @Property(int, notify=changed)
    def headerCount(self):
        return self._header_count

    @Property(str, notify=changed)
    def profileName(self):
        return self._profile_name

    @staticmethod
    def _validated_entries(meta: dict) -> list[dict]:
        entries = meta.get("entries", [])
        if not isinstance(entries, list):
            raise ValueError("_meta.json 的 entries 必须是数组")
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or not _valid_profile_id(entry.get("id"))
                or not isinstance(entry.get("name"), str)
            ):
                raise ValueError("_meta.json 包含无效配置条目，已拒绝覆盖")
        return entries

    def _active_profile(self, meta: dict) -> tuple[str, str]:
        entries = self._validated_entries(meta)
        applied_id = meta.get("appliedId", "")
        for entry in entries:
            if (
                isinstance(entry, dict)
                and entry.get("id") == applied_id
                and _valid_profile_id(applied_id)
            ):
                return applied_id, str(entry.get("name", ""))
        return "", ""

    @Slot()
    def reload(self):
        self._installed = claude_desktop_installed(self._install_target)
        self._developer_mode_enabled = False
        self._third_party_enabled = False
        self._endpoint = ""
        self._auth_scheme = "bearer"
        self._models_text = ""
        self._has_api_key = False
        self._header_count = 0
        self._profile_name = ""
        self._active_config_path = self._config_library_dir

        try:
            for path in self._developer_settings_paths:
                settings = _read_json_object(path)
                if settings.get("allowDevTools") is True:
                    self._developer_mode_enabled = True

            desktop_config = _read_json_object(self._desktop_config_path)
            meta = _read_json_object(self._meta_path)
            profile_id, profile_name = self._active_profile(meta)
            if profile_id:
                profile_path = self._config_library_dir / f"{profile_id}.json"
                profile = _read_json_object(profile_path)
                self._active_config_path = profile_path
                self._profile_name = profile_name
                self._endpoint = str(profile.get("inferenceGatewayBaseUrl", ""))
                auth_scheme = str(
                    profile.get("inferenceGatewayAuthScheme", "bearer")
                ).strip()
                self._auth_scheme = (
                    auth_scheme if auth_scheme in SUPPORTED_AUTH_SCHEMES else "bearer"
                )
                self._models_text = _models_to_text(profile.get("inferenceModels"))
                self._has_api_key = bool(profile.get("inferenceGatewayApiKey"))
                headers = profile.get(
                    "inferenceCustomHeaders",
                    profile.get("inferenceGatewayHeaders", {}),
                )
                self._header_count = len(headers) if isinstance(headers, dict) else 0
                self._third_party_enabled = (
                    desktop_config.get("deploymentMode") == "3p"
                    and profile.get("inferenceProvider") == "gateway"
                    and bool(self._endpoint)
                )
        except Exception as exc:
            LOGGER.exception("读取 Claude Desktop 配置失败")
            self.notify.emit(3, "Claude 配置读取失败", str(exc))
        self.changed.emit()

    def _prepare_profile(self, cfg: dict) -> tuple[dict, dict, Path]:
        meta = _read_json_object(self._meta_path)
        entries = self._validated_entries(meta)

        profile_id, _ = self._active_profile(meta)
        if not profile_id:
            valid_entry = next(
                (
                    entry
                    for entry in entries
                    if isinstance(entry, dict) and _valid_profile_id(entry.get("id"))
                ),
                None,
            )
            if valid_entry:
                profile_id = str(valid_entry["id"])
                meta["appliedId"] = profile_id
            else:
                profile_id = str(uuid.uuid4())
                entry = {"id": profile_id, "name": DEFAULT_PROFILE_NAME}
                entries.append(entry)
                meta["entries"] = entries
                meta["appliedId"] = profile_id

        profile_path = self._config_library_dir / f"{profile_id}.json"
        profile = _read_json_object(profile_path)
        endpoint = _validate_endpoint(str(cfg.get("endpoint", "")))
        auth_scheme = str(cfg.get("authScheme", "bearer")).strip()
        if auth_scheme not in SUPPORTED_AUTH_SCHEMES:
            raise ValueError("认证方式只能是 bearer 或 x-api-key")

        models_text = str(cfg.get("modelsText", ""))
        profile["inferenceProvider"] = "gateway"
        profile["inferenceGatewayBaseUrl"] = endpoint
        profile["inferenceCredentialKind"] = "static"
        profile["inferenceGatewayAuthScheme"] = auth_scheme

        if models_text != self._models_text:
            models = _parse_models(models_text)
            if models:
                profile["inferenceModels"] = models
            else:
                profile.pop("inferenceModels", None)

        api_key = str(cfg.get("apiKey", "")).strip()
        if bool(cfg.get("clearApiKey", False)):
            profile.pop("inferenceGatewayApiKey", None)
        elif api_key:
            profile["inferenceGatewayApiKey"] = api_key

        headers_text = str(cfg.get("headersText", "")).strip()
        if bool(cfg.get("clearHeaders", False)):
            profile.pop("inferenceCustomHeaders", None)
            profile.pop("inferenceGatewayHeaders", None)
        elif headers_text:
            profile["inferenceCustomHeaders"] = _parse_headers(headers_text)
            profile.pop("inferenceGatewayHeaders", None)

        return meta, profile, profile_path

    def _saved_gateway_profile(self) -> dict:
        meta = _read_json_object(self._meta_path)
        profile_id, _ = self._active_profile(meta)
        if not profile_id:
            raise ValueError("尚未保存 Gateway 配置，请先填写并应用")
        profile_path = self._config_library_dir / f"{profile_id}.json"
        profile = _read_json_object(profile_path)
        if profile.get("inferenceProvider") != "gateway":
            raise ValueError("当前配置档案不是 Gateway 类型")
        _validate_endpoint(str(profile.get("inferenceGatewayBaseUrl", "")))
        return profile

    @Slot(str)
    def openOfficialInstallSource(self, product):
        try:
            product_name = {
                "claude-code": "Claude Code CLI",
                "claude-desktop": "Claude Desktop",
            }.get(product)
            if not product_name:
                raise ValueError("未知的 Claude 安装项")
            url = official_install_url(product)
            if not QDesktopServices.openUrl(QUrl(url)):
                raise RuntimeError("系统未能打开官方安装入口")
            self.notify.emit(
                0,
                f"已打开 {product_name} 官方安装入口",
                "请按 Anthropic 官方页面提示完成安装。",
            )
        except ValueError as exc:
            self.notify.emit(2, "安装入口不可用", str(exc))
        except Exception as exc:
            LOGGER.exception("打开 Claude 官方安装入口失败")
            self.notify.emit(3, "打开失败", str(exc))

    @Slot(bool)
    def setDeveloperModeEnabled(self, enabled):
        try:
            for path in self._developer_settings_paths:
                settings = _read_json_object(path)
                settings["allowDevTools"] = bool(enabled)
                _atomic_write_json(path, settings)
            self.reload()
            state = "启用" if enabled else "关闭"
            self.notify.emit(
                1,
                f"Developer Mode 已{state}",
                "请完全退出并重新打开 Claude Desktop。",
            )
        except Exception as exc:
            LOGGER.exception("切换 Claude Desktop Developer Mode 失败")
            self.reload()
            self.notify.emit(3, "切换失败", str(exc))

    @Slot(bool)
    def setThirdPartyEnabled(self, enabled):
        try:
            if enabled:
                self._saved_gateway_profile()
            desktop_config = _read_json_object(self._desktop_config_path)
            desktop_config["deploymentMode"] = "3p" if enabled else "1p"
            _atomic_write_json(self._desktop_config_path, desktop_config)
            self.reload()
            state = "启用" if enabled else "关闭"
            self.notify.emit(
                1,
                f"Gateway 已{state}",
                "已保留配置档案；请完全退出并重新打开 Claude Desktop。",
            )
        except ValueError as exc:
            self.reload()
            self.notify.emit(2, "无法启用 Gateway", str(exc))
        except Exception as exc:
            LOGGER.exception("切换 Claude Desktop Gateway 失败")
            self.reload()
            self.notify.emit(3, "切换失败", str(exc))

    @Slot("QVariantMap")
    def applyConfig(self, cfg):
        try:
            meta, profile, profile_path = self._prepare_profile(dict(cfg))
            desktop_config = _read_json_object(self._desktop_config_path)
            desktop_config["deploymentMode"] = "3p"

            developer_settings: list[tuple[Path, dict]] = []
            for path in self._developer_settings_paths:
                settings = _read_json_object(path)
                settings["allowDevTools"] = True
                developer_settings.append((path, settings))

            _atomic_write_json(profile_path, profile)
            _atomic_write_json(self._meta_path, meta)
            for path, settings in developer_settings:
                _atomic_write_json(path, settings)
            # 最后切换 deploymentMode，避免 Claude 在配置库尚未写完时进入 3p 模式。
            _atomic_write_json(self._desktop_config_path, desktop_config)

            self.reload()
            self.notify.emit(
                1,
                "Claude Desktop 已配置",
                "开发者模式与第三方 Gateway 已写入；请完全退出并重新打开 Claude Desktop。",
            )
        except ValueError as exc:
            self.notify.emit(2, "参数无效", str(exc))
        except Exception as exc:
            LOGGER.exception("写入 Claude Desktop 配置失败")
            self.notify.emit(3, "应用失败", str(exc))

    @Slot()
    def openConfigDirectory(self):
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._data_dir))):
                raise RuntimeError("系统未能打开配置目录")
        except Exception as exc:
            LOGGER.exception("打开 Claude Desktop 配置目录失败")
            self.notify.emit(3, "打开失败", str(exc))
