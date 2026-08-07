import QtQuick
import QtQuick.Controls
import ".." as UI

ComboBox {
    id: control
    implicitHeight: UI.Theme.controlHeightLarge
    leftPadding: UI.Theme.space12
    rightPadding: UI.Theme.space32
    font.family: UI.Theme.fontFamily
    font.pixelSize: UI.Theme.fontBody

    contentItem: Text {
        leftPadding: 0
        rightPadding: 0
        text: control.displayText
        font: control.font
        color: control.enabled ? UI.Theme.textPrimary : UI.Theme.disabled
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: control.width - width - UI.Theme.space12
        y: (control.height - height) / 2
        text: "⌄"
        color: control.enabled ? UI.Theme.textSecondary : UI.Theme.disabled
        font.family: UI.Theme.fontFamily
        font.pixelSize: UI.Theme.fontSubtitle
    }

    background: Rectangle {
        radius: UI.Theme.radiusMedium
        color: control.down ? UI.Theme.surfacePressed : control.hovered ? UI.Theme.surfaceHover : UI.Theme.surface
        border.width: control.visualFocus ? UI.Theme.focusWidth : 1
        border.color: control.visualFocus ? UI.Theme.focus : UI.Theme.borderStrong
    }

    delegate: ItemDelegate {
        required property var model
        required property int index
        width: ListView.view ? ListView.view.width : control.width
        height: UI.Theme.controlHeight
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: control.textAt(index)
            color: UI.Theme.textPrimary
            font: control.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            color: parent.highlighted ? UI.Theme.accentSubtle : parent.hovered ? UI.Theme.surfaceHover : UI.Theme.surface
        }
    }

    popup: Popup {
        y: control.height + UI.Theme.space4
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + UI.Theme.space8, 280)
        padding: UI.Theme.space4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle {
            color: UI.Theme.surface
            border.color: UI.Theme.border
            radius: UI.Theme.radiusMedium
        }
    }
}
