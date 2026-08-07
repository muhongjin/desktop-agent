import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".."

Rectangle {
    id: root

    property string summary: ""
    property string details: ""
    property string toolName: ""
    property string toolStatus: ""
    property string toolInput: ""
    property bool expanded: false
    readonly property string statusIcon: toolStatus === "completed" ? "✓"
                                                 : toolStatus === "failed" ? "×"
                                                 : toolStatus === "cancelled" ? "■" : "…"
    readonly property string statusText: toolStatus === "completed" ? qsTr("成功")
                                                 : toolStatus === "failed" ? qsTr("失败")
                                                 : toolStatus === "cancelled" ? qsTr("已取消")
                                                                                 : qsTr("运行中")
    readonly property color statusColor: toolStatus === "completed" ? Theme.success
                                                 : toolStatus === "failed" ? Theme.danger
                                                 : toolStatus === "cancelled" ? Theme.warning
                                                                                 : Theme.textSecondary

    function copyInput() {
        inputArea.selectAll()
        inputArea.copy()
        inputArea.deselect()
    }

    function copyOutput() {
        outputArea.selectAll()
        outputArea.copy()
        outputArea.deselect()
    }

    implicitHeight: expanded ? 440 : 60
    color: Theme.surfaceSecondary
    border.color: Theme.border
    border.width: 1
    radius: Theme.radiusMedium

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        anchors.margins: Theme.space12
        spacing: root.expanded ? Theme.space12 : 0

        AbstractButton {
            id: summaryButton
            objectName: "toolSummaryButton"
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.controlHeight
            activeFocusOnTab: true
            clip: true
            onClicked: root.expanded = !root.expanded

            background: Rectangle {
                color: summaryButton.down ? Theme.surfacePressed
                                          : summaryButton.hovered ? Theme.surfaceHover
                                                                  : "transparent"
                border.color: summaryButton.activeFocus ? Theme.focus : "transparent"
                border.width: summaryButton.activeFocus ? Theme.focusWidth : 0
                radius: Theme.radiusSmall
            }

            contentItem: RowLayout {
                spacing: Theme.space8

                Label {
                    text: root.statusIcon
                    color: root.statusColor
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSubtitle
                    font.weight: Font.Bold
                    Layout.preferredWidth: Theme.space20
                    horizontalAlignment: Text.AlignHCenter
                }

                Label {
                    text: root.toolName || qsTr("工具")
                    color: Theme.textPrimary
                    font.family: Theme.monoFontFamily
                    font.pixelSize: Theme.fontBody
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    Layout.maximumWidth: 180
                }

                Label {
                    objectName: "toolSummaryText"
                    text: root.summary
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontBody
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    wrapMode: Text.NoWrap
                    clip: true
                    Layout.fillWidth: true
                }

                Label {
                    text: root.statusText
                    color: root.statusColor
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontCaption
                    font.weight: Font.DemiBold
                }

                Label {
                    text: root.expanded ? "⌃" : "⌄"
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSubtitle
                    Layout.preferredWidth: Theme.space20
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            ToolTip.visible: hovered
            ToolTip.text: root.expanded ? qsTr("收起工具详情") : qsTr("展开工具详情")
        }

        ColumnLayout {
            objectName: "toolInputSection"
            visible: root.expanded
            spacing: Theme.space4
            Layout.fillWidth: true

            RowLayout {
                Layout.fillWidth: true

                Label {
                    text: qsTr("输入")
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontCaption
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }

                ToolButton {
                    objectName: "copyToolInputButton"
                    text: qsTr("复制")
                    enabled: root.toolInput.length > 0
                    onClicked: root.copyInput()
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("复制工具输入")
                }
            }

            ScrollView {
                id: inputScroll
                objectName: "toolInputScroll"
                Layout.fillWidth: true
                Layout.preferredHeight: 88
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                TextArea {
                    id: inputArea
                    objectName: "toolInputText"
                    text: root.toolInput || qsTr("无输入")
                    readOnly: true
                    selectByKeyboard: true
                    selectByMouse: true
                    wrapMode: TextArea.NoWrap
                    color: Theme.textPrimary
                    font.family: Theme.monoFontFamily
                    font.pixelSize: Theme.fontCaption
                    background: Rectangle {
                        color: Theme.surface
                        border.color: Theme.border
                        radius: Theme.radiusSmall
                    }
                }
            }
        }

        ColumnLayout {
            objectName: "toolOutputSection"
            visible: root.expanded
            spacing: Theme.space4
            Layout.fillWidth: true

            RowLayout {
                Layout.fillWidth: true

                Label {
                    text: qsTr("输出")
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontCaption
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }

                ToolButton {
                    objectName: "copyToolOutputButton"
                    text: qsTr("复制")
                    enabled: root.details.length > 0
                    onClicked: root.copyOutput()
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("复制工具输出")
                }
            }

            ScrollView {
                id: outputScroll
                objectName: "toolOutputScroll"
                Layout.fillWidth: true
                Layout.preferredHeight: 156
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                TextArea {
                    id: outputArea
                    objectName: "toolOutputText"
                    text: root.details || qsTr("无输出")
                    readOnly: true
                    selectByKeyboard: true
                    selectByMouse: true
                    wrapMode: TextArea.NoWrap
                    color: Theme.textPrimary
                    font.family: Theme.monoFontFamily
                    font.pixelSize: Theme.fontCaption
                    background: Rectangle {
                        color: Theme.surface
                        border.color: Theme.border
                        radius: Theme.radiusSmall
                    }
                }
            }
        }
    }
}
