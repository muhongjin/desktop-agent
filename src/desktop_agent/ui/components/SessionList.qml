import QtQuick
import QtQuick.Controls

ListView {
    id: root
    property string currentSessionId: ""
    signal sessionSelected(string sessionId)

    clip: true
    spacing: 4
    boundsBehavior: Flickable.StopAtBounds

    delegate: ItemDelegate {
        required property string sessionId
        required property string title
        width: ListView.view.width
        height: 42
        text: title
        highlighted: root.currentSessionId === sessionId
        onClicked: root.sessionSelected(sessionId)
    }

    ScrollBar.vertical: ScrollBar {}
}
