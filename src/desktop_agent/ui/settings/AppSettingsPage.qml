import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        Label {
            text: qsTr("应用")
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }

        CheckBox {
            text: qsTr("开机启动")
            checked: settingsService.startAtLogin
            onToggled: settingsService.setValue("start_at_login", checked)
        }

        Label { text: qsTr("主题") }
        ComboBox {
            model: [qsTr("跟随系统"), qsTr("浅色"), qsTr("深色")]
            currentIndex: settingsService.theme === "light" ? 1 : settingsService.theme === "dark" ? 2 : 0
            onActivated: settingsService.setValue("theme", ["system", "light", "dark"][currentIndex])
        }

        Label { text: qsTr("PowerShell") }
        ComboBox {
            objectName: "shellModeSelector"
            model: [qsTr("自动"), qsTr("Windows PowerShell 5.1"), qsTr("PowerShell 7+")]
            currentIndex: settingsService.shellMode === "windows-powershell" ? 1 : settingsService.shellMode === "pwsh" ? 2 : 0
            onActivated: settingsService.setValue("shell_mode", ["auto", "windows-powershell", "pwsh"][currentIndex])
        }

        Label { text: qsTr("日志目录") }
        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: logDirectory
                objectName: "logDirectoryInput"
                text: settingsService.logDirectory
                selectByMouse: true
                Layout.fillWidth: true
            }
            Button {
                text: qsTr("保存")
                onClicked: settingsService.setValue("log_directory", logDirectory.text)
            }
        }

        Item { Layout.fillHeight: true }
    }
}
