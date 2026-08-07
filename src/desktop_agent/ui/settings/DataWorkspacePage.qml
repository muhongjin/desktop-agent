import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    objectName: "dataWorkspacePage"
    ScrollView {
        id: pageScroll
        anchors.fill: parent
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            x: Math.max(UI.Theme.space32, (pageScroll.availableWidth - width) / 2)
            width: Math.max(360, Math.min(UI.Theme.contentMaxWidth, pageScroll.availableWidth - UI.Theme.space32 * 2))
            spacing: UI.Theme.space20

            Item { Layout.preferredHeight: UI.Theme.space12 }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space4
                Label {
                    text: qsTr("数据与工作区")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontTitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("查看应用数据和会话工作区在本机上的保存位置。")
                    color: UI.Theme.textSecondary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("应用数据")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("包含设置、聊天记录和本地数据库。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8
                    SettingsTextField {
                        text: dataService.dataPath
                        readOnly: true
                        Layout.fillWidth: true
                        font.family: UI.Theme.monoFontFamily
                    }
                    SettingsButton {
                        text: qsTr("打开目录")
                        enabled: dataService.dataPath.length > 0
                        onClicked: dataService.openDataDirectory()
                    }
                }
                Label {
                    visible: dataService.dataPath.length === 0
                    text: qsTr("不可用：应用数据目录尚未初始化。")
                    color: UI.Theme.danger
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("会话工作区")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("每个会话会在这里自动创建独立目录；归档聊天不会移除工作区。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8
                    SettingsTextField {
                        text: dataService.workspacesPath
                        readOnly: true
                        Layout.fillWidth: true
                        font.family: UI.Theme.monoFontFamily
                    }
                    SettingsButton {
                        text: qsTr("打开目录")
                        enabled: dataService.workspacesPath.length > 0
                        onClicked: dataService.openWorkspacesDirectory()
                    }
                }
                Label {
                    visible: dataService.workspacesPath.length === 0
                    text: qsTr("不可用：工作区目录尚未初始化。")
                    color: UI.Theme.danger
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                }
            }

            Item { Layout.preferredHeight: UI.Theme.space24 }
        }
    }
}
