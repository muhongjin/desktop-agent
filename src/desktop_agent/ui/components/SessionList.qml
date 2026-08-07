import QtQuick
import QtQuick.Controls
import ".." as UI

ListView {
    id: root

    property string currentSessionId: ""
    signal sessionSelected(string sessionId)

    clip: true
    spacing: UI.Theme.space4
    boundsBehavior: Flickable.StopAtBounds
    activeFocusOnTab: true
    keyNavigationEnabled: false
    currentIndex: -1
    highlightMoveDuration: 80

    function moveCursor(index) {
        if (count === 0)
            return
        currentIndex = Math.max(0, Math.min(count - 1, index))
        positionViewAtIndex(currentIndex, ListView.Contain)
    }

    function activateCursor() {
        if (currentItem)
            sessionSelected(currentItem.sessionId)
    }

    Keys.onPressed: event => {
        if (event.modifiers !== Qt.NoModifier)
            return
        if (event.key === Qt.Key_Up) {
            moveCursor(currentIndex < 0 ? count - 1 : currentIndex - 1)
            event.accepted = true
        } else if (event.key === Qt.Key_Down) {
            moveCursor(currentIndex < 0 ? 0 : currentIndex + 1)
            event.accepted = true
        } else if (event.key === Qt.Key_Home) {
            moveCursor(0)
            event.accepted = true
        } else if (event.key === Qt.Key_End) {
            moveCursor(count - 1)
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            activateCursor()
            event.accepted = true
        }
    }

    delegate: ItemDelegate {
        id: delegate

        required property string sessionId
        required property string title
        required property int index
        readonly property bool selected: root.currentSessionId === sessionId

        width: ListView.view.width
        height: UI.Theme.controlHeightLarge
        text: title
        hoverEnabled: true
        highlighted: selected || (root.activeFocus && ListView.isCurrentItem)
        onSelectedChanged: {
            if (selected)
                root.currentIndex = index
        }
        Component.onCompleted: {
            if (selected)
                root.currentIndex = index
        }
        onClicked: {
            root.currentIndex = index
            root.sessionSelected(sessionId)
            root.forceActiveFocus()
        }

        contentItem: Label {
            text: delegate.text
            color: delegate.selected ? UI.Theme.accent : UI.Theme.textPrimary
            font.family: UI.Theme.fontFamily
            font.pixelSize: UI.Theme.fontBody
            font.weight: delegate.selected ? Font.DemiBold : Font.Normal
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            leftPadding: UI.Theme.space12
            rightPadding: UI.Theme.space8
        }

        background: Rectangle {
            radius: UI.Theme.radiusMedium
            color: delegate.selected ? UI.Theme.accentSubtle
                  : delegate.down ? UI.Theme.surfacePressed
                  : delegate.hovered ? UI.Theme.surfaceHover : "transparent"
            border.color: root.activeFocus && delegate.ListView.isCurrentItem
                    ? UI.Theme.focus : "transparent"
            border.width: root.activeFocus && delegate.ListView.isCurrentItem
                    ? UI.Theme.focusWidth : 0
        }
    }

    ScrollBar.vertical: ScrollBar {
        policy: root.contentHeight > root.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
    }
}
