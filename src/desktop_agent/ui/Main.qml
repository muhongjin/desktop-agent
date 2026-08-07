import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "." as UI
import "components"
import "settings" as SettingsViews

ApplicationWindow {
    id: window

    objectName: "mainWindow"
    width: 1240
    height: 800
    minimumWidth: 920
    minimumHeight: 620
    visible: true
    title: qsTr("Desktop Agent")
    color: UI.Theme.background

    font.family: UI.Theme.fontFamily
    font.pixelSize: UI.Theme.fontBody

    function createSessionAndFocus() {
        sessionService.createSession()
        Qt.callLater(composer.focusEditor)
    }

    function showModelSettings() {
        settingsWindow.show()
        settingsWindow.raise()
        settingsWindow.requestActivate()
    }

    SettingsViews.SettingsWindow {
        id: settingsWindow
    }

    PermissionDialog {
        id: permissionDialog
        onResolved: decision => chatService.resolvePermission(decision)
    }

    Connections {
        target: chatService

        function onPermissionRequested(capability, path, detail) {
            permissionDialog.capability = capability
            permissionDialog.targetPath = path
            permissionDialog.operationDetail = detail
            permissionDialog.restoreFocusItem = window.activeFocusItem
            permissionDialog.open()
        }
    }

    Shortcut {
        id: newSessionShortcut
        objectName: "newSessionShortcut"
        sequence: "Ctrl+N"
        onActivated: window.createSessionAndFocus()
    }

    Shortcut {
        id: stopShortcut
        objectName: "stopShortcut"
        sequence: "Escape"
        enabled: chatService.running && !permissionDialog.opened
                && !composer.popupOpen && !settingsWindow.visible
        onActivated: chatService.stop()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: UI.Theme.navigationWidth
            Layout.fillHeight: true
            color: UI.Theme.surfaceSecondary

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: UI.Theme.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: UI.Theme.space12
                spacing: UI.Theme.space12

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: UI.Theme.controlHeightLarge
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("Desktop Agent")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontSubtitle
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    ToolButton {
                        id: settingsButton
                        objectName: "settingsButton"
                        text: "⚙"
                        font.pixelSize: 17
                        activeFocusOnTab: true
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("设置")
                        onClicked: settingsWindow.show()

                        background: Rectangle {
                            radius: UI.Theme.radiusMedium
                            color: settingsButton.down ? UI.Theme.surfacePressed
                                  : settingsButton.hovered ? UI.Theme.surfaceHover : "transparent"
                            border.color: settingsButton.visualFocus
                                    ? UI.Theme.focus : "transparent"
                            border.width: settingsButton.visualFocus
                                    ? UI.Theme.focusWidth : 0
                        }
                    }
                }

                Button {
                    id: newSessionButton
                    objectName: "newSessionButton"
                    text: qsTr("新对话")
                    Layout.fillWidth: true
                    Layout.preferredHeight: UI.Theme.controlHeightLarge
                    activeFocusOnTab: true
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("新建对话 (Ctrl+N)")
                    onClicked: window.createSessionAndFocus()

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: newSessionButton.down ? UI.Theme.accentPressed
                              : newSessionButton.hovered ? UI.Theme.accentHover : UI.Theme.accent
                        border.color: newSessionButton.visualFocus
                                ? UI.Theme.focus : "transparent"
                        border.width: newSessionButton.visualFocus
                                ? UI.Theme.focusWidth : 0
                    }

                    contentItem: Label {
                        text: newSessionButton.text
                        color: UI.Theme.surface
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Label {
                    text: qsTr("最近对话")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    font.weight: Font.DemiBold
                    Layout.leftMargin: UI.Theme.space8
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
                    id: archiveButton
                    objectName: "archiveButton"
                    text: qsTr("归档当前对话")
                    enabled: sessionService.hasCurrentSession
                    flat: true
                    activeFocusOnTab: true
                    Layout.fillWidth: true
                    Layout.preferredHeight: UI.Theme.controlHeight
                    onClicked: sessionService.archiveCurrent()

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: archiveButton.down ? UI.Theme.surfacePressed
                              : archiveButton.hovered ? UI.Theme.surfaceHover : "transparent"
                        border.color: archiveButton.visualFocus
                                ? UI.Theme.focus : "transparent"
                        border.width: archiveButton.visualFocus
                                ? UI.Theme.focusWidth : 0
                    }

                    contentItem: Label {
                        text: archiveButton.text
                        color: archiveButton.enabled ? UI.Theme.textSecondary : UI.Theme.disabled
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: UI.Theme.space8
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                color: UI.Theme.surface

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: UI.Theme.border
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: UI.Theme.space20
                    anchors.rightMargin: UI.Theme.space12
                    spacing: UI.Theme.space12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Label {
                            text: sessionService.hasCurrentSession
                                    ? sessionService.currentSessionTitle
                                    : qsTr("选择或创建对话")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Label {
                            visible: sessionService.hasCurrentSession
                            text: qsTr("工作区已就绪")
                            color: UI.Theme.textMuted
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontCaption
                        }
                    }

                    Button {
                        id: openWorkspaceButton
                        objectName: "openWorkspaceButton"
                        text: qsTr("打开工作区")
                        enabled: sessionService.hasCurrentSession
                        activeFocusOnTab: true
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("在文件资源管理器中打开")
                        onClicked: sessionService.openCurrentWorkspace()

                        background: Rectangle {
                            radius: UI.Theme.radiusMedium
                            color: openWorkspaceButton.down ? UI.Theme.surfacePressed
                                  : openWorkspaceButton.hovered ? UI.Theme.surfaceHover
                                  : UI.Theme.surface
                            border.color: openWorkspaceButton.visualFocus
                                    ? UI.Theme.focus : UI.Theme.border
                            border.width: openWorkspaceButton.visualFocus
                                    ? UI.Theme.focusWidth : 1
                        }
                    }
                }
            }

            ChatView {
                id: chatView
                objectName: "chatView"
                Layout.fillWidth: true
                Layout.fillHeight: true
                hasSession: sessionService.hasCurrentSession
                running: chatService.running
                model: chatService.messageModel
            }

            ComposerBar {
                id: composer
                objectName: "composerBar"
                Layout.fillWidth: true
                enabled: sessionService.hasCurrentSession
                modelChoices: modelService.configuredModels
                selectedModel: sessionService.currentModelId
                thinkingStrength: sessionService.thinkingStrength
                executionMode: sessionService.executionMode
                fullAccess: sessionService.fullAccess
                running: chatService.running
                onModelSelected: sessionService.setCurrentModel(value)
                onThinkingSelected: sessionService.setThinkingStrength(value)
                onExecutionModeSelected: sessionService.setExecutionMode(value)
                onFullAccessChangedByUser: sessionService.setFullAccess(enabled)
                onConfigureModelsRequested: window.showModelSettings()
                onSendRequested: text => chatService.sendMessage(text)
                onStopRequested: chatService.stop()
            }
        }
    }
}
