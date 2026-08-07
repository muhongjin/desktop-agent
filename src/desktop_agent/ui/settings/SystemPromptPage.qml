import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        Label {
            text: qsTr("系统提示词")
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }

        TextArea {
            id: promptEditor
            objectName: "systemPromptEditor"
            text: settingsService.systemPrompt
            wrapMode: TextArea.Wrap
            selectByMouse: true
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        RowLayout {
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("恢复默认")
                onClicked: {
                    settingsService.resetSystemPrompt()
                    promptEditor.text = settingsService.systemPrompt
                }
            }
            Button {
                text: qsTr("保存")
                onClicked: settingsService.saveSystemPrompt(promptEditor.text)
            }
        }
    }
}
