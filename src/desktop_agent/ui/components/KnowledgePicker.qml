pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import ".." as UI

FocusScope {
    id: root

    signal selectionChanged(var ids)

    property var choices: []
    property var selectedIds: []
    readonly property bool popupOpen: pickerPopup.opened
    readonly property int selectedCount: selectedIds ? selectedIds.length : 0

    implicitWidth: 118
    implicitHeight: UI.Theme.controlHeight

    function isSelected(kbId) {
        return selectedIds !== undefined && selectedIds !== null
                && selectedIds.indexOf(kbId) >= 0
    }

    function toggle(kbId) {
        const current = (selectedIds || []).slice()
        const index = current.indexOf(kbId)
        if (index >= 0)
            current.splice(index, 1)
        else
            current.push(kbId)
        selectedIds = current
        root.selectionChanged(current)
    }

    function clearAll() {
        selectedIds = []
        root.selectionChanged([])
    }

    Button {
        id: selector
        objectName: "knowledgePickerButton"
        anchors.fill: parent
        activeFocusOnTab: true
        Accessible.name: qsTr("知识库")
        ToolTip.visible: hovered
        ToolTip.text: qsTr("选择当前会话使用的知识库")
        onClicked: {
            if (pickerPopup.opened) {
                pickerPopup.close()
            } else {
                pickerPopup.open()
            }
        }

        background: Rectangle {
            radius: UI.Theme.radiusMedium
            color: selector.down ? UI.Theme.surfacePressed
                    : selector.hovered || pickerPopup.opened
                      ? UI.Theme.surfaceHover : "transparent"
            border.width: selector.visualFocus ? UI.Theme.focusWidth : 1
            border.color: selector.visualFocus ? UI.Theme.focus
                    : pickerPopup.opened ? UI.Theme.borderStrong : "transparent"
        }

        contentItem: RowLayout {
            spacing: UI.Theme.space8

            Label {
                Layout.fillWidth: true
                text: root.selectedCount === 0
                      ? qsTr("知识库：关")
                      : qsTr("知识库：%1").arg(root.selectedCount)
                color: root.selectedCount === 0
                       ? UI.Theme.textSecondary : UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.Medium
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }

            Label {
                text: pickerPopup.opened ? "⌃" : "⌄"
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontSubtitle
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    Popup {
        id: pickerPopup
        objectName: "knowledgePickerPopup"
        x: 0
        y: -height - UI.Theme.space8
        width: 288
        padding: UI.Theme.space8
        focus: true
        modal: false
        dim: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: Qt.callLater(knowledgeList.forceActiveFocus)

        background: Rectangle {
            radius: UI.Theme.radiusLarge
            color: UI.Theme.surface
            border.color: UI.Theme.border
        }

        contentItem: ColumnLayout {
            spacing: UI.Theme.space4

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: UI.Theme.space8
                Layout.rightMargin: UI.Theme.space4

                Label {
                    Layout.fillWidth: true
                    text: qsTr("知识库")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    font.weight: Font.DemiBold
                }

                Button {
                    objectName: "knowledgePickerClearButton"
                    text: qsTr("清空")
                    flat: true
                    visible: root.selectedCount > 0
                    onClicked: root.clearAll()
                }
            }

            Label {
                Layout.fillWidth: true
                Layout.margins: UI.Theme.space8
                visible: root.choices.length === 0
                text: qsTr("还没有知识库。先去 设置 → 知识库 创建并导入文档。")
                color: UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
            }

            ListView {
                id: knowledgeList
                objectName: "knowledgePickerList"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(360, contentHeight)
                visible: root.choices.length > 0
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: root.choices
                activeFocusOnTab: true

                delegate: ItemDelegate {
                    id: knowledgeRow
                    required property int index
                    required property var modelData

                    width: knowledgeList.width
                    height: UI.Theme.controlHeightLarge
                    hoverEnabled: true

                    onClicked: root.toggle(modelData.id)

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: knowledgeRow.hovered
                               ? UI.Theme.surfaceHover : "transparent"
                    }

                    contentItem: RowLayout {
                        spacing: UI.Theme.space8

                        Rectangle {
                            Layout.preferredWidth: 16
                            Layout.preferredHeight: 16
                            radius: 3
                            color: root.isSelected(knowledgeRow.modelData.id)
                                   ? UI.Theme.accent : "transparent"
                            border.color: root.isSelected(knowledgeRow.modelData.id)
                                    ? UI.Theme.accent : UI.Theme.borderStrong
                            Label {
                                anchors.centerIn: parent
                                visible: root.isSelected(knowledgeRow.modelData.id)
                                text: "✓"
                                color: UI.Theme.surface
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            Label {
                                Layout.fillWidth: true
                                text: knowledgeRow.modelData.name
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                elide: Text.ElideRight
                            }

                            Label {
                                Layout.fillWidth: true
                                text: knowledgeRow.modelData.embeddingModel || ""
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Space || event.key === Qt.Key_Return
                            || event.key === Qt.Key_Enter) {
                        if (currentIndex >= 0 && currentIndex < root.choices.length)
                            root.toggle(root.choices[currentIndex].id)
                        event.accepted = true
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                Layout.margins: UI.Theme.space8
                visible: root.choices.length > 0
                text: qsTr("选择对当前会话生效，会自动检索并注入回答。")
                color: UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
            }
        }
    }
}
