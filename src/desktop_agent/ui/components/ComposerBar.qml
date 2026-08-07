import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    signal sendRequested(string text)
    signal stopRequested()
    signal modelSelected(string value)
    signal thinkingSelected(string value)
    signal executionModeSelected(string value)
    signal fullAccessChangedByUser(bool enabled)
    property bool running: false
    property var modelChoices: []
    property string selectedModel: ""
    property string thinkingStrength: "medium"
    property string executionMode: "local"
    property bool fullAccess: false

    implicitHeight: 154
    color: "#ffffff"
    border.color: "#dfe3e6"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                id: editor
                objectName: "messageInput"
                placeholderText: qsTr("输入消息…")
                wrapMode: TextArea.Wrap
                background: null
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ComboBox {
                objectName: "modelSelector"
                Layout.preferredWidth: 180
                model: root.modelChoices
                textRole: "display"
                valueRole: "value"
                currentIndex: {
                    for (let index = 0; index < count; index++) {
                        if (valueAt(index) === root.selectedModel)
                            return index
                    }
                    return 0
                }
                onActivated: root.modelSelected(currentValue)
            }

            ComboBox {
                objectName: "thinkingSelector"
                Layout.preferredWidth: 108
                model: [qsTr("低思考"), qsTr("中思考"), qsTr("高思考")]
                currentIndex: root.thinkingStrength === "low" ? 0 : root.thinkingStrength === "high" ? 2 : 1
                onActivated: root.thinkingSelected(["low", "medium", "high"][currentIndex])
            }

            ComboBox {
                objectName: "executionModeSelector"
                Layout.preferredWidth: 104
                model: ["none", "local"]
                currentIndex: root.executionMode === "none" ? 0 : 1
                onActivated: root.executionModeSelected(currentText)
            }

            CheckBox {
                objectName: "fullAccessToggle"
                text: qsTr("完全访问")
                checked: root.fullAccess
                ToolTip.visible: hovered
                ToolTip.text: qsTr("仅对当前会话有效")
                onClicked: root.fullAccessChangedByUser(checked)
            }

            Item { Layout.fillWidth: true }

            ToolButton {
                objectName: "stopButton"
                text: "■"
                visible: root.running
                ToolTip.visible: hovered
                ToolTip.text: qsTr("停止")
                onClicked: root.stopRequested()
            }

            ToolButton {
                objectName: "sendButton"
                text: "➤"
                enabled: !root.running && root.selectedModel.length > 0 && editor.text.trim().length > 0
                ToolTip.visible: hovered
                ToolTip.text: qsTr("发送")
                onClicked: {
                    root.sendRequested(editor.text)
                    editor.clear()
                }
            }
        }
    }
}
