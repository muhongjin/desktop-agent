import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    id: root
    objectName: "systemPromptPage"
    property string statusMessage: ""

    function savePrompt() {
        settingsService.saveSystemPrompt(promptEditor.text)
        root.statusMessage = qsTr("系统提示词已保存。")
    }

    Shortcut {
        sequence: "Ctrl+S"
        enabled: root.visible
        onActivated: root.savePrompt()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: UI.Theme.space32
        anchors.rightMargin: UI.Theme.space32
        anchors.topMargin: UI.Theme.space32
        anchors.bottomMargin: UI.Theme.space24
        spacing: UI.Theme.space16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: UI.Theme.space4
            Label {
                text: qsTr("系统提示词")
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontTitle
                font.weight: Font.DemiBold
            }
            Label {
                text: qsTr("定义 Agent 的默认角色与工作方式。修改仅影响后续发出的请求。")
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

        Label {
            text: qsTr("提示词内容")
            color: UI.Theme.textPrimary
            font.family: UI.Theme.fontFamily
            font.pixelSize: UI.Theme.fontBody
            font.weight: Font.DemiBold
        }

        TextArea {
            id: promptEditor
            objectName: "systemPromptEditor"
            text: settingsService.systemPrompt
            wrapMode: TextArea.Wrap
            selectByMouse: true
            persistentSelection: true
            leftPadding: UI.Theme.space12
            rightPadding: UI.Theme.space12
            topPadding: UI.Theme.space12
            bottomPadding: UI.Theme.space12
            color: UI.Theme.textPrimary
            selectionColor: UI.Theme.accent
            selectedTextColor: "#ffffff"
            font.family: UI.Theme.fontFamily
            font.pixelSize: UI.Theme.fontBody
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 220
            background: Rectangle {
                color: UI.Theme.surface
                radius: UI.Theme.radiusMedium
                border.width: promptEditor.activeFocus ? UI.Theme.focusWidth : 1
                border.color: promptEditor.activeFocus ? UI.Theme.focus : UI.Theme.borderStrong
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: UI.Theme.space8
            Label {
                text: root.statusMessage.length > 0 ? qsTr("完成：") + root.statusMessage : qsTr("Ctrl+S 保存")
                color: root.statusMessage.length > 0 ? UI.Theme.success : UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            SettingsButton {
                text: qsTr("恢复默认")
                onClicked: {
                    settingsService.resetSystemPrompt()
                    promptEditor.text = settingsService.systemPrompt
                    root.statusMessage = qsTr("默认提示词已恢复并保存。")
                }
            }
            SettingsButton {
                text: qsTr("保存")
                primary: true
                onClicked: root.savePrompt()
            }
        }
    }
}
