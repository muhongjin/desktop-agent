import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        Label {
            text: qsTr("数据与工作区")
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }

        Label { text: qsTr("数据目录") }
        TextField {
            text: dataService.dataPath
            readOnly: true
            selectByMouse: true
            Layout.fillWidth: true
        }
        Button {
            text: qsTr("打开数据目录")
            onClicked: dataService.openDataDirectory()
        }

        Label { text: qsTr("默认工作区目录") }
        TextField {
            text: dataService.workspacesPath
            readOnly: true
            selectByMouse: true
            Layout.fillWidth: true
        }
        Button {
            text: qsTr("打开工作区目录")
            onClicked: dataService.openWorkspacesDirectory()
        }

        Item { Layout.fillHeight: true }
    }
}
