import QtQuick
import QtQuick.Controls
import ".." as UI

TextField {
    id: control
    implicitHeight: UI.Theme.controlHeightLarge
    leftPadding: UI.Theme.space12
    rightPadding: UI.Theme.space12
    selectByMouse: true
    font.family: UI.Theme.fontFamily
    font.pixelSize: UI.Theme.fontBody
    color: UI.Theme.textPrimary
    placeholderTextColor: UI.Theme.textMuted
    selectionColor: UI.Theme.accent
    selectedTextColor: "#ffffff"

    background: Rectangle {
        radius: UI.Theme.radiusMedium
        color: control.readOnly ? UI.Theme.surfaceSecondary : UI.Theme.surface
        border.width: control.activeFocus ? UI.Theme.focusWidth : 1
        border.color: control.activeFocus ? UI.Theme.focus : UI.Theme.borderStrong
    }
}
