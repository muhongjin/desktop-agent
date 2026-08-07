import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

FocusScope {
    id: root

    signal sendRequested(string text)
    signal stopRequested()
    signal modelSelected(string value)
    signal thinkingSelected(string value)
    signal executionModeSelected(string value)
    signal fullAccessChangedByUser(bool enabled)
    signal configureModelsRequested()

    property bool running: false
    property var modelChoices: []
    property string selectedModel: ""
    property string thinkingStrength: "medium"
    property string executionMode: "local"
    property bool fullAccess: false
    readonly property bool hasModel: selectedModel.length > 0
    readonly property bool hasConfiguredModels: modelChoices.length > 0
            && modelChoices[0].value !== ""
    readonly property bool popupOpen: modelSelector.popup.visible
            || thinkingSelector.popup.visible || executionModeSelector.popup.visible

    implicitHeight: fullAccess ? 190 : 154

    function focusEditor() {
        editor.forceActiveFocus()
    }

    function submit() {
        if (running || !hasModel || editor.inputMethodComposing
                || editor.text.trim().length === 0)
            return
        root.sendRequested(editor.text)
        editor.clear()
    }

    Rectangle {
        anchors.fill: parent
        color: UI.Theme.surface
        border.color: UI.Theme.border

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: UI.Theme.space16
            anchors.rightMargin: UI.Theme.space16
            anchors.topMargin: UI.Theme.space12
            anchors.bottomMargin: UI.Theme.space12
            spacing: UI.Theme.space8

            Rectangle {
                visible: root.fullAccess
                Layout.fillWidth: true
                Layout.preferredHeight: UI.Theme.controlHeight
                radius: UI.Theme.radiusMedium
                color: UI.Theme.warningSubtle
                border.color: UI.Theme.warning

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: UI.Theme.space12
                    anchors.rightMargin: UI.Theme.space4
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("完全访问已开启 · 仅限当前会话")
                        color: UI.Theme.warning
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontCaption
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Button {
                        id: fullAccessOffButton
                        objectName: "fullAccessOffButton"
                        text: qsTr("关闭")
                        flat: true
                        activeFocusOnTab: true
                        onClicked: root.fullAccessChangedByUser(false)

                        background: Rectangle {
                            radius: UI.Theme.radiusSmall
                            color: fullAccessOffButton.down ? UI.Theme.surfacePressed
                                  : fullAccessOffButton.hovered ? UI.Theme.surfaceHover
                                  : "transparent"
                            border.color: fullAccessOffButton.visualFocus
                                    ? UI.Theme.focus : "transparent"
                            border.width: fullAccessOffButton.visualFocus
                                    ? UI.Theme.focusWidth : 0
                        }

                        contentItem: Label {
                            text: fullAccessOffButton.text
                            color: UI.Theme.warning
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontCaption
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                TextArea {
                    id: editor
                    objectName: "messageInput"
                    activeFocusOnTab: true
                    placeholderText: !root.hasConfiguredModels
                            ? qsTr("配置模型后即可发送，也可以先输入草稿")
                            : !root.hasModel ? qsTr("选择模型后即可发送")
                                             : qsTr("输入消息，Ctrl+Enter 发送")
                    wrapMode: TextArea.Wrap
                    selectByKeyboard: true
                    selectByMouse: true
                    color: UI.Theme.textPrimary
                    placeholderTextColor: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontBody
                    padding: UI.Theme.space8

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: UI.Theme.background
                        border.color: editor.activeFocus ? UI.Theme.focus : UI.Theme.border
                        border.width: editor.activeFocus ? UI.Theme.focusWidth : 1
                    }

                    Keys.onPressed: event => {
                        const enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                        if (enter && event.modifiers === Qt.ControlModifier) {
                            if (!editor.inputMethodComposing)
                                root.submit()
                            event.accepted = true
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space8

                ComboBox {
                    id: modelSelector
                    objectName: "modelSelector"
                    Layout.preferredWidth: 190
                    Layout.minimumWidth: 140
                    model: root.modelChoices
                    textRole: "display"
                    valueRole: "value"
                    activeFocusOnTab: true
                    currentIndex: {
                        for (let index = 0; index < count; index++) {
                            if (valueAt(index) === root.selectedModel)
                                return index
                        }
                        return -1
                    }
                    displayText: currentIndex < 0 ? qsTr("选择模型") : currentText
                    onActivated: {
                        if (currentValue.length > 0)
                            root.modelSelected(currentValue)
                        else
                            root.configureModelsRequested()
                    }
                }

                ComboBox {
                    id: thinkingSelector
                    objectName: "thinkingSelector"
                    Layout.preferredWidth: 104
                    model: [qsTr("低思考"), qsTr("中思考"), qsTr("高思考")]
                    activeFocusOnTab: true
                    currentIndex: root.thinkingStrength === "low" ? 0
                            : root.thinkingStrength === "high" ? 2 : 1
                    onActivated: root.thinkingSelected(["low", "medium", "high"][currentIndex])
                }

                ComboBox {
                    id: executionModeSelector
                    objectName: "executionModeSelector"
                    Layout.preferredWidth: 104
                    model: ["none", "local"]
                    activeFocusOnTab: true
                    currentIndex: root.executionMode === "none" ? 0 : 1
                    onActivated: root.executionModeSelected(currentText)
                }

                CheckBox {
                    id: fullAccessToggle
                    objectName: "fullAccessToggle"
                    visible: !root.fullAccess
                    text: qsTr("完全访问")
                    checked: root.fullAccess
                    activeFocusOnTab: true
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("为当前会话开放工作区外访问；可随时关闭")
                    onClicked: root.fullAccessChangedByUser(checked)
                }

                Item {
                    Layout.fillWidth: true
                }

                Label {
                    visible: !root.hasModel && root.hasConfiguredModels
                    text: qsTr("请先选择模型")
                    color: UI.Theme.textSecondary
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                }

                Button {
                    id: configureModelsButton
                    objectName: "configureModelsButton"
                    visible: !root.hasConfiguredModels
                    text: qsTr("配置模型")
                    activeFocusOnTab: true
                    onClicked: root.configureModelsRequested()
                }

                Button {
                    id: stopButton
                    objectName: "stopButton"
                    visible: root.running
                    text: qsTr("停止")
                    activeFocusOnTab: true
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("停止当前响应 (Esc)")
                    onClicked: root.stopRequested()

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: stopButton.down ? UI.Theme.dangerSubtle
                              : stopButton.hovered ? UI.Theme.surfaceHover : UI.Theme.surface
                        border.color: stopButton.visualFocus ? UI.Theme.focus : UI.Theme.danger
                        border.width: stopButton.visualFocus ? UI.Theme.focusWidth : 1
                    }

                    contentItem: Label {
                        text: stopButton.text
                        color: UI.Theme.danger
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    id: sendButton
                    objectName: "sendButton"
                    visible: root.hasModel && !root.running
                    enabled: editor.text.trim().length > 0
                    text: qsTr("发送")
                    activeFocusOnTab: true
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("发送 (Ctrl+Enter)")
                    onClicked: root.submit()

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: !sendButton.enabled ? UI.Theme.surfacePressed
                              : sendButton.down ? UI.Theme.accentPressed
                              : sendButton.hovered ? UI.Theme.accentHover : UI.Theme.accent
                        border.color: sendButton.visualFocus ? UI.Theme.focus : "transparent"
                        border.width: sendButton.visualFocus ? UI.Theme.focusWidth : 0
                    }

                    contentItem: Label {
                        text: sendButton.text
                        color: sendButton.enabled ? UI.Theme.surface : UI.Theme.textMuted
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
}
