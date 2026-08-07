import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

FocusScope {
    id: root

    property bool hasSession: false
    property bool running: false
    property alias model: messageList.model
    property alias timeline: messageList
    property bool followingTail: true
    property bool pendingNewContent: false
    property bool tailLayoutPending: false
    property int previousCount: 0
    property real previousContentY: 0
    readonly property bool newContentAvailable: pendingNewContent && !followingTail

    function isAtBottom() {
        return messageList.contentHeight <= messageList.height
                || messageList.contentY >= messageList.originY
                    + messageList.contentHeight - messageList.height - Theme.space4
    }

    function scrollToBottom() {
        followingTail = true
        pendingNewContent = false
        tailLayoutPending = false
        if (messageList.count > 0)
            messageList.positionViewAtEnd()
        previousContentY = messageList.contentY
    }

    function scheduleTailFollow() {
        Qt.callLater(scrollToBottom)
    }

    function markNewContent() {
        if (followingTail) {
            tailLayoutPending = true
        } else {
            pendingNewContent = true
        }
    }

    function scrollPage(direction) {
        const distance = Math.max(Theme.controlHeightLarge, messageList.height * 0.8)
        const upperBound = messageList.originY
        const lowerBound = Math.max(upperBound,
                                    messageList.originY + messageList.contentHeight
                                    - messageList.height)
        messageList.contentY = Math.max(upperBound,
                                        Math.min(lowerBound,
                                                 messageList.contentY + direction * distance))
        followingTail = isAtBottom()
        if (followingTail)
            pendingNewContent = false
        previousContentY = messageList.contentY
    }

    ListView {
        id: messageList
        objectName: "messageTimeline"
        anchors.fill: parent
        anchors.leftMargin: root.width < 600 ? Theme.space12 : Theme.space24
        anchors.rightMargin: anchors.leftMargin
        anchors.topMargin: Theme.space16
        anchors.bottomMargin: Theme.space16
        activeFocusOnTab: true
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        keyNavigationEnabled: false
        spacing: Theme.space16

        delegate: Item {
            id: messageDelegate

            required property string role
            required property string content
            required property string status
            required property string details
            required property string toolName
            required property string toolStatus
            required property string toolInput
            required property bool completionMarker

            width: ListView.view.width
            implicitHeight: messageColumn.implicitHeight

            ColumnLayout {
                id: messageColumn
                width: Math.min(parent.width, Theme.contentMaxWidth)
                x: (parent.width - width) / 2
                spacing: Theme.space4

                Label {
                    text: messageDelegate.role === "user" ? qsTr("你") : qsTr("Agent")
                    visible: messageDelegate.role !== "tool"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontCaption
                    font.weight: Font.DemiBold
                    color: messageDelegate.role === "user" ? Theme.accent : Theme.textSecondary
                    Layout.fillWidth: true
                }

                TextEdit {
                    id: messageText
                    objectName: "messageText"
                    visible: messageDelegate.role !== "tool"
                    text: messageDelegate.content
                    readOnly: true
                    selectByKeyboard: true
                    selectByMouse: true
                    wrapMode: TextEdit.Wrap
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontBody
                    Layout.fillWidth: true
                }

                RowLayout {
                    id: thinkingIndicator
                    objectName: "thinkingIndicator"
                    visible: root.running
                            && messageDelegate.role === "assistant"
                            && messageDelegate.content.length === 0
                            && !messageDelegate.completionMarker
                    spacing: Theme.space8
                    Layout.fillWidth: true

                    BusyIndicator {
                        running: thinkingIndicator.visible
                        Layout.preferredWidth: Theme.space20
                        Layout.preferredHeight: Theme.space20
                    }

                    Label {
                        text: qsTr("正在思考")
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontBody
                        Layout.alignment: Qt.AlignVCenter
                    }
                }

                ToolRunSummary {
                    visible: messageDelegate.role === "tool"
                    summary: messageDelegate.content
                    toolName: messageDelegate.toolName
                    toolStatus: messageDelegate.toolStatus
                    toolInput: messageDelegate.toolInput
                    details: messageDelegate.details
                    Layout.fillWidth: true
                }
            }
        }

        ScrollBar.vertical: ScrollBar {
            policy: messageList.contentHeight > messageList.height
                    ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
        }

        Keys.onPressed: event => {
            if (event.key === Qt.Key_PageUp && event.modifiers === Qt.NoModifier) {
                root.scrollPage(-1)
                event.accepted = true
            } else if (event.key === Qt.Key_PageDown && event.modifiers === Qt.NoModifier) {
                root.scrollPage(1)
                event.accepted = true
            } else if (event.key === Qt.Key_Home
                       && (event.modifiers & Qt.ControlModifier)) {
                root.followingTail = false
                messageList.positionViewAtBeginning()
                root.previousContentY = messageList.contentY
                event.accepted = true
            } else if (event.key === Qt.Key_End
                       && (event.modifiers & Qt.ControlModifier)) {
                root.scrollToBottom()
                event.accepted = true
            }
        }

        onCountChanged: {
            if (count === 0) {
                root.followingTail = true
                root.pendingNewContent = false
            } else if (count > root.previousCount) {
                root.markNewContent()
            }
            root.previousCount = count
        }

        onContentHeightChanged: {
            if (root.followingTail && root.tailLayoutPending) {
                root.tailLayoutPending = false
                root.scheduleTailFollow()
            }
        }

        onContentYChanged: {
            const movedUp = contentY < root.previousContentY - 0.5
            if ((moving || dragging || flicking) && movedUp)
                root.followingTail = false
            if ((moving || dragging || flicking) && root.isAtBottom()) {
                root.followingTail = true
                root.pendingNewContent = false
            }
            root.previousContentY = contentY
        }

        onMovementStarted: {
            if (!root.isAtBottom())
                root.followingTail = false
        }

        onMovementEnded: {
            if (root.isAtBottom()) {
                root.followingTail = true
                root.pendingNewContent = false
            }
        }
    }

    Connections {
        target: messageList.model
        ignoreUnknownSignals: true

        function onDataChanged() {
            root.markNewContent()
        }

        function onModelReset() {
            if (messageList.count > 0)
                root.markNewContent()
        }
    }

    Button {
        id: newContentButton
        objectName: "newContentButton"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.space16
        visible: root.newContentAvailable
        text: qsTr("有新内容  ↓")
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontBody
        height: Theme.controlHeight
        padding: Theme.space8
        z: 2
        onClicked: {
            root.scrollToBottom()
            messageList.forceActiveFocus()
        }

        background: Rectangle {
            radius: Theme.radiusMedium
            color: newContentButton.down ? Theme.accentPressed
                                        : newContentButton.hovered ? Theme.accentHover
                                                                   : Theme.accent
            border.color: newContentButton.activeFocus ? Theme.focus : "transparent"
            border.width: newContentButton.activeFocus ? Theme.focusWidth : 0
        }

        contentItem: Label {
            text: newContentButton.text
            color: Theme.surface
            font: newContentButton.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - Theme.space24 * 2, 420)
        spacing: Theme.space8
        visible: messageList.count === 0

        Label {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.hasSession ? qsTr("开始一段对话") : qsTr("创建对话后即可开始")
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSubtitle
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            wrapMode: Text.Wrap
        }

        Label {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.hasSession ? qsTr("工作区已为当前会话准备好") : qsTr("每个会话都有独立工作区")
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontBody
            color: Theme.textMuted
            wrapMode: Text.Wrap
        }
    }
}
