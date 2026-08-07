import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "components"

ApplicationWindow {
    id: window
    objectName: "mainWindow"
    width: 1240
    height: 800
    minimumWidth: 920
    minimumHeight: 620
    visible: true
    title: qsTr("Desktop Agent")
    color: "#f6f7f8"

    font.family: "Segoe UI"
    font.pixelSize: 14

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 272
            Layout.fillHeight: true
            color: "#eef0f2"
            border.color: "#d9dde1"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40

                    Label {
                        text: qsTr("Desktop Agent")
                        font.pixelSize: 17
                        font.weight: Font.DemiBold
                        color: "#202428"
                        Layout.fillWidth: true
                    }

                    ToolButton {
                        objectName: "settingsButton"
                        text: "⚙"
                        font.pixelSize: 17
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("设置")
                    }
                }

                Button {
                    objectName: "newSessionButton"
                    text: qsTr("＋  新对话")
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    onClicked: sessionService.createSession()
                }

                SessionList {
                    id: sessionList
                    objectName: "sessionList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: sessionService.activeSessions
                    currentSessionId: sessionService.currentSessionId
                    onSessionSelected: sessionService.selectSession(sessionId)
                }

                Button {
                    objectName: "archiveButton"
                    text: qsTr("归档当前对话")
                    enabled: sessionService.hasCurrentSession
                    flat: true
                    Layout.fillWidth: true
                    onClicked: sessionService.archiveCurrent()
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                color: "#ffffff"
                border.color: "#e0e3e6"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.rightMargin: 12

                    Label {
                        text: sessionService.hasCurrentSession ? qsTr("新对话") : qsTr("选择或创建对话")
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: "#24282d"
                        Layout.fillWidth: true
                    }

                    ToolButton {
                        objectName: "openWorkspaceButton"
                        text: "▣"
                        enabled: sessionService.hasCurrentSession
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("打开工作区")
                        onClicked: sessionService.openCurrentWorkspace()
                    }
                }
            }

            ChatView {
                id: chatView
                objectName: "chatView"
                Layout.fillWidth: true
                Layout.fillHeight: true
                hasSession: sessionService.hasCurrentSession
            }

            ComposerBar {
                id: composer
                objectName: "composerBar"
                Layout.fillWidth: true
                enabled: sessionService.hasCurrentSession
            }
        }
    }
}
