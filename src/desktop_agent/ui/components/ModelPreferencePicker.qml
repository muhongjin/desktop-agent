pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

FocusScope {
    id: root

    signal modelSelected(string value)
    signal thinkingSelected(string value)
    signal configureModelsRequested()

    property var modelChoices: []
    property string selectedModel: ""
    property string thinkingStrength: "medium"
    readonly property bool hasConfiguredModels: modelChoices.length > 0
            && modelChoices[0].value !== ""
    readonly property bool popupOpen: preferencePopup.opened
    readonly property string modelName: selectedModelName()
    readonly property string thinkingName: thinkingLabel(thinkingStrength)
    readonly property string summaryText: (modelName.length > 0 ? modelName : qsTr("选择模型"))
            + "  " + thinkingName

    implicitWidth: Math.min(280, Math.max(148, summaryMetrics.advanceWidth + 48))
    implicitHeight: UI.Theme.controlHeight

    function selectedModelName() {
        for (let index = 0; index < modelChoices.length; index++) {
            const choice = modelChoices[index]
            if (choice.value !== selectedModel)
                continue
            const label = String(choice.display || "")
            const separator = label.lastIndexOf(" · ")
            return separator >= 0 ? label.substring(0, separator) : label
        }
        const separator = selectedModel.indexOf(":")
        return separator >= 0 ? selectedModel.substring(separator + 1) : selectedModel
    }

    function thinkingLabel(value) {
        if (value === "low")
            return qsTr("低")
        if (value === "high")
            return qsTr("高")
        return qsTr("中")
    }

    function selectedModelIndex() {
        for (let index = 0; index < modelChoices.length; index++) {
            if (modelChoices[index].value === selectedModel)
                return index
        }
        return modelChoices.length > 0 ? 0 : -1
    }

    function thinkingIndex() {
        return thinkingStrength === "low" ? 0 : thinkingStrength === "high" ? 2 : 1
    }

    function openPanel(panel) {
        preferencePopup.activePanel = panel
        if (!preferencePopup.opened)
            preferencePopup.open()
        Qt.callLater(() => {
            if (panel === "models") {
                modelChoiceList.currentIndex = selectedModelIndex()
                modelChoiceList.forceActiveFocus()
            } else {
                thinkingChoiceList.currentIndex = thinkingIndex()
                thinkingChoiceList.forceActiveFocus()
            }
        })
    }

    function chooseModel(index) {
        if (index < 0 || index >= modelChoices.length)
            return
        const value = String(modelChoices[index].value || "")
        preferencePopup.close()
        modelSelector.forceActiveFocus()
        if (value.length > 0)
            root.modelSelected(value)
        else
            root.configureModelsRequested()
    }

    function chooseThinking(index) {
        const values = ["low", "medium", "high"]
        if (index < 0 || index >= values.length)
            return
        preferencePopup.close()
        modelSelector.forceActiveFocus()
        root.thinkingSelected(values[index])
    }

    TextMetrics {
        id: summaryMetrics
        text: root.summaryText
        font.family: UI.Theme.fontFamily
        font.pixelSize: UI.Theme.fontBody
        font.weight: Font.Medium
    }

    Button {
        id: modelSelector
        objectName: "modelSelector"
        anchors.fill: parent
        activeFocusOnTab: true
        Accessible.name: qsTr("模型与推理强度")
        Accessible.description: root.summaryText
        onClicked: {
            if (preferencePopup.opened)
                preferencePopup.close()
            else {
                preferencePopup.activePanel = ""
                preferencePopup.open()
            }
        }

        background: Rectangle {
            radius: UI.Theme.radiusMedium
            color: modelSelector.down ? UI.Theme.surfacePressed
                    : modelSelector.hovered || preferencePopup.opened
                      ? UI.Theme.surfaceHover : "transparent"
            border.width: modelSelector.visualFocus ? UI.Theme.focusWidth : 1
            border.color: modelSelector.visualFocus ? UI.Theme.focus : "transparent"
        }

        contentItem: RowLayout {
            spacing: UI.Theme.space8

            Label {
                Layout.fillWidth: true
                text: root.summaryText
                color: root.selectedModel.length > 0
                        ? UI.Theme.textPrimary : UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.Medium
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }

            Label {
                text: preferencePopup.opened ? "⌃" : "⌄"
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontSubtitle
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    Popup {
        id: preferencePopup
        objectName: "modelPreferencePopup"
        property string activePanel: ""
        property int mainPanelWidth: 248
        property int detailPanelWidth: 292

        x: 0
        y: -height - UI.Theme.space8
        width: popupContent.implicitWidth
        height: popupContent.implicitHeight
        padding: 0
        focus: true
        modal: false
        dim: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: Qt.callLater(modelMenuButton.forceActiveFocus)
        onClosed: activePanel = ""

        background: Item {}

        contentItem: Item {
            id: popupContent
            implicitWidth: preferencePopup.mainPanelWidth
                    + (preferencePopup.activePanel.length > 0
                       ? UI.Theme.space8 + preferencePopup.detailPanelWidth : 0)
            implicitHeight: Math.max(mainPanel.implicitHeight,
                                     detailPanelLoader.implicitHeight)

            Item {
                width: preferencePopup.mainPanelWidth
                height: popupContent.implicitHeight

                Rectangle {
                    id: mainPanel
                    objectName: "modelPreferenceMainPanel"
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    implicitHeight: mainColumn.implicitHeight + UI.Theme.space8 * 2
                    height: implicitHeight
                    radius: UI.Theme.radiusLarge
                    color: UI.Theme.surface
                    border.color: UI.Theme.border

                    ColumnLayout {
                        id: mainColumn
                        anchors.fill: parent
                        anchors.margins: UI.Theme.space8
                        spacing: 0

                        Button {
                            id: modelMenuButton
                            objectName: "modelMenuButton"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            activeFocusOnTab: true
                            Accessible.name: qsTr("模型") + " "
                                    + (root.modelName.length > 0
                                       ? root.modelName : qsTr("未选择"))
                            onClicked: root.openPanel("models")

                            Keys.onPressed: event => {
                                if (event.key === Qt.Key_Right) {
                                    root.openPanel("models")
                                } else if (event.key === Qt.Key_Down
                                           || event.key === Qt.Key_End) {
                                    thinkingMenuButton.forceActiveFocus()
                                } else {
                                    return
                                }
                                event.accepted = true
                            }

                            background: Rectangle {
                                radius: UI.Theme.radiusMedium
                                color: preferencePopup.activePanel === "models"
                                        ? UI.Theme.surfacePressed
                                        : modelMenuButton.down ? UI.Theme.surfacePressed
                                        : modelMenuButton.hovered ? UI.Theme.surfaceHover
                                        : "transparent"
                                border.width: modelMenuButton.visualFocus
                                              ? UI.Theme.focusWidth : 0
                                border.color: UI.Theme.focus
                            }

                            contentItem: RowLayout {
                                spacing: UI.Theme.space8

                                Label {
                                    Layout.fillWidth: true
                                    text: qsTr("模型")
                                    color: UI.Theme.textPrimary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                    font.weight: Font.DemiBold
                                }

                                Label {
                                    Layout.maximumWidth: 120
                                    text: root.modelName.length > 0
                                            ? root.modelName : qsTr("未选择")
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                    elide: Text.ElideRight
                                }

                                Label {
                                    text: "›"
                                    color: UI.Theme.textMuted
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: 20
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.leftMargin: UI.Theme.space8
                            Layout.rightMargin: UI.Theme.space8
                            Layout.preferredHeight: 1
                            color: UI.Theme.border
                        }

                        Button {
                            id: thinkingMenuButton
                            objectName: "thinkingSelector"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            activeFocusOnTab: true
                            Accessible.name: qsTr("推理强度") + " " + root.thinkingName
                            onClicked: root.openPanel("thinking")

                            Keys.onPressed: event => {
                                if (event.key === Qt.Key_Right) {
                                    root.openPanel("thinking")
                                } else if (event.key === Qt.Key_Up
                                           || event.key === Qt.Key_Home) {
                                    modelMenuButton.forceActiveFocus()
                                } else {
                                    return
                                }
                                event.accepted = true
                            }

                            background: Rectangle {
                                radius: UI.Theme.radiusMedium
                                color: preferencePopup.activePanel === "thinking"
                                        ? UI.Theme.surfacePressed
                                        : thinkingMenuButton.down ? UI.Theme.surfacePressed
                                        : thinkingMenuButton.hovered ? UI.Theme.surfaceHover
                                        : "transparent"
                                border.width: thinkingMenuButton.visualFocus
                                              ? UI.Theme.focusWidth : 0
                                border.color: UI.Theme.focus
                            }

                            contentItem: RowLayout {
                                spacing: UI.Theme.space8

                                Label {
                                    Layout.fillWidth: true
                                    text: qsTr("推理强度")
                                    color: UI.Theme.textPrimary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                    font.weight: Font.DemiBold
                                }

                                Label {
                                    text: root.thinkingName
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                }

                                Label {
                                    text: "›"
                                    color: UI.Theme.textMuted
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: 20
                                }
                            }
                        }
                    }
                }
            }

            Loader {
                id: detailPanelLoader
                objectName: "modelPreferenceDetailPanel"
                x: preferencePopup.mainPanelWidth + UI.Theme.space8
                active: preferencePopup.activePanel.length > 0
                visible: active
                sourceComponent: preferencePopup.activePanel === "models"
                                 ? modelPanel : thinkingPanel
            }
        }
    }

    Component {
        id: modelPanel

        Rectangle {
            objectName: "modelChoicePanel"
            width: preferencePopup.detailPanelWidth
            implicitHeight: Math.min(320,
                    Math.max(56, modelChoiceList.contentHeight + UI.Theme.space8 * 2))
            height: implicitHeight
            radius: UI.Theme.radiusLarge
            color: UI.Theme.surface
            border.color: UI.Theme.border

            ListView {
                id: modelChoiceList
                objectName: "modelChoiceList"
                anchors.fill: parent
                anchors.margins: UI.Theme.space8
                clip: true
                model: root.modelChoices
                currentIndex: root.selectedModelIndex()
                activeFocusOnTab: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {
                    policy: modelChoiceList.contentHeight > modelChoiceList.height
                            ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                }

                delegate: ItemDelegate {
                    id: modelChoice
                    required property int index
                    required property var modelData
                    width: modelChoiceList.width
                    height: UI.Theme.controlHeightLarge
                    highlighted: ListView.isCurrentItem
                    hoverEnabled: true
                    Accessible.name: String(modelData.display || "")
                    Accessible.selected: String(modelData.value || "") === root.selectedModel
                    onHoveredChanged: {
                        if (hovered)
                            modelChoiceList.currentIndex = index
                    }
                    onClicked: root.chooseModel(index)

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: modelChoice.highlighted || modelChoice.hovered
                                ? UI.Theme.surfaceHover : "transparent"
                    }

                    contentItem: RowLayout {
                        spacing: UI.Theme.space8

                        Label {
                            Layout.fillWidth: true
                            text: String(modelChoice.modelData.display || "")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                        }

                        Label {
                            visible: String(modelChoice.modelData.value || "")
                                     === root.selectedModel
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
                        currentIndex = count > 0 ? 0 : -1
                    } else if (event.key === Qt.Key_End) {
                        currentIndex = count - 1
                    } else if (event.key === Qt.Key_Return
                               || event.key === Qt.Key_Enter
                               || event.key === Qt.Key_Space) {
                        root.chooseModel(currentIndex)
                    } else if (event.key === Qt.Key_Left
                               || event.key === Qt.Key_Escape) {
                        preferencePopup.activePanel = ""
                        modelMenuButton.forceActiveFocus()
                    } else {
                        return
                    }
                    event.accepted = true
                }
            }
        }
    }

    Component {
        id: thinkingPanel

        Rectangle {
            objectName: "thinkingChoicePanel"
            width: 208
            implicitHeight: thinkingChoiceList.contentHeight + UI.Theme.space8 * 2
            height: implicitHeight
            radius: UI.Theme.radiusLarge
            color: UI.Theme.surface
            border.color: UI.Theme.border

            ListView {
                id: thinkingChoiceList
                objectName: "thinkingChoiceList"
                anchors.fill: parent
                anchors.margins: UI.Theme.space8
                model: [qsTr("低"), qsTr("中"), qsTr("高")]
                currentIndex: root.thinkingIndex()
                activeFocusOnTab: true

                delegate: ItemDelegate {
                    id: thinkingChoice
                    required property int index
                    required property string modelData
                    width: thinkingChoiceList.width
                    height: UI.Theme.controlHeightLarge
                    highlighted: ListView.isCurrentItem
                    hoverEnabled: true
                    Accessible.name: modelData
                    Accessible.selected: index === root.thinkingIndex()
                    onHoveredChanged: {
                        if (hovered)
                            thinkingChoiceList.currentIndex = index
                    }
                    onClicked: root.chooseThinking(index)

                    background: Rectangle {
                        radius: UI.Theme.radiusMedium
                        color: thinkingChoice.highlighted || thinkingChoice.hovered
                                ? UI.Theme.surfaceHover : "transparent"
                    }

                    contentItem: RowLayout {
                        spacing: UI.Theme.space8

                        Label {
                            Layout.fillWidth: true
                            text: thinkingChoice.modelData
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            font.weight: Font.Medium
                        }

                        Label {
                            visible: thinkingChoice.index === root.thinkingIndex()
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
                        root.chooseThinking(currentIndex)
                    } else if (event.key === Qt.Key_Left
                               || event.key === Qt.Key_Escape) {
                        preferencePopup.activePanel = ""
                        thinkingMenuButton.forceActiveFocus()
                    } else {
                        return
                    }
                    event.accepted = true
                }
            }
        }
    }
}
