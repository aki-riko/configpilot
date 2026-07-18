// ConfigPilot 主窗口
import QtQuick

import PrismQML as Fluent

QtObject {
    id: root

    readonly property int windowWidth: 980
    readonly property int windowHeight: 640
    readonly property string windowTitle: "ConfigPilot"

    function iconPath(name) {
        return (typeof FluentIconsDir !== "undefined" ? FluentIconsDir : "") + name + ".svg"
    }

    function resourceIconPath(name) {
        return Qt.resolvedUrl("../resources/" + name + ".svg")
    }

    property var navItems: [
        { "text": "Codex", "icon": resourceIconPath("chatgpt") },
        { "text": "Claude", "icon": resourceIconPath("claude") }
    ]

    property var bottomNavItems: [
        { "text": "帮助", "icon": iconPath("Info"), "key": "AboutView" }
    ]

    property var pagePaths: [
        Qt.resolvedUrl("views/CodexView.qml"),
        Qt.resolvedUrl("views/ClaudeDesktopView.qml"),
        Qt.resolvedUrl("views/AboutView.qml")
    ]

    property var windowInstance: null

    Component.onCompleted: {
        Fluent.Translator.setLanguage(Fluent.Enums.lang.zh_CN)
        windowInstance = windowComponent.createObject(null)
        if (windowInstance) {
            windowInstance.show()
        }
    }
    Component.onDestruction: { if (windowInstance) windowInstance.destroy() }

    property Component windowComponent: Component {
        Fluent.Windows {
            id: appWindow
            width: root.windowWidth; height: root.windowHeight
            minimumWidth: 760
            minimumHeight: 560
            windowTitle: root.windowTitle
            windowIcon: typeof AppLogo !== "undefined" ? AppLogo : ""
            windowIconColored: true
            navigationItems: root.navItems
            bottomNavigationItems: root.bottomNavItems
            pageSources: root.pagePaths
            lazyLoading: true
            property string updateDownloadUrl: ""
            property string updateReleaseUrl: ""
            readonly property bool canDownloadInstaller:
                AppUpdater.isWindows && updateDownloadUrl !== ""

            function showUpdateError(message) {
                Fluent.NotificationManager.toast.error(
                    appWindow, "更新失败", message
                )
            }

            // 启动屏:挂到 _splashInstance,内容加载完成后引擎自动 finish()
            Component.onCompleted: {
                this._splashInstance = root.splashComponent.createObject(this.contentItem)
                if (AppUpdater.autoCheckEnabled) {
                    updateCheckTimer.start()
                }
            }

            Item {
                id: updateLayer
                anchors.fill: parent
                z: 10000

                Timer {
                    id: updateCheckTimer
                    interval: AppUpdater.startupDelayMs
                    repeat: false
                    onTriggered: AppUpdater.checkAutomatically()
                }

                Fluent.UpdateDialog {
                    id: updateDialog
                    overlayTarget: appWindow.contentItem
                    currentVersion: AppUpdater.currentVersion
                    confirmText: appWindow.canDownloadInstaller
                        ? "下载并自动安装" : "打开下载页面"
                    cancelText: "稍后"
                    onConfirmed: {
                        if (appWindow.canDownloadInstaller) {
                            downloadDialog.progress = -1
                            downloadDialog.content = "正在连接下载服务器..."
                            downloadDialog.open()
                            AppUpdater.downloadUpdate(appWindow.updateDownloadUrl)
                        } else if (!AppUpdater.openReleasePage(appWindow.updateReleaseUrl)) {
                            appWindow.showUpdateError("无法打开官方发布页面")
                        }
                    }
                }

                Fluent.ProgressDialog {
                    id: downloadDialog
                    overlayTarget: appWindow.contentItem
                    title: "正在更新 ConfigPilot"
                    content: "正在准备下载..."
                    maxWaitingTime: -1
                }

                Connections {
                    target: AppUpdater

                    function onUpdateAvailable(version, notes, downloadUrl, htmlUrl) {
                        appWindow.updateDownloadUrl = downloadUrl
                        appWindow.updateReleaseUrl = htmlUrl
                        updateDialog.version = version
                        updateDialog.notes = notes
                        updateDialog.open()
                    }

                    function onUpToDate(version, manual) {
                        if (manual) {
                            Fluent.NotificationManager.toast.success(
                                appWindow, "已是最新版本", version
                            )
                        }
                    }

                    function onCheckFailed(message, manual) {
                        if (manual) {
                            appWindow.showUpdateError(message)
                        }
                    }

                    function onDownloadProgress(received, total) {
                        if (total > 0) {
                            downloadDialog.progress = Math.min(100, received * 100 / total)
                            downloadDialog.content = "已下载 "
                                + Math.round(downloadDialog.progress) + "%"
                        } else {
                            downloadDialog.progress = -1
                            downloadDialog.content = "正在下载更新包..."
                        }
                    }

                    function onDownloadReady() {
                        downloadDialog.progress = 100
                        downloadDialog.content = "下载完成，正在启动安装程序..."
                    }

                    function onDownloadFailed(message) {
                        downloadDialog.close()
                        appWindow.showUpdateError(message)
                    }

                    function onInstallLaunchFailed(message) {
                        downloadDialog.close()
                        appWindow.showUpdateError(message)
                    }
                }
            }
        }
    }

    // 启动屏组件
    property Component splashComponent: Component {
        Fluent.SplashScreen {
            iconSource: typeof AppLogo !== "undefined" ? AppLogo : ""
            title: root.windowTitle
            subtitle: "正在加载..."
            z: 9999
        }
    }
}
