# coding: utf-8
"""Claude 安装文件的平台签名与脚本来源校验。"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from backend.claude_install_sources import InstallSpec


POWERSHELL_SCRIPT_MARKER = "https://downloads.claude.ai/claude-code-releases"
SHELL_SCRIPT_MARKER = 'DOWNLOAD_BASE_URL="https://downloads.claude.ai/claude-code-releases"'


def _verify_script(spec: InstallSpec, path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if "<html" in text.lower() or "<!doctype" in text.lower():
        raise RuntimeError("官方脚本地址返回了网页内容")
    marker = (
        POWERSHELL_SCRIPT_MARKER
        if spec.kind == "powershell-script"
        else SHELL_SCRIPT_MARKER
    )
    if marker not in text:
        raise RuntimeError("官方 Claude Code 安装脚本缺少预期发布地址")


def _verify_windows_signature(spec: InstallSpec, path: Path) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        raise RuntimeError("系统未找到 PowerShell，无法验证安装包签名")
    env = os.environ.copy()
    env["CONFIGPILOT_INSTALLER_PATH"] = str(path)
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "$s=Get-AuthenticodeSignature -LiteralPath $env:CONFIGPILOT_INSTALLER_PATH;"
        "Write-Output ([string]$s.Status);"
        "Write-Output ([string]$s.SignerCertificate.Subject)"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=spec.verification_timeout_seconds,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines or lines[0] != "Valid":
        raise RuntimeError("Claude Desktop 安装包的 Authenticode 签名无效")
    subject = " ".join(lines[1:])
    if not spec.windows_publisher or spec.windows_publisher.lower() not in subject.lower():
        raise RuntimeError("Claude Desktop 安装包发布者不是 Anthropic")


def _verify_macos_dmg(spec: InstallSpec, path: Path) -> None:
    commands = (
        ["hdiutil", "verify", str(path)],
        [
            "spctl", "--assess", "--type", "open",
            "--context", "context:primary-signature", "--verbose=2", str(path),
        ],
    )
    for command in commands:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=spec.verification_timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError(f"macOS 安装包校验失败: {Path(command[0]).name}")


def verify_download(spec: InstallSpec, path: Path) -> None:
    if spec.kind.endswith("script"):
        _verify_script(spec, path)
    elif spec.kind == "windows-exe":
        _verify_windows_signature(spec, path)
    elif spec.kind == "macos-dmg":
        _verify_macos_dmg(spec, path)
