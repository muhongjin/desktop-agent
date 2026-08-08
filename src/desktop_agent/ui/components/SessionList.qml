import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

ListView {
    id: root

    property string currentSessionId: ""
    property string contextSessionId: ""
    property string contextSessionTitle: ""
    signal sessionSelected(string sessionId)
    signal archiveRequested(string sessionId)
    signal workspaceRequested(string sessionId)
    signal renameRequested(string sessionId, string title)

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

    function openContextMenu(sessionId, title, parentItem, x, y) {
        contextSessionId = sessionId
        contextSessionTitle = title
        contextMenu.popup(parentItem, x, y)
    }

    function openCursorMenu() {
        if (!currentItem)
            return
        openContextMenu(currentItem.sessionId, currentItem.title, currentItem,
                        UI.Theme.space12, currentItem.height / 2)
    }

    function openRenameDialog() {
        renameInput.text = contextSessionTitle
        renameDialog.open()
    }

    Keys.onPressed: event => {
        const contextShortcut = event.key === Qt.Key_F10
                && event.modifiers === Qt.ShiftModifier
        if (event.modifiers !== Qt.NoModifier && !contextShortcut)
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
        } else if (event.key === Qt.Key_Menu || contextShortcut) {
            openCursorMenu()
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

        TapHandler {
            acceptedButtons: Qt.RightButton
            gesturePolicy: TapHandler.ReleaseWithinBounds
            onTapped: eventPoint => root.openContextMenu(
                delegate.sessionId,
                delegate.title,
                delegate,
                eventPoint.position.x,
                eventPoint.position.y
            )
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
                  : root.contextSessionId === delegate.sessionId && contextMenu.opened
                    ? UI.Theme.surfaceHover
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

    Menu {
        id: contextMenu
        objectName: "sessionContextMenu"

        MenuItem {
            objectName: "renameSessionMenuItem"
            text: qsTr("重命名")
            onTriggered: root.openRenameDialog()
        }

        MenuItem {
            objectName: "openWorkspaceMenuItem"
            text: qsTr("打开工作区")
            onTriggered: root.workspaceRequested(root.contextSessionId)
        }

        MenuSeparator {}

        MenuItem {
            objectName: "archiveSessionMenuItem"
            text: qsTr("归档")
            onTriggered: root.archiveRequested(root.contextSessionId)
        }
    }

    Dialog {
        id: renameDialog
        objectName: "renameSessionDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        title: qsTr("重命名对话")
        modal: true
        focus: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        closePolicy: Popup.CloseOnEscape
        width: Math.min(400, parent ? parent.width - UI.Theme.space32 : 400)
        padding: UI.Theme.space20

        onOpened: Qt.callLater(() => {
            renameInput.forceActiveFocus()
            renameInput.selectAll()
        })
        onAccepted: {
            const title = renameInput.text.trim()
            if (title.length > 0)
                root.renameRequested(root.contextSessionId, title)
        }

        background: Rectangle {
            radius: UI.Theme.radiusLarge
            color: UI.Theme.surface
            border.color: UI.Theme.borderStrong
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: UI.Theme.space12

            Label {
                text: qsTr("输入新的对话名称")
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                Layout.fillWidth: true
            }

            TextField {
                id: renameInput
                objectName: "renameSessionInput"
                maximumLength: 24
                selectByMouse: true
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                Layout.fillWidth: true
            }
        }
    }
}
