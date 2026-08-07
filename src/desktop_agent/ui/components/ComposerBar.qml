import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    signal sendRequested(string text)
    signal stopRequested()
    property bool running: false

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
                model: [qsTr("请先配置模型")]
            }

            ComboBox {
                objectName: "thinkingSelector"
                Layout.preferredWidth: 108
                model: [qsTr("低思考"), qsTr("中思考"), qsTr("高思考")]
                currentIndex: 1
            }

            ComboBox {
                objectName: "executionModeSelector"
                Layout.preferredWidth: 104
                model: ["none", "local"]
                currentIndex: 1
            }

            CheckBox {
                objectName: "fullAccessToggle"
                text: qsTr("完全访问")
                ToolTip.visible: hovered
                ToolTip.text: qsTr("仅对当前会话有效")
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
                enabled: !root.running && editor.text.trim().length > 0
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
