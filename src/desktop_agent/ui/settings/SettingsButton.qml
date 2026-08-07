import QtQuick
import QtQuick.Controls
import ".." as UI

Button {
    id: control
    property bool primary: false
    property bool destructive: false

    implicitHeight: UI.Theme.controlHeight
    implicitWidth: Math.max(88, contentItem.implicitWidth + UI.Theme.space24)
    leftPadding: UI.Theme.space12
    rightPadding: UI.Theme.space12
    font.family: UI.Theme.fontFamily
    font.pixelSize: UI.Theme.fontBody

    contentItem: Text {
        text: control.text
        font: control.font
        color: !control.enabled ? UI.Theme.disabled
              : control.primary ? "#ffffff"
              : control.destructive ? UI.Theme.danger
              : UI.Theme.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: UI.Theme.radiusMedium
        color: !control.enabled ? UI.Theme.surfaceSecondary
               : control.primary ? (control.down ? UI.Theme.accentPressed : control.hovered ? UI.Theme.accentHover : UI.Theme.accent)
               : control.destructive ? (control.down ? UI.Theme.dangerSubtle : control.hovered ? UI.Theme.dangerSubtle : UI.Theme.surface)
               : control.down ? UI.Theme.surfacePressed
               : control.hovered ? UI.Theme.surfaceHover
               : UI.Theme.surface
        border.width: control.visualFocus ? UI.Theme.focusWidth : 1
        border.color: control.visualFocus ? UI.Theme.focus
                      : control.destructive ? UI.Theme.danger
                      : UI.Theme.borderStrong
    }
}
