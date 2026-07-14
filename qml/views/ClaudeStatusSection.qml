import QtQuick
import QtQuick.Layouts
import PrismQML as Fluent

Fluent.Card {
    id: root

    property bool installed: false
    property bool developerModeEnabled: false
    property bool thirdPartyEnabled: false
    property string profileName: ""
    property string configPath: ""

    autoHeight: true

    Column {
        id: cardColumn
        width: parent ? parent.width : 0
        leftPadding: Fluent.Enums.spacing.xl
        rightPadding: Fluent.Enums.spacing.xl
        topPadding: Fluent.Enums.spacing.xl
        bottomPadding: Fluent.Enums.spacing.xl
        spacing: Fluent.Enums.spacing.l

        readonly property real innerWidth: Math.max(
            0, width - leftPadding - rightPadding
        )

        RowLayout {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.m

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Fluent.Enums.spacing.xxs

                Text {
                    text: "安装与模式"
                    color: Fluent.Enums.textColor.primary
                    font.pixelSize: Fluent.Enums.typography.subtitle
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Text {
                    Layout.fillWidth: true
                    text: "直接使用 Claude Desktop 自己的本地配置库，不修改程序文件"
                    color: Fluent.Enums.textColor.tertiary
                    font.pixelSize: Fluent.Enums.typography.caption
                    font.family: Fluent.Enums.fontFamily
                    wrapMode: Text.WordWrap
                }
            }

            Fluent.Badge {
                text: root.installed ? "已安装" : "未检测到安装"
                level: root.installed
                       ? Fluent.Enums.statusLevel.success
                       : Fluent.Enums.statusLevel.warning
            }
        }

        GridLayout {
            width: cardColumn.innerWidth
            columns: width < 620 ? 1 : 2
            columnSpacing: Fluent.Enums.spacing.l
            rowSpacing: Fluent.Enums.spacing.m

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "Developer Mode"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.developerModeEnabled ? "已启用" : "等待启用"
                    level: root.developerModeEnabled
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.attention
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Fluent.Enums.spacing.xs

                Text {
                    text: "Third-Party Inference"
                    color: Fluent.Enums.textColor.secondary
                    font.pixelSize: Fluent.Enums.typography.body
                    font.bold: true
                    font.family: Fluent.Enums.fontFamily
                }
                Fluent.Badge {
                    text: root.thirdPartyEnabled ? "Gateway 已应用" : "等待配置"
                    level: root.thirdPartyEnabled
                           ? Fluent.Enums.statusLevel.success
                           : Fluent.Enums.statusLevel.attention
                }
            }
        }

        Fluent.Separator {
            width: cardColumn.innerWidth
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.xxs

            Text {
                text: root.profileName.length > 0
                      ? "当前配置：" + root.profileName
                      : "当前配置：尚未创建"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.family: Fluent.Enums.fontFamily
            }
            Text {
                width: parent.width
                text: root.configPath
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WrapAnywhere
            }
        }
    }
}
