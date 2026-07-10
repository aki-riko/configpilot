// 帮助页
import QtQuick
import PrismQML as Fluent

Item {
    id: root

    Fluent.ScrollArea {
        anchors.fill: parent

        Column {
            width: parent ? parent.width : 0
            spacing: Fluent.Enums.spacing.l
            topPadding: Fluent.Enums.spacing.l
            bottomPadding: Fluent.Enums.spacing.xxxl

            Text {
                text: "帮助"
                font.pixelSize: Fluent.Enums.typography.displayLarge
                font.bold: true
                color: Fluent.Enums.textColor.primary
                font.family: Fluent.Enums.fontFamily
            }

            Fluent.Card {
                width: parent ? parent.width : 0
                autoHeight: true
                Column {
                    width: parent ? parent.width : 0
                    leftPadding: Fluent.Enums.spacing.l
                    rightPadding: Fluent.Enums.spacing.l
                    topPadding: Fluent.Enums.spacing.l
                    bottomPadding: Fluent.Enums.spacing.l
                    spacing: Fluent.Enums.spacing.m
                    Text {
                        text: "ConfigPilot 做什么"
                        font.pixelSize: Fluent.Enums.typography.subtitle
                        font.bold: true
                        color: Fluent.Enums.textColor.primary
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        text: "ConfigPilot 是 AI 工具配置与自动化中心。当前版本管理 Codex 的 config.toml 连接配置,支持切换 API 地址并填写 API key。\n\n• 直接填写 base_url / provider / wire_api / model\n• 通过下拉按钮套用 GPT-5.5 或 GPT-5.6 上下文预设\n• 「应用配置」写入 ~/.codex/config.toml,保留 notify 等其它内容\n• 写入前自动备份 config.toml.bak / auth.json.bak\n• 改完重启 Codex 生效"
                        font.pixelSize: Fluent.Enums.typography.body
                        color: Fluent.Enums.textColor.secondary
                        font.family: Fluent.Enums.fontFamily
                        wrapMode: Text.WordWrap
                        width: parent ? parent.width - Fluent.Enums.spacing.l * 2 : 0
                    }
                }
            }

            Fluent.Card {
                width: parent ? parent.width : 0
                autoHeight: true
                Column {
                    width: parent ? parent.width : 0
                    leftPadding: Fluent.Enums.spacing.l
                    rightPadding: Fluent.Enums.spacing.l
                    topPadding: Fluent.Enums.spacing.l
                    bottomPadding: Fluent.Enums.spacing.l
                    spacing: Fluent.Enums.spacing.s
                    Text {
                        text: "ConfigPilot"
                        font.pixelSize: Fluent.Enums.typography.subtitle
                        font.bold: true
                        color: Fluent.Enums.textColor.primary
                        font.family: Fluent.Enums.fontFamily
                    }
                    Text {
                        text: "AI 工具配置与自动化中心\n基于 PrismQML (prismqml 0.2.22) · MIT"
                        font.pixelSize: Fluent.Enums.typography.body
                        color: Fluent.Enums.textColor.secondary
                        font.family: Fluent.Enums.fontFamily
                    }
                }
            }
        }
    }
}
