# coding: utf-8
"""Claude 官方安装源、平台选择与 Linux 软件包解析。"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import logging
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urljoin, urlparse


INSTALL_SOURCES_FILE_NAME = "claude_install_sources.json"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstallSpec:
    product: str
    display_name: str
    kind: str
    url: str
    file_name: str
    allowed_hosts: tuple[str, ...]
    max_bytes: int
    metadata_max_bytes: int
    timeout_seconds: int
    verification_timeout_seconds: int
    chunk_bytes: int
    user_agent: str
    windows_publisher: str = ""
    help_url: str = ""
    packages_url: str = ""
    repository_base_url: str = ""
    architecture: str = ""
    expected_bytes: int = 0
    sha256: str = ""
    resolve_redirect_with_curl: bool = False


def _install_sources_path() -> Path:
    override = os.environ.get("CONFIGPILOT_CLAUDE_INSTALL_SOURCES")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "resources" / INSTALL_SOURCES_FILE_NAME


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
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "AnthropicClaude" / "claude.exe"
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


def _positive_int(value: object, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是正整数") from exc
    if parsed <= 0:
        raise ValueError(f"{name} 必须是正整数")
    return parsed


def _security_settings(sources: dict) -> dict:
    security = sources.get("security")
    if not isinstance(security, dict):
        raise ValueError("Claude 安装安全配置无效")
    hosts = security.get("allowedHosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("Claude 安装安全域名列表无效")
    help_hosts = security.get("helpHosts")
    if not isinstance(help_hosts, list) or not help_hosts:
        raise ValueError("Claude 安装帮助域名列表无效")
    security = dict(security)
    security["allowedHosts"] = tuple(str(host).lower() for host in hosts)
    security["helpHosts"] = tuple(str(host).lower() for host in help_hosts)
    return security


def _validate_https_url(value: object, allowed_hosts: tuple[str, ...]) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("官方安装地址必须是完整的 HTTPS URL")
    if parsed.hostname.lower() not in allowed_hosts:
        raise ValueError(f"安装地址域名不在允许列表中: {parsed.hostname}")
    return url


def _validate_file_name(value: object) -> str:
    name = str(value or "").strip()
    if not name or Path(name).name != name:
        raise ValueError("安装文件名无效")
    return name


def _desktop_install_key() -> str:
    machine = platform.machine().strip().lower().replace("_", "-")
    is_arm64 = machine in {"arm64", "aarch64"}
    if sys.platform == "win32":
        return "windows-arm64" if is_arm64 else "windows-x64"
    if sys.platform == "darwin":
        return "macos-universal"
    if sys.platform.startswith("linux"):
        return "linux"
    raise ValueError(f"当前平台暂不支持内置安装 Claude Desktop: {sys.platform}")


def _base_spec(product: str, display_name: str, raw: dict, security: dict) -> InstallSpec:
    kind = str(raw.get("kind", "")).strip()
    max_key = "maxScriptBytes" if kind.endswith("script") else "maxInstallerBytes"
    hosts = security["allowedHosts"]
    url = _validate_https_url(raw.get("url"), hosts) if raw.get("url") else ""
    return InstallSpec(
        product=product,
        display_name=display_name,
        kind=kind,
        url=url,
        file_name=_validate_file_name(raw.get("fileName")) if raw.get("fileName") else "",
        allowed_hosts=hosts,
        max_bytes=_positive_int(security.get(max_key), max_key),
        metadata_max_bytes=_positive_int(security.get("maxMetadataBytes"), "maxMetadataBytes"),
        timeout_seconds=_positive_int(security.get("networkTimeoutSeconds"), "networkTimeoutSeconds"),
        verification_timeout_seconds=_positive_int(
            security.get("verificationTimeoutSeconds"), "verificationTimeoutSeconds"
        ),
        chunk_bytes=_positive_int(security.get("downloadChunkBytes"), "downloadChunkBytes"),
        user_agent=str(security.get("userAgent", "ConfigPilot")).strip() or "ConfigPilot",
        windows_publisher=str(security.get("windowsPublisher", "")).strip(),
        help_url=(
            _validate_https_url(raw.get("helpUrl"), security["helpHosts"])
            if raw.get("helpUrl") else ""
        ),
        resolve_redirect_with_curl=bool(raw.get("resolveRedirectWithCurl", False)),
    )


def _linux_spec(product: str, raw: dict, security: dict) -> InstallSpec:
    spec = _base_spec(product, "Claude Desktop", raw, security)
    machine = platform.machine().strip().lower().replace("_", "-")
    architectures = raw.get("architectures")
    if not isinstance(architectures, dict) or machine not in architectures:
        raise ValueError(f"Claude Desktop Linux 不支持当前架构: {machine}")
    architecture = str(architectures[machine]).strip()
    packages_url = str(raw.get("packagesUrlTemplate", "")).format(
        architecture=architecture
    )
    return replace(
        spec,
        architecture=architecture,
        packages_url=_validate_https_url(packages_url, spec.allowed_hosts),
        repository_base_url=_validate_https_url(
            raw.get("repositoryBaseUrl"), spec.allowed_hosts
        ),
    )


def official_install_spec(product: str) -> InstallSpec:
    sources = _read_install_sources()
    security = _security_settings(sources)
    if product == "claude-code":
        code_sources = sources.get("claudeCode")
        if not isinstance(code_sources, dict):
            raise ValueError("Claude Code 安装源配置无效")
        key = "windows" if sys.platform == "win32" else "unix"
        raw = code_sources.get(key)
        if not isinstance(raw, dict):
            raise ValueError("Claude Code 当前平台安装源无效")
        return _base_spec(product, "Claude Code CLI", raw, security)
    if product != "claude-desktop":
        raise ValueError("未知的 Claude 安装项")
    desktop_sources = sources.get("claudeDesktop")
    if not isinstance(desktop_sources, dict):
        raise ValueError("Claude Desktop 安装源配置无效")
    key = _desktop_install_key()
    raw = desktop_sources.get(key)
    if not isinstance(raw, dict):
        raise ValueError("Claude Desktop 当前平台安装源无效")
    return _linux_spec(product, raw, security) if key == "linux" else _base_spec(
        product, "Claude Desktop", raw, security
    )


def official_install_url(product: str) -> str:
    spec = official_install_spec(product)
    return spec.url or spec.help_url


def _version_key(value: str) -> tuple:
    parts = re.split(r"(\d+)", value)
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


def _package_entries(index_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for stanza in re.split(r"\r?\n\r?\n", index_text.strip()):
        entry: dict[str, str] = {}
        for line in stanza.splitlines():
            if ":" in line and not line.startswith((" ", "\t")):
                key, value = line.split(":", 1)
                entry[key] = value.strip()
        if entry:
            entries.append(entry)
    return entries


def resolve_linux_package(spec: InstallSpec, index_text: str) -> InstallSpec:
    candidates = [
        entry for entry in _package_entries(index_text)
        if entry.get("Package") == "claude-desktop"
        and entry.get("Architecture") == spec.architecture
    ]
    if not candidates:
        raise ValueError("Anthropic 仓库中没有当前架构的 Claude Desktop")
    selected = max(candidates, key=lambda entry: _version_key(entry.get("Version", "")))
    filename = selected.get("Filename", "")
    if not filename.endswith(".deb") or ".." in Path(filename).parts:
        raise ValueError("Anthropic 仓库返回了无效的 DEB 路径")
    size = _positive_int(selected.get("Size"), "DEB Size")
    sha256 = selected.get("SHA256", "").lower()
    if size > spec.max_bytes or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Anthropic 仓库中的 DEB 校验信息无效")
    url = urljoin(spec.repository_base_url.rstrip("/") + "/", filename)
    return replace(
        spec,
        url=_validate_https_url(url, spec.allowed_hosts),
        file_name=Path(filename).name,
        expected_bytes=size,
        sha256=sha256,
    )
