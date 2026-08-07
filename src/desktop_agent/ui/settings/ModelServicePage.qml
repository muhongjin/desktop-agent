import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var preset: modelService.providerPresets[providerSelector.currentIndex]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        Label {
            text: qsTr("模型服务")
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }

        Label { text: qsTr("服务商") }
        ComboBox {
            id: providerSelector
            objectName: "providerSelector"
            Layout.fillWidth: true
            model: modelService.providerPresets
            textRole: "displayName"
            onActivated: {
                baseUrl.text = root.preset.baseUrl
                modelId.placeholderText = root.preset.modelHints.join(", ")
                status.text = ""
            }
        }

        Label { text: qsTr("Base URL") }
        TextField {
            id: baseUrl
            objectName: "baseUrlInput"
            Layout.fillWidth: true
            text: root.preset ? root.preset.baseUrl : ""
        }

        Label { text: qsTr("API Key") }
        TextField {
            id: apiKey
            objectName: "apiKeyInput"
            Layout.fillWidth: true
            echoMode: TextInput.Password
            placeholderText: qsTr("留空则保留已保存的密钥")
        }

        Label { text: qsTr("模型 ID") }
        TextField {
            id: modelId
            objectName: "manualModelInput"
            Layout.fillWidth: true
            placeholderText: root.preset ? root.preset.modelHints.join(", ") : ""
        }

        RowLayout {
            Button {
                objectName: "discoverModelsButton"
                text: qsTr("发现模型")
                onClicked: modelService.discoverModels(root.preset.id, baseUrl.text, apiKey.text)
            }

            Button {
                objectName: "saveProviderButton"
                text: qsTr("保存")
                enabled: modelId.text.trim().length > 0
                onClicked: {
                    modelService.saveProvider(root.preset.id, baseUrl.text, apiKey.text, modelId.text)
                    apiKey.clear()
                    status.text = qsTr("已保存")
                }
            }

            Label {
                id: status
                color: "#4b555e"
                Layout.fillWidth: true
            }
        }

        Item { Layout.fillHeight: true }
    }

    Connections {
        target: modelService

        function onModelsDiscovered(providerId, models) {
            if (providerId !== root.preset.id)
                return
            if (models.length > 0)
                modelId.text = models[0]
            status.text = qsTr("发现 %1 个模型").arg(models.length)
        }

        function onDiscoveryFailed(providerId, message) {
            if (providerId === root.preset.id)
                status.text = qsTr("发现失败，请手动输入模型 ID")
        }
    }
}
