import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    id: root
    objectName: "appSettingsPage"
    property string statusMessage: ""

    function saveLogDirectory() {
        settingsService.setValue("log_directory", logDirectory.text)
        root.statusMessage = qsTr("日志目录已保存。")
    }

    Shortcut {
        sequence: "Ctrl+S"
        enabled: root.visible
        onActivated: root.saveLogDirectory()
    }

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
                    text: qsTr("应用")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontTitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("调整启动、外观、Shell 和日志位置。")
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
                spacing: UI.Theme.space12
                Label {
                    text: qsTr("启动")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space16
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: UI.Theme.space2
                        Label {
                            text: qsTr("开机启动")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                        }
                        Label {
                            text: qsTr("登录 Windows 后自动打开 Desktop Agent。")
                            color: UI.Theme.textMuted
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontCaption
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }
                    Switch {
                        checked: settingsService.startAtLogin
                        activeFocusOnTab: true
                        onToggled: settingsService.setValue("start_at_login", checked)
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space12
                Label {
                    text: qsTr("外观")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("主题")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                }
                SettingsComboBox {
                    Layout.fillWidth: true
                    model: [qsTr("跟随系统"), qsTr("浅色"), qsTr("深色")]
                    currentIndex: settingsService.theme === "light" ? 1 : settingsService.theme === "dark" ? 2 : 0
                    onActivated: settingsService.setValue("theme", ["system", "light", "dark"][currentIndex])
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space12
                Label {
                    text: qsTr("命令执行")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("PowerShell")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                }
                SettingsComboBox {
                    objectName: "shellModeSelector"
                    Layout.fillWidth: true
                    model: [qsTr("自动选择"), qsTr("Windows PowerShell 5.1"), qsTr("PowerShell 7+")]
                    currentIndex: settingsService.shellMode === "windows-powershell" ? 1 : settingsService.shellMode === "pwsh" ? 2 : 0
                    onActivated: settingsService.setValue("shell_mode", ["auto", "windows-powershell", "pwsh"][currentIndex])
                }
                Label {
                    text: qsTr("自动选择会优先使用 PowerShell 7，不可用时回退到 Windows PowerShell 5.1。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8
                Label {
                    text: qsTr("日志目录")
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontSubtitle
                    font.weight: Font.DemiBold
                }
                Label {
                    text: qsTr("诊断日志会写入此目录。长路径可以在输入框内横向滚动。")
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
                        id: logDirectory
                        objectName: "logDirectoryInput"
                        text: settingsService.logDirectory
                        Layout.fillWidth: true
                    }
                    SettingsButton {
                        text: qsTr("保存")
                        primary: true
                        onClicked: root.saveLogDirectory()
                    }
                }
                Label {
                    visible: root.statusMessage.length > 0
                    text: qsTr("完成：") + root.statusMessage
                    color: UI.Theme.success
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Item { Layout.preferredHeight: UI.Theme.space24 }
        }
    }
}
