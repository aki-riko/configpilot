# coding: utf-8
"""ConfigPilot 对 PrismQML Updater 的应用层协调。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import sys
from typing import Callable, Optional

from PySide6.QtCore import QCoreApplication, QObject, Property, Signal, Slot

from .app_settings import AppSettings
from .async_tasks import SerialTaskRunner
from .background_updater import BackgroundDownloadUpdater
from .system_launcher import is_http_url, open_external_target


LOGGER = logging.getLogger(__name__)
_SHELL_EXECUTE_ERRORS = (
    OSError,
    AttributeError,
    ctypes.ArgumentError,
    TypeError,
    ValueError,
)


def _launch_windows_update_installer(installer_path: str, silent_args: str) -> bool:
    """在后台线程通过 Windows Shell 启动带 manifest 的安装器。"""
    if sys.platform != "win32" or not installer_path or not os.path.isfile(installer_path):
        return False
    try:
        shell_execute = ctypes.windll.shell32.ShellExecuteW
        shell_execute.argtypes = [
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.c_int,
        ]
        shell_execute.restype = wintypes.HINSTANCE
        arguments = " ".join(part for part in silent_args.split(" ") if part) or None
        result = int(
            shell_execute(None, "open", installer_path, arguments, None, 1) or 0
        )
    except _SHELL_EXECUTE_ERRORS:
        LOGGER.exception("启动更新安装程序异常: %s", installer_path)
        return False
    return result > 32


class AppUpdater(QObject):
    """保留引擎更新能力，并补充自动/手动检查状态与应用配置。"""

    updateAvailable = Signal(str, str, str, str)
    upToDate = Signal(str, bool)
    checkFailed = Signal(str, bool)
    checkingChanged = Signal()
    downloadProgress = Signal(int, int)
    downloadReady = Signal()
    downloadFailed = Signal(str)
    installLaunchFailed = Signal(str)
    releasePageOpenFailed = Signal(str)

    def __init__(
        self,
        settings: AppSettings,
        prismqml_version: str,
        parent: Optional[QObject] = None,
        updater_factory: Callable = BackgroundDownloadUpdater,
        installer_launcher: Optional[Callable[[str, str], bool]] = None,
        external_opener: Optional[Callable[[str], bool]] = None,
        quit_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._settings = settings
        self._prismqml_version = prismqml_version
        self._checking = False
        self._manual_check = False
        self._installer_launcher = installer_launcher or _launch_windows_update_installer
        self._external_opener = external_opener or open_external_target
        self._quit_callback = quit_callback or QCoreApplication.quit
        self._installer_tasks = SerialTaskRunner(
            self,
            thread_name="ConfigPilotUpdateLauncher",
        )
        updates = settings.updates
        self._updater = updater_factory(
            updates.repository,
            f"v{settings.version}",
            updates.asset_keyword,
            parent=self,
        )
        self._connect_engine_signals()

    def _connect_engine_signals(self) -> None:
        self._updater.updateAvailable.connect(self._on_update_available)
        self._updater.upToDate.connect(self._on_up_to_date)
        self._updater.checkFailed.connect(self._on_check_failed)
        self._updater.downloadProgress.connect(self.downloadProgress.emit)
        self._updater.downloadFinished.connect(self._on_download_finished)
        self._updater.downloadFailed.connect(self.downloadFailed.emit)

    @Property(str, constant=True)
    def version(self) -> str:
        return self._settings.version

    @Property(str, constant=True)
    def currentVersion(self) -> str:  # noqa: N802 - QML 公开属性
        return f"v{self._settings.version}"

    @Property(str, constant=True)
    def prismqmlVersion(self) -> str:  # noqa: N802 - QML 公开属性
        return self._prismqml_version

    @Property(bool, constant=True)
    def autoCheckEnabled(self) -> bool:  # noqa: N802 - QML 公开属性
        return self._settings.updates.auto_check

    @Property(int, constant=True)
    def startupDelayMs(self) -> int:  # noqa: N802 - QML 公开属性
        return self._settings.updates.startup_delay_ms

    @Property(bool, constant=True)
    def isWindows(self) -> bool:  # noqa: N802 - QML 公开属性
        return sys.platform == "win32"

    @Property(bool, notify=checkingChanged)
    def checking(self) -> bool:
        return self._checking

    def _set_checking(self, value: bool) -> None:
        if self._checking == value:
            return
        self._checking = value
        self.checkingChanged.emit()

    def _start_check(self, manual: bool) -> None:
        if self._checking:
            self._manual_check = self._manual_check or manual
            return
        self._manual_check = manual
        self._set_checking(True)
        self._updater.checkForUpdate()

    def _finish_check(self) -> bool:
        manual = self._manual_check
        self._manual_check = False
        self._set_checking(False)
        return manual

    @Slot()
    def checkAutomatically(self) -> None:  # noqa: N802 - QML 公开槽
        if self._settings.updates.auto_check:
            self._start_check(False)

    @Slot()
    def checkManually(self) -> None:  # noqa: N802 - QML 公开槽
        self._start_check(True)

    @Slot(str)
    def downloadUpdate(self, url: str) -> None:  # noqa: N802 - QML 公开槽
        self._updater.downloadUpdate(url)

    @Slot(str, result=bool)
    def openReleasePage(self, url: str) -> bool:  # noqa: N802 - QML 公开槽
        if not is_http_url(url):
            return False
        try:
            self._installer_tasks.submit(
                lambda: self._external_opener(url),
                self._on_release_page_opened,
                self._on_release_page_open_error,
            )
        except RuntimeError:
            return False
        return True

    def _on_release_page_opened(self, opened: object) -> None:
        if not bool(opened):
            self.releasePageOpenFailed.emit("无法打开官方发布页面")

    def _on_release_page_open_error(self, exc: Exception) -> None:
        LOGGER.exception(
            "打开官方发布页面失败",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        self.releasePageOpenFailed.emit("无法打开官方发布页面")

    def _on_update_available(
        self, version: str, notes: str, download_url: str, html_url: str
    ) -> None:
        self._finish_check()
        self.updateAvailable.emit(version, notes, download_url, html_url)

    def _on_up_to_date(self, version: str) -> None:
        self.upToDate.emit(version, self._finish_check())

    def _on_check_failed(self, message: str) -> None:
        self.checkFailed.emit(message, self._finish_check())

    def _on_download_finished(self, installer_path: str) -> None:
        self.downloadReady.emit()
        self._installer_tasks.submit(
            lambda: self._installer_launcher(
                installer_path,
                self._settings.updates.windows_installer_args,
            ),
            self._on_installer_launched,
            self._on_installer_launch_error,
        )

    def _on_installer_launched(self, launched: object) -> None:
        if bool(launched):
            self._quit_callback()
            return
        self.installLaunchFailed.emit("无法启动更新安装程序，请稍后重试")

    def _on_installer_launch_error(self, exc: Exception) -> None:
        LOGGER.exception(
            "启动更新安装程序失败",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        self.installLaunchFailed.emit("无法启动更新安装程序，请稍后重试")
