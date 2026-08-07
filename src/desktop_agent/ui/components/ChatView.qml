import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property bool hasSession: false
    property alias model: messageList.model

    ListView {
        id: messageList
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 18
        anchors.bottomMargin: 18
        clip: true
        spacing: 14

        delegate: ColumnLayout {
            required property string role
            required property string content
            required property string details
            width: ListView.view.width
            spacing: 5

            Label {
                text: role === "user" ? qsTr("你") : qsTr("Agent")
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: role === "user" ? "#176b5b" : "#555d66"
            }

            TextEdit {
                visible: role !== "tool"
                text: content
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: "#202428"
                Layout.fillWidth: true
            }

            ToolRunSummary {
                visible: role === "tool"
                summary: content
                details: parent.details
                Layout.fillWidth: true
            }
        }

        ScrollBar.vertical: ScrollBar {}
    }

    Column {
        anchors.centerIn: parent
        spacing: 8
        visible: messageList.count === 0

        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.hasSession ? qsTr("开始一段对话") : qsTr("创建对话后即可开始")
            font.pixelSize: 19
            font.weight: Font.DemiBold
            color: "#383e44"
        }

        Label {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.hasSession ? qsTr("工作区已为当前会话准备好") : qsTr("每个会话都有独立工作区")
            color: "#747c84"
        }
    }
}
