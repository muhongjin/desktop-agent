pragma Singleton

import QtQuick

QtObject {
    readonly property color background: "#f7f7f8"
    readonly property color surface: "#ffffff"
    readonly property color surfaceSecondary: "#f1f2f3"
    readonly property color surfaceHover: "#e9eaec"
    readonly property color surfacePressed: "#dedfe2"
    readonly property color textPrimary: "#1b1a19"
    readonly property color textSecondary: "#5d5a58"
    readonly property color textMuted: "#767370"
    readonly property color border: "#d8d6d4"
    readonly property color borderStrong: "#8a8886"
    readonly property color accent: "#0f6cbd"
    readonly property color accentHover: "#115ea3"
    readonly property color accentPressed: "#0c3b5e"
    readonly property color accentSubtle: "#ebf3fc"
    readonly property color focus: "#005fb8"
    readonly property color success: "#107c10"
    readonly property color successSubtle: "#eaf6ea"
    readonly property color warning: "#8a4f00"
    readonly property color warningSubtle: "#fff4ce"
    readonly property color danger: "#c42b1c"
    readonly property color dangerHover: "#a4262c"
    readonly property color dangerSubtle: "#fde7e9"
    readonly property color disabled: "#a19f9d"

    readonly property int space2: 2
    readonly property int space4: 4
    readonly property int space8: 8
    readonly property int space12: 12
    readonly property int space16: 16
    readonly property int space20: 20
    readonly property int space24: 24
    readonly property int space32: 32

    readonly property int radiusSmall: 4
    readonly property int radiusMedium: 6
    readonly property int radiusLarge: 8
    readonly property int controlHeight: 36
    readonly property int controlHeightLarge: 40
    readonly property int navigationWidth: 220
    readonly property int contentMaxWidth: 760
    readonly property int focusWidth: 2

    readonly property int fontCaption: 12
    readonly property int fontBody: 14
    readonly property int fontSubtitle: 16
    readonly property int fontTitle: 24
    readonly property int lineHeightBody: 20
    readonly property string fontFamily: "Segoe UI"
    readonly property string monoFontFamily: "Consolas"
}
