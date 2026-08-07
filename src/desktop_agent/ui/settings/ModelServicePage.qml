import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    id: root
    objectName: "modelServicePage"
    property var preset: modelService.providerPresets[providerSelector.currentIndex]
    property bool discovering: false
    property string discoveringProviderId: ""
    property string statusKind: ""
    property string statusMessage: ""

    function saveProvider() {
        if (!root.preset || modelId.text.trim().length === 0)
            return
        modelService.saveProvider(root.preset.id, baseUrl.text, apiKey.text, modelId.text)
        apiKey.clear()
        root.statusKind = "success"
        root.statusMessage = qsTr("配置已保存，新会话可以选择这个模型。")
    }

    Shortcut {
        sequence: "Ctrl+S"
        enabled: root.visible && modelId.text.trim().length > 0
        onActivated: root.saveProvider()
    }

    ScrollView {
        id: pageScroll
        anchors.fill: parent
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            x: Math.max(UI.Theme.space32, (pageScroll.availableWidth - width) / 2)
            width: Math.max(360, Math.min(UI.Theme.contentMaxWidth, pageScroll.availableWidth - UI.Theme.space32 * 2))
            spacing: UI.Theme.space20

            Item { Layout.preferredHeight: UI.Theme.space12 }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space4
                Label {
                    text: qsTr("模型服务")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontTitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("配置 OpenAI-compatible API。密钥仅保存在 Windows 凭据管理器中。")
                    color: UI.Theme.textSecondary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("服务商")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    font.weight: Font.DemiBold
                }
                SettingsComboBox {
                    id: providerSelector
                    objectName: "providerSelector"
                    Layout.fillWidth: true
                    enabled: !root.discovering
                    model: modelService.providerPresets
                    textRole: "displayName"
                    onActivated: {
                        baseUrl.text = root.preset.baseUrl
                        modelId.placeholderText = root.preset.modelHints.join(", ")
                        root.statusKind = ""
                        root.statusMessage = ""
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("Base URL")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    font.weight: Font.DemiBold
                }
                SettingsTextField {
                    id: baseUrl
                    objectName: "baseUrlInput"
                    Layout.fillWidth: true
                    text: root.preset ? root.preset.baseUrl : ""
                    placeholderText: qsTr("https://example.com/v1")
                    inputMethodHints: Qt.ImhUrlCharactersOnly
                }
                Label {
                    text: qsTr("填写兼容 OpenAI API 的根地址。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("API Key")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    font.weight: Font.DemiBold
                }
                SettingsTextField {
                    id: apiKey
                    objectName: "apiKeyInput"
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    placeholderText: qsTr("留空则保留已保存的密钥")
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("模型 ID")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    font.weight: Font.DemiBold
                }
                SettingsTextField {
                    id: modelId
                    objectName: "manualModelInput"
                    Layout.fillWidth: true
                    placeholderText: root.preset ? root.preset.modelHints.join(", ") : ""
                }
                Label {
                    text: qsTr("可以手动输入，也可以让应用从服务商读取模型列表。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Rectangle {
                objectName: "modelDiscoveryStatus"
                visible: root.statusMessage.length > 0
                Layout.fillWidth: true
                Layout.preferredHeight: statusRow.implicitHeight + UI.Theme.space16
                radius: UI.Theme.radiusMedium
                color: root.statusKind === "error" ? UI.Theme.dangerSubtle
                     : root.statusKind === "success" ? UI.Theme.successSubtle
                     : UI.Theme.accentSubtle

                RowLayout {
                    id: statusRow
                    anchors.fill: parent
                    anchors.margins: UI.Theme.space8
                    spacing: UI.Theme.space8
                    BusyIndicator {
                        visible: root.discovering
                        running: root.discovering
                        implicitWidth: 20
                        implicitHeight: 20
                    }
                    Label {
                        text: (root.statusKind === "error" ? qsTr("失败：")
                              : root.statusKind === "success" ? qsTr("完成：") : "") + root.statusMessage
                        color: root.statusKind === "error" ? UI.Theme.danger
                             : root.statusKind === "success" ? UI.Theme.success
                             : UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                SettingsButton {
                    objectName: "discoverModelsButton"
                    text: root.discovering ? qsTr("正在发现…") : qsTr("发现模型")
                    enabled: !root.discovering && root.preset !== undefined
                    onClicked: {
                        root.discovering = true
                        root.discoveringProviderId = root.preset.id
                        root.statusKind = "busy"
                        root.statusMessage = qsTr("正在连接服务商并读取模型列表。")
                        modelService.discoverModels(root.preset.id, baseUrl.text, apiKey.text)
                    }
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: qsTr("Ctrl+S 保存")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                }
                SettingsButton {
                    objectName: "saveProviderButton"
                    text: qsTr("保存配置")
                    primary: true
                    enabled: modelId.text.trim().length > 0
                    onClicked: root.saveProvider()
                }
            }

            Item { Layout.preferredHeight: UI.Theme.space24 }
        }
    }

    Connections {
        target: modelService

        function onModelsDiscovered(providerId, models) {
            if (providerId !== root.discoveringProviderId)
                return
            root.discovering = false
            root.discoveringProviderId = ""
            if (!root.preset || providerId !== root.preset.id)
                return
            if (models.length > 0) {
                modelId.text = models[0]
                root.statusKind = "success"
                root.statusMessage = qsTr("发现 %1 个模型，已填入第一个模型 ID。").arg(models.length)
            } else {
                root.statusKind = "error"
                root.statusMessage = qsTr("服务商没有返回模型，请手动输入模型 ID。")
            }
        }

        function onDiscoveryFailed(providerId, message) {
            if (providerId !== root.discoveringProviderId)
                return
            root.discovering = false
            root.discoveringProviderId = ""
            if (!root.preset || providerId !== root.preset.id)
                return
            root.statusKind = "error"
            root.statusMessage = qsTr("无法读取模型列表，请检查 Base URL、API Key 或网络后重试，也可以手动输入模型 ID。")
        }
    }
}
