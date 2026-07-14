import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property bool installed: false
    property bool developerModeEnabled: false
    property bool thirdPartyEnabled: false
    property bool gatewayCanEnable: false
    property string profileName: ""
    property string configPath: ""
    readonly property var installOptions: [
        { "text": "安装 Claude Code CLI", "id": "claude-code" },
        { "text": "安装 Claude Desktop", "id": "claude-desktop" }
    ]

    signal developerModeToggled(bool value)
    signal gatewayToggled(bool value)
    signal installRequested(string product)

    autoHeight: true

    Column {
        id: cardColumn
        width: parent ? parent.width : 0
        leftPadding: Fluent.Enums.spacing.l
        rightPadding: Fluent.Enums.spacing.l
        topPadding: Fluent.Enums.spacing.m
        bottomPadding: Fluent.Enums.spacing.m

        readonly property real innerWidth: Math.max(
            0, width - leftPadding - rightPadding
        )

        GridLayout {
            width: cardColumn.innerWidth
            columns: width < 700 ? 2 : 4
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.m

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Claude Desktop"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.installed ? "已安装" : "未检测到安装"
                    visible: root.installed
                    level: root.installed
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.warning
                }
                Fluent.Button {
                    objectName: "claudeInstallDropdown"
                    visible: !root.installed
                    style: Fluent.Enums.button.style_default
                    feature: Fluent.Enums.button.feature_dropdown
                    text: "获取 Claude"
                    menuItems: root.installOptions
                    onMenuItemClicked: function(index, text) {
                        if (index >= 0 && index < root.installOptions.length) {
                            root.installRequested(root.installOptions[index].id)
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Developer Mode"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Toggle {
                    id: developerModeToggle
                    objectName: "claudeDeveloperModeToggle"
                    controlType: Fluent.Enums.toggle.control_switch
                    type: Fluent.Enums.toggle.type_default
                    text: root.developerModeEnabled ? "已启用" : "未启用"

                    function syncChecked() {
                        if (checked !== root.developerModeEnabled) {
                            checked = root.developerModeEnabled
                        }
                    }

                    Component.onCompleted: Qt.callLater(syncChecked)
                    onToggled: function(checkedValue) {
                        root.developerModeToggled(checkedValue)
                        Qt.callLater(syncChecked)
                    }
                    Connections {
                        target: root
                        function onDeveloperModeEnabledChanged() {
                            developerModeToggle.syncChecked()
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "Gateway"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Toggle {
                    id: gatewayToggle
                    objectName: "claudeGatewayToggle"
                    enabled: root.thirdPartyEnabled || root.gatewayCanEnable
                    controlType: Fluent.Enums.toggle.control_switch
                    type: Fluent.Enums.toggle.type_default
                    text: root.thirdPartyEnabled ? "已应用" : "未启用"

                    function syncChecked() {
                        if (checked !== root.thirdPartyEnabled) {
                            checked = root.thirdPartyEnabled
                        }
                    }

                    Component.onCompleted: Qt.callLater(syncChecked)
                    onToggled: function(checkedValue) {
                        root.gatewayToggled(checkedValue)
                        Qt.callLater(syncChecked)
                    }
                    Connections {
                        target: root
                        function onThirdPartyEnabledChanged() {
                            gatewayToggle.syncChecked()
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "配置档案"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.profileName.length > 0 ? root.profileName : "未创建"
                    level: root.profileName.length > 0
                           ? Fluent.Enums.statusLevel.info
                           : Fluent.Enums.statusLevel.attention
                }
            }
        }
    }
}
