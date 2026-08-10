pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

FocusScope {
    id: root

    signal modeSelected(string value)

    property string mode: "local"
    readonly property bool popupOpen: modePopup.opened
    readonly property var choices: ["none", "local", "all"]

    implicitWidth: 96
    implicitHeight: UI.Theme.controlHeight

    function selectedIndex() {
        const index = choices.indexOf(mode)
        return index >= 0 ? index : 1
    }

    function choose(index) {
        if (index < 0 || index >= choices.length)
            return
        modePopup.close()
        executionModeSelector.forceActiveFocus()
        root.modeSelected(choices[index])
    }

    Button {
        id: executionModeSelector
        objectName: "executionModeSelector"
        anchors.fill: parent
        activeFocusOnTab: true
        Accessible.name: qsTr("执行模式")
        Accessible.description: root.mode
        onClicked: {
            if (modePopup.opened) {
                modePopup.close()
            } else {
                modeChoiceList.currentIndex = root.selectedIndex()
                modePopup.open()
            }
        }

        background: Rectangle {
            radius: UI.Theme.radiusMedium
            color: executionModeSelector.down ? UI.Theme.surfacePressed
                    : executionModeSelector.hovered || modePopup.opened
                      ? UI.Theme.surfaceHover : "transparent"
            border.width: executionModeSelector.visualFocus ? UI.Theme.focusWidth : 1
            border.color: executionModeSelector.visualFocus
                    ? UI.Theme.focus : "transparent"
        }

        contentItem: RowLayout {
            spacing: UI.Theme.space8

            Label {
                Layout.fillWidth: true
                text: root.mode
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.Medium
                verticalAlignment: Text.AlignVCenter
            }

            Label {
                text: modePopup.opened ? "⌃" : "⌄"
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontSubtitle
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    Popup {
        id: modePopup
        objectName: "executionModePopup"
        x: 0
        y: -height - UI.Theme.space8
        width: 168
        height: modeChoiceList.contentHeight + UI.Theme.space8 * 2
        padding: UI.Theme.space8
        focus: true
        modal: false
        dim: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: {
            modeChoiceList.currentIndex = root.selectedIndex()
            Qt.callLater(modeChoiceList.forceActiveFocus)
        }

        background: Rectangle {
            radius: UI.Theme.radiusLarge
            color: UI.Theme.surface
            border.color: UI.Theme.border
        }

        contentItem: ListView {
            id: modeChoiceList
            objectName: "executionModeChoiceList"
            model: root.choices
            currentIndex: root.selectedIndex()
            activeFocusOnTab: true
            boundsBehavior: Flickable.StopAtBounds

            delegate: ItemDelegate {
                id: modeChoice
                required property int index
                required property string modelData
                width: modeChoiceList.width
                height: UI.Theme.controlHeightLarge
                highlighted: ListView.isCurrentItem
                hoverEnabled: true
                Accessible.name: modelData
                Accessible.selected: modelData === root.mode
                onHoveredChanged: {
                    if (hovered)
                        modeChoiceList.currentIndex = index
                }
                onClicked: root.choose(index)

                background: Rectangle {
                    radius: UI.Theme.radiusMedium
                    color: modeChoice.highlighted || modeChoice.hovered
                            ? UI.Theme.surfaceHover : "transparent"
                }

                contentItem: RowLayout {
                    spacing: UI.Theme.space8

                    Label {
                        Layout.fillWidth: true
                        text: modeChoice.modelData
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.Medium
                    }

                    Label {
                        visible: modeChoice.modelData === root.mode
                        text: "✓"
                        color: UI.Theme.accent
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontSubtitle
                    }
                }
            }

            Keys.onPressed: event => {
                if (event.key === Qt.Key_Down) {
                    currentIndex = Math.min(count - 1, currentIndex + 1)
                } else if (event.key === Qt.Key_Up) {
                    currentIndex = Math.max(0, currentIndex - 1)
                } else if (event.key === Qt.Key_Home) {
                    currentIndex = 0
                } else if (event.key === Qt.Key_End) {
                    currentIndex = count - 1
                } else if (event.key === Qt.Key_Return
                           || event.key === Qt.Key_Enter
                           || event.key === Qt.Key_Space) {
                    root.choose(currentIndex)
                } else {
                    return
                }
                event.accepted = true
            }
        }
    }
}
