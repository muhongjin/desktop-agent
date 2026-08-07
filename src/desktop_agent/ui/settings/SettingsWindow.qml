import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root
    objectName: "settingsWindow"
    width: 900
    height: 620
    minimumWidth: 760
    minimumHeight: 520
    title: qsTr("设置")
    color: "#f7f8f9"

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 190
            Layout.fillHeight: true
            color: "#eceff1"

            ListView {
                id: navigation
                objectName: "settingsNavigation"
                anchors.fill: parent
                anchors.margins: 12
                spacing: 4
                currentIndex: 0
                model: [
                    qsTr("模型服务"),
                    qsTr("系统提示词"),
                    qsTr("已归档聊天"),
                    qsTr("数据与工作区"),
                    qsTr("应用")
                ]

                delegate: ItemDelegate {
                    required property string modelData
                    required property int index
                    width: ListView.view.width
                    height: 42
                    text: modelData
                    highlighted: ListView.isCurrentItem
                    onClicked: navigation.currentIndex = index
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
