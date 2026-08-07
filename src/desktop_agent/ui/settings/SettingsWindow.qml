import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import ".." as UI

Window {
    id: root
    objectName: "settingsWindow"
    width: 960
    height: 680
    minimumWidth: 780
    minimumHeight: 540
    title: qsTr("设置")
    color: UI.Theme.background

    onVisibleChanged: {
        if (visible)
            Qt.callLater(navigation.forceActiveFocus)
    }

    Shortcut {
        sequence: "Ctrl+W"
        onActivated: root.close()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: UI.Theme.navigationWidth
            Layout.fillHeight: true
            color: UI.Theme.surfaceSecondary

            Rectangle {
                width: 1
                height: parent.height
                anchors.right: parent.right
                color: UI.Theme.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: UI.Theme.space16
                spacing: UI.Theme.space16

                Label {
                    text: qsTr("设置")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontTitle
                    font.weight: Font.DemiBold
                    Layout.leftMargin: UI.Theme.space8
                    Layout.topMargin: UI.Theme.space8
                }

                ListView {
                    id: navigation
                    objectName: "settingsNavigation"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: UI.Theme.space4
                    currentIndex: 0
                    activeFocusOnTab: true
                    keyNavigationEnabled: true
                    model: [
                        qsTr("模型服务"),
                        qsTr("系统提示词"),
                        qsTr("已归档聊天"),
                        qsTr("数据与工作区"),
                        qsTr("应用")
                    ]

                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Home) {
                            currentIndex = 0
                            positionViewAtIndex(currentIndex, ListView.Contain)
                            event.accepted = true
                        } else if (event.key === Qt.Key_End) {
                            currentIndex = count - 1
                            positionViewAtIndex(currentIndex, ListView.Contain)
                            event.accepted = true
                        }
                    }

                    delegate: ItemDelegate {
                        required property string modelData
                        required property int index
                        width: ListView.view.width
                        height: UI.Theme.controlHeightLarge
                        text: modelData
                        highlighted: ListView.isCurrentItem
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        onClicked: {
                            navigation.currentIndex = index
                            navigation.forceActiveFocus()
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.highlighted ? UI.Theme.accent : UI.Theme.textPrimary
                            font.family: parent.font.family
                            font.pixelSize: parent.font.pixelSize
                            font.weight: parent.highlighted ? Font.DemiBold : Font.Normal
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            leftPadding: UI.Theme.space12
                        }
                        background: Rectangle {
                            radius: UI.Theme.radiusMedium
                            color: parent.highlighted ? UI.Theme.accentSubtle
                                  : parent.hovered ? UI.Theme.surfaceHover
                                  : "transparent"
                            border.width: parent.visualFocus ? UI.Theme.focusWidth : 0
                            border.color: UI.Theme.focus
                        }
                    }
                }

                Label {
                    text: qsTr("本地运行 · 无需登录")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    Layout.leftMargin: UI.Theme.space8
                    Layout.bottomMargin: UI.Theme.space8
                }
            }
        }

        StackLayout {
            objectName: "settingsPages"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: navigation.currentIndex

            ModelServicePage {}
            SystemPromptPage {}
            ArchivedChatsPage {}
            DataWorkspacePage {}
            AppSettingsPage {}
        }
    }
}
