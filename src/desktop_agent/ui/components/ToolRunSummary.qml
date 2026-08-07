import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    id: root
    property string summary: ""
    property string details: ""
    property bool expanded: false

    padding: 10

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true

            Label {
                text: root.summary
                elide: Text.ElideRight
                Layout.fillWidth: true
                color: "#4b535b"
            }

            ToolButton {
                text: root.expanded ? "⌃" : "⌄"
                ToolTip.visible: hovered
                ToolTip.text: root.expanded ? qsTr("收起") : qsTr("展开详情")
                onClicked: root.expanded = !root.expanded
            }
        }

        TextArea {
            visible: root.expanded
            text: root.details
            readOnly: true
            selectByMouse: true
            wrapMode: TextArea.Wrap
            Layout.fillWidth: true
        }
    }
}
