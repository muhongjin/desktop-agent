import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Dialog {
    id: root

    property string capability: ""
    property string targetPath: ""
    property string operationDetail: ""
    property var restoreFocusItem: null
    signal resolved(string decision)

    readonly property string actionLabel: {
        const labels = {
            "fs.read": qsTr("读取文件或目录"),
            "fs.write": qsTr("写入文件或目录"),
            "fs.delete": qsTr("删除文件或目录"),
            "process.exec": qsTr("运行系统命令")
        }
        return labels[capability] || capability || qsTr("执行受限操作")
    }

    function decide(decision) {
        root.resolved(decision)
        root.close()
    }

    objectName: "permissionDialog"
    title: qsTr("确认权限")
    modal: true
    focus: true
    standardButtons: Dialog.NoButton
    closePolicy: Popup.NoAutoClose
    width: Math.min(520, parent ? parent.width - UI.Theme.space32 : 520)
    padding: UI.Theme.space20

    onOpened: Qt.callLater(rejectButton.forceActiveFocus)
    onClosed: {
        if (restoreFocusItem)
            Qt.callLater(restoreFocusItem.forceActiveFocus)
        restoreFocusItem = null
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.opened
        onActivated: root.decide("deny")
    }

    background: Rectangle {
        radius: UI.Theme.radiusLarge
        color: UI.Theme.surface
        border.color: UI.Theme.borderStrong
        border.width: 1
    }

    contentItem: ColumnLayout {
        spacing: UI.Theme.space16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: UI.Theme.space4

            Label {
                text: root.actionLabel
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontSubtitle
                font.weight: Font.DemiBold
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }

            Label {
                text: qsTr("Agent 请求执行工作区权限范围外的操作。")
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: permissionDetails.implicitHeight + UI.Theme.space24
            radius: UI.Theme.radiusMedium
            color: UI.Theme.background
            border.color: UI.Theme.border

            ColumnLayout {
                id: permissionDetails
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: UI.Theme.space12
                anchors.rightMargin: UI.Theme.space12
                spacing: UI.Theme.space8

                Label {
                    text: qsTr("能力")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                }

                Label {
                    objectName: "permissionCapability"
                    text: root.capability
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.monoFontFamily
                    font.pixelSize: UI.Theme.fontBody
                    Layout.fillWidth: true
                    wrapMode: Text.WrapAnywhere
                }

                Label {
                    text: qsTr("目标")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    Layout.topMargin: UI.Theme.space4
                }

                TextField {
                    objectName: "permissionTarget"
                    text: root.targetPath
                    readOnly: true
                    selectByMouse: true
                    activeFocusOnTab: true
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.monoFontFamily
                    font.pixelSize: UI.Theme.fontBody
                    Layout.fillWidth: true

                    background: Rectangle {
                        radius: UI.Theme.radiusSmall
                        color: UI.Theme.surface
                        border.color: parent.activeFocus ? UI.Theme.focus : UI.Theme.border
                        border.width: parent.activeFocus ? UI.Theme.focusWidth : 1
                    }
                }

                Label {
                    visible: root.operationDetail.length > 0
                    text: qsTr("实际操作")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    Layout.topMargin: UI.Theme.space4
                }

                TextArea {
                    objectName: "permissionOperationDetail"
                    visible: root.operationDetail.length > 0
                    text: root.operationDetail
                    readOnly: true
                    selectByKeyboard: true
                    selectByMouse: true
                    wrapMode: TextArea.WrapAnywhere
                    color: UI.Theme.textPrimary
                    font.family: UI.Theme.monoFontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(96, Math.max(48, contentHeight + UI.Theme.space16))

                    background: Rectangle {
                        radius: UI.Theme.radiusSmall
                        color: UI.Theme.surface
                        border.color: parent.activeFocus ? UI.Theme.focus : UI.Theme.border
                        border.width: parent.activeFocus ? UI.Theme.focusWidth : 1
                    }
                }
            }
        }

        Label {
            text: qsTr("允许一次只批准当前操作；允许本会话会批准本会话内同类操作。高风险操作仍会再次确认。")
            color: UI.Theme.textSecondary
            font.family: UI.Theme.fontFamily
            font.pixelSize: UI.Theme.fontCaption
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: UI.Theme.space8

            Item {
                Layout.fillWidth: true
            }

            Button {
                id: rejectButton
                objectName: "permissionRejectButton"
                text: qsTr("拒绝")
                activeFocusOnTab: true
                onClicked: root.decide("deny")
            }

            Button {
                id: allowSessionButton
                objectName: "permissionAllowSessionButton"
                text: qsTr("允许本会话")
                activeFocusOnTab: true
                onClicked: root.decide("session")
            }

            Button {
                id: allowButton
                objectName: "permissionAllowButton"
                text: qsTr("允许一次")
                activeFocusOnTab: true
                onClicked: root.decide("once")

                background: Rectangle {
                    radius: UI.Theme.radiusMedium
                    color: allowButton.down ? UI.Theme.accentPressed
                          : allowButton.hovered ? UI.Theme.accentHover : UI.Theme.accent
                    border.color: allowButton.visualFocus ? UI.Theme.focus : "transparent"
                    border.width: allowButton.visualFocus ? UI.Theme.focusWidth : 0
                }

                contentItem: Label {
                    text: allowButton.text
                    color: UI.Theme.surface
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
