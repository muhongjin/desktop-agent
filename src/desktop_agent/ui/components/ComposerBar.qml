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
    signal knowledgeSelectionChanged(var ids)

    property bool running: false
    property var modelChoices: []
    property string selectedModel: ""
    property string thinkingStrength: "medium"
    property string executionMode: "local"
    property bool fullAccess: false
    property var knowledgeChoices: []
    property var knowledgeSelectedIds: []
    readonly property bool hasModel: selectedModel.length > 0
    readonly property bool hasConfiguredModels: modelChoices.length > 0
            && modelChoices[0].value !== ""
    readonly property bool popupOpen: preferencePicker.popupOpen
            || executionModePicker.popupOpen
            || knowledgePicker.popupOpen

    implicitHeight: 154

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

    function selectExecutionMode(value) {
        if (value === "all") {
            if (executionMode !== "local")
                root.executionModeSelected("local")
            if (!fullAccess)
                root.fullAccessChangedByUser(true)
            return
        }
        if (fullAccess)
            root.fullAccessChangedByUser(false)
        if (executionMode !== value)
            root.executionModeSelected(value)
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

                ModelPreferencePicker {
                    id: preferencePicker
                    objectName: "modelPreferencePicker"
                    Layout.preferredWidth: implicitWidth
                    Layout.minimumWidth: 148
                    Layout.maximumWidth: 280
                    modelChoices: root.modelChoices
                    selectedModel: root.selectedModel
                    thinkingStrength: root.thinkingStrength
                    onModelSelected: value => root.modelSelected(value)
                    onThinkingSelected: value => root.thinkingSelected(value)
                    onConfigureModelsRequested: root.configureModelsRequested()
                }

                ExecutionModePicker {
                    id: executionModePicker
                    objectName: "executionModePicker"
                    Layout.preferredWidth: implicitWidth
                    mode: root.fullAccess ? "all" : root.executionMode
                    onModeSelected: value => root.selectExecutionMode(value)
                }

                KnowledgePicker {
                    id: knowledgePicker
                    objectName: "knowledgePicker"
                    Layout.preferredWidth: implicitWidth
                    choices: root.knowledgeChoices
                    selectedIds: root.knowledgeSelectedIds
                    onSelectionChanged: ids => root.knowledgeSelectionChanged(ids)
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
