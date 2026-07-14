import QtQuick
import PrismQML as Fluent

Fluent.Card {
    id: root

    property string modelsValue: ""
    property string headersValue: ""
    property int headerCount: 0
    property bool clearHeadersValue: false

    signal modelsEdited(string value)
    signal headersEdited(string value)
    signal clearHeadersToggled(bool value)

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

        Text {
            text: "模型与额外 Header"
            color: Fluent.Enums.textColor.primary
            font.pixelSize: Fluent.Enums.typography.subtitle
            font.bold: true
            font.family: Fluent.Enums.fontFamily
        }
        Text {
            width: cardColumn.innerWidth
            text: "模型留空时由 Gateway 的 /v1/models 自动发现；Header 留空默认保留现有值"
            color: Fluent.Enums.textColor.tertiary
            font.pixelSize: Fluent.Enums.typography.caption
            font.family: Fluent.Enums.fontFamily
            wrapMode: Text.WordWrap
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.xs

            Text {
                text: "Model list · 每行一个，第一个作为默认模型"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Fluent.TextEdit {
                id: modelsEdit
                objectName: "claudeModelsEdit"
                width: parent.width
                height: 112
                placeholderText: "claude-sonnet-4-6\nclaude-opus-4-6"
                Component.onCompleted: Qt.callLater(function() {
                    text = root.modelsValue
                })
                onTextEdited: {
                    if (text !== root.modelsValue) root.modelsEdited(text)
                }
                Connections {
                    target: root
                    function onModelsValueChanged() {
                        if (modelsEdit.text !== root.modelsValue) {
                            modelsEdit.text = root.modelsValue
                        }
                    }
                }
            }
        }

        Fluent.Separator {
            width: cardColumn.innerWidth
        }

        Column {
            width: cardColumn.innerWidth
            spacing: Fluent.Enums.spacing.xs

            Text {
                text: root.headerCount > 0
                      ? "额外 Header · 已保存 " + root.headerCount + " 项"
                      : "额外 Header · 可选"
                color: Fluent.Enums.textColor.secondary
                font.pixelSize: Fluent.Enums.typography.body
                font.bold: true
                font.family: Fluent.Enums.fontFamily
            }
            Text {
                width: parent.width
                text: "输入 JSON 对象会覆盖现有 Header；其中可能包含敏感信息，界面不会回显已保存的值"
                color: Fluent.Enums.textColor.tertiary
                font.pixelSize: Fluent.Enums.typography.caption
                font.family: Fluent.Enums.fontFamily
                wrapMode: Text.WordWrap
            }
            Fluent.TextEdit {
                id: headersEdit
                objectName: "claudeHeadersEdit"
                width: parent.width
                height: 112
                enabled: !root.clearHeadersValue
                placeholderText: "{\n  \"X-Tenant\": \"tenant-id\"\n}"
                Component.onCompleted: Qt.callLater(function() {
                    text = root.headersValue
                })
                onTextEdited: {
                    if (text !== root.headersValue) root.headersEdited(text)
                }
                Connections {
                    target: root
                    function onHeadersValueChanged() {
                        if (headersEdit.text !== root.headersValue) {
                            headersEdit.text = root.headersValue
                        }
                    }
                }
            }
        }

        Fluent.Toggle {
            id: clearHeadersToggle
            width: cardColumn.innerWidth
            enabled: root.headerCount > 0
            controlType: Fluent.Enums.toggle.control_switch
            type: Fluent.Enums.toggle.type_subtitle
            text: "移除已保存的额外 Header"
            subtitle: "关闭时，编辑框留空会保留现有 Header"
            Component.onCompleted: Qt.callLater(function() {
                checked = root.clearHeadersValue
            })
            onToggled: function(checkedValue) {
                root.clearHeadersToggled(checkedValue)
            }
            Connections {
                target: root
                function onClearHeadersValueChanged() {
                    if (clearHeadersToggle.checked !== root.clearHeadersValue) {
                        clearHeadersToggle.checked = root.clearHeadersValue
                    }
                }
            }
        }
    }
}
