import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        Label {
            text: qsTr("已归档聊天")
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }

        ListView {
            objectName: "archivedChatsList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            model: archiveService.archivedSessions

            delegate: ItemDelegate {
                required property string sessionId
                required property string title
                width: ListView.view.width
                height: 48

                contentItem: RowLayout {
                    Label {
                        text: title
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Button {
                        text: qsTr("恢复")
                        onClicked: archiveService.restore(sessionId)
                    }
                    Button {
                        text: qsTr("删除")
                        onClicked: archiveService.deletePermanently(sessionId)
                    }
                }
            }
        }
    }
}
