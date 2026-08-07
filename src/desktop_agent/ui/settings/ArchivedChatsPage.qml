import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    id: root
    objectName: "archivedChatsPage"
    property string pendingDeleteId: ""
    property string pendingDeleteTitle: ""
    property string statusMessage: ""

    Dialog {
        id: deleteDialog
        title: qsTr("永久删除聊天？")
        modal: true
        focus: true
        anchors.centerIn: parent
        width: Math.min(460, root.width - UI.Theme.space32 * 2)
        padding: UI.Theme.space24
        closePolicy: Popup.CloseOnEscape
        onOpened: cancelDeleteButton.forceActiveFocus()
        onRejected: {
            root.pendingDeleteId = ""
            root.pendingDeleteTitle = ""
        }

        background: Rectangle {
            color: UI.Theme.surface
            border.color: UI.Theme.border
            radius: UI.Theme.radiusLarge
        }

        header: Label {
            text: deleteDialog.title
            color: UI.Theme.textPrimary
            font.family: UI.Theme.fontFamily
            font.pixelSize: UI.Theme.fontSubtitle
            font.weight: Font.DemiBold
            leftPadding: UI.Theme.space24
            rightPadding: UI.Theme.space24
            topPadding: UI.Theme.space20
            bottomPadding: UI.Theme.space8
        }

        contentItem: ColumnLayout {
            spacing: UI.Theme.space12
            Label {
                text: root.pendingDeleteTitle
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.DemiBold
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Label {
                text: qsTr("聊天记录会被永久删除，无法恢复。自动工作区会一并移入系统回收站。")
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        footer: DialogButtonBox {
            spacing: UI.Theme.space8
            leftPadding: UI.Theme.space24
            rightPadding: UI.Theme.space24
            topPadding: UI.Theme.space8
            bottomPadding: UI.Theme.space20
            background: Item {}

            SettingsButton {
                id: cancelDeleteButton
                text: qsTr("取消")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
            SettingsButton {
                text: qsTr("永久删除")
                destructive: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            onAccepted: {
                archiveService.deletePermanently(root.pendingDeleteId)
                root.statusMessage = qsTr("聊天已永久删除，工作区已移入系统回收站。")
                root.pendingDeleteId = ""
                root.pendingDeleteTitle = ""
                deleteDialog.close()
            }
            onRejected: deleteDialog.reject()
        }
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
                text: qsTr("已归档聊天")
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontTitle
                font.weight: Font.DemiBold
            }
            Label {
                text: qsTr("归档不会删除聊天或工作区。可以恢复聊天，或在这里永久删除。")
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

        Label {
            visible: root.statusMessage.length > 0
            text: qsTr("完成：") + root.statusMessage
            color: UI.Theme.success
            font.family: UI.Theme.fontFamily
            font.pixelSize: UI.Theme.fontBody
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        Item {
            objectName: "archivedChatsEmptyState"
            visible: archivedChatsList.count === 0
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width, 420)
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("暂无已归档聊天")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Label {
                    text: qsTr("从主界面归档的聊天会保留在这里。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }

        ListView {
            id: archivedChatsList
            objectName: "archivedChatsList"
            visible: count > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: UI.Theme.space8
            activeFocusOnTab: true
            keyNavigationEnabled: true
            model: archiveService.archivedSessions
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                required property string sessionId
                required property string title
                width: ListView.view.width
                height: 60
                color: UI.Theme.surface
                border.color: UI.Theme.border
                radius: UI.Theme.radiusMedium

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: UI.Theme.space16
                    anchors.rightMargin: UI.Theme.space8
                    spacing: UI.Theme.space8
                    Label {
                        text: title
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        ToolTip.visible: truncated && titleMouse.containsMouse
                        ToolTip.text: title
                        MouseArea {
                            id: titleMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.NoButton
                        }
                    }
                    SettingsButton {
                        text: qsTr("恢复")
                        onClicked: {
                            archiveService.restore(sessionId)
                            root.statusMessage = qsTr("“%1”已恢复到聊天列表。").arg(title)
                        }
                    }
                    SettingsButton {
                        text: qsTr("删除")
                        destructive: true
                        onClicked: {
                            root.pendingDeleteId = sessionId
                            root.pendingDeleteTitle = title
                            deleteDialog.open()
                        }
                    }
                }
            }
        }
    }
}
