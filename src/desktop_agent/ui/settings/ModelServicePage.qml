import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    id: root
    objectName: "modelServicePage"

    property string mode: "list"
    property string editingConfigId: ""
    property string editingProviderId: "openai"
    property string editingApiProtocol: "responses"
    property var selectedModels: []
    property var modelEntries: []
    property string selectedModelId: ""
    property string settingsModelId: ""
    property string settingsCapabilities: ""
    property int settingsContextWindow: 0
    property string settingsContextText: ""
    property int settingsOutputTokens: 0
    property bool settingsContextKnown: false
    property bool settingsDefaultContextKnown: false
    property int settingsDefaultContext: 0
    property int settingsInitialContextWindow: 0
    property string settingsInitialContextText: ""
    property string settingsContextSource: "unknown"
    property string settingsApiProtocol: "responses"
    property var discoveredModels: []
    property string discoveryRequestId: ""
    property bool discovering: false
    property string statusKind: ""
    property string statusMessage: ""
    readonly property var currentPreset: presetById(editingProviderId)
    readonly property var filteredModels: {
        const query = discoverySearch.text.trim().toLowerCase()
        if (query.length === 0)
            return discoveredModels
        const matches = []
        for (let index = 0; index < discoveredModels.length; index++) {
            const modelId = String(discoveredModels[index])
            if (modelId.toLowerCase().includes(query))
                matches.push(modelId)
        }
        return matches
    }

    function presetById(providerId) {
        for (let index = 0; index < modelService.providerPresets.length; index++) {
            const preset = modelService.providerPresets[index]
            if (preset.id === providerId)
                return preset
        }
        return modelService.providerPresets[0]
    }

    function selectPreset(preset) {
        editingProviderId = preset.id
        providerNameInput.text = preset.displayName
        baseUrlInput.text = preset.baseUrl
        editingApiProtocol = preset.apiProtocol
        manualModelInput.placeholderText = preset.modelHints.join(", ")
        clearDiscovery()
        modelService.ensureProviderMetadata(preset.id)
    }

    function beginCreate() {
        mode = "editor"
        editingConfigId = ""
        selectedModels = []
        modelEntries = []
        selectedModelId = ""
        apiKeyInput.clear()
        timeoutInput.text = "120"
        selectPreset(modelService.providerPresets[0])
        statusKind = ""
        statusMessage = ""
    }

    function beginEdit(config) {
        mode = "editor"
        editingConfigId = config.id
        editingProviderId = config.providerId
        providerNameInput.text = config.displayName
        baseUrlInput.text = config.baseUrl
        apiKeyInput.clear()
        timeoutInput.text = String(config.timeout)
        editingApiProtocol = config.apiProtocol
        modelService.ensureProviderMetadata(config.providerId)
        selectedModels = config.models.slice()
        modelEntries = config.modelEntries && config.modelEntries.length > 0
                ? config.modelEntries.slice() : config.models.map(function(modelId) {
                    return {id: modelId, enabled: true, capabilities: "", contextWindow: 0,
                        outputTokens: 0, contextKnown: false, contextSource: "unknown",
                        apiProtocol: config.apiProtocol}
                })
        selectedModelId = ""
        manualModelInput.clear()
        manualModelInput.placeholderText = currentPreset.modelHints.join(", ")
        root.applyMetadataToEntries(config.providerId)
        clearDiscovery()
        statusKind = ""
        statusMessage = ""
    }

    function cancelEditor() {
        mode = "list"
        clearDiscovery()
        statusKind = ""
        statusMessage = ""
    }

    function clearDiscovery() {
        discoveredModels = []
        discoverySearch.clear()
        discovering = false
        discoveryRequestId = ""
    }

    function hasModel(modelId) {
        return selectedModels.indexOf(modelId) >= 0
    }

    function setModelSelected(modelId, selected, autoProbe) {
        autoProbe = autoProbe === true
        const values = selectedModels.slice()
        const index = values.indexOf(modelId)
        if (selected && index < 0)
            values.push(modelId)
        else if (!selected && index >= 0)
            values.splice(index, 1)
        selectedModels = values
        if (selected) {
            let exists = false
            for (let entry of modelEntries) {
                if (entry.id === modelId) { exists = true; break }
            }
            if (!exists) {
                const entries = modelEntries.slice()
                const metadata = modelService.metadataForModel(root.editingProviderId, modelId)
                const hasContext = metadata && metadata.context !== undefined
                        && metadata.context !== null && Number(metadata.context) > 0
                entries.push({id: modelId, enabled: !autoProbe, testing: autoProbe,
                    autoProbe: autoProbe,
                    capabilities: "", contextWindow: hasContext ? Number(metadata.context) : 0,
                    outputTokens: metadata && metadata.output !== undefined
                            && metadata.output !== null ? Number(metadata.output) : 0,
                    contextKnown: hasContext,
                    contextSource: hasContext ? "models.dev" : "unknown",
                    apiProtocol: root.editingApiProtocol})
                modelEntries = entries
            }
            if (autoProbe)
                root.testEntry(modelId)
        } else {
            modelEntries = modelEntries.filter(function(entry) { return entry.id !== modelId })
            if (selectedModelId === modelId)
                selectedModelId = modelEntries.length > 0 ? modelEntries[0].id : ""
        }
    }

    function entryFor(modelId) {
        for (let entry of modelEntries) {
            if (entry.id === modelId)
                return entry
        }
        return null
    }

    function updateEntry(modelId, values) {
        const entries = modelEntries.slice()
        for (let index = 0; index < entries.length; index++) {
            if (entries[index].id === modelId) {
                entries[index] = Object.assign({}, entries[index], values)
                modelEntries = entries
                return
            }
        }
    }

    function openModelSettings(modelId) {
        const entry = entryFor(modelId)
        if (!entry)
            return
        settingsModelId = modelId
        settingsCapabilities = entry.capabilities || ""
        settingsContextKnown = entry.contextKnown === true || Number(entry.contextWindow || 0) > 0
        settingsContextText = settingsContextKnown ? String(entry.contextWindow) : ""
        settingsContextWindow = settingsContextKnown ? Number(entry.contextWindow) : 0
        settingsOutputTokens = Number(entry.outputTokens || 0)
        settingsContextSource = entry.contextSource || "unknown"
        settingsInitialContextWindow = settingsContextWindow
        settingsInitialContextText = settingsContextText
        const metadata = modelService.metadataForModel(root.editingProviderId, modelId)
        settingsDefaultContextKnown = metadata && metadata.context !== undefined
                && metadata.context !== null && Number(metadata.context) > 0
        settingsDefaultContext = settingsDefaultContextKnown ? Number(metadata.context) : 0
        settingsApiProtocol = entry.apiProtocol || root.editingApiProtocol
        selectedModelId = modelId
        modelSettingsDialog.open()
    }

    function saveModelSettings() {
        const normalizedText = modelContextInput.text.trim()
        const hasContext = normalizedText.length > 0 && Number(normalizedText) > 0
        const contextWindow = hasContext ? Number(normalizedText) : 0
        const contextChanged = normalizedText !== settingsInitialContextText
        updateEntry(settingsModelId, {
            capabilities: settingsCapabilities,
            contextWindow: contextWindow,
            contextKnown: hasContext,
            contextSource: contextChanged ? (hasContext ? "manual" : "unknown")
                                           : settingsContextSource,
            outputTokens: settingsOutputTokens,
            apiProtocol: settingsApiProtocol
        })
        selectedModelId = ""
        modelSettingsDialog.close()
    }

    function modelSettingsPayload() {
        const values = {}
        for (let entry of modelEntries) {
            values[entry.id] = {
                enabled: entry.enabled !== false,
                capabilities: entry.capabilities || "",
                context: entry.contextKnown === true ? Number(entry.contextWindow || 0) : null,
                output: entry.outputTokens ? Number(entry.outputTokens) : null,
                context_source: entry.contextSource || "unknown",
                api_protocol: entry.apiProtocol || root.editingApiProtocol
            }
        }
        return values
    }

    function testEntry(modelId) {
        const requestId = (root.editingConfigId || "new") + ":" + modelId + ":" + Date.now()
        updateEntry(modelId, {testing: true, testState: "testing", testMessage: ""})
        modelService.probeModel(requestId, root.editingProviderId, baseUrlInput.text,
                                apiKeyInput.text, modelId, parseInt(timeoutInput.text || "120"),
                                (entryFor(modelId) || {}).apiProtocol || root.editingApiProtocol,
                                root.editingConfigId)
    }

    function addEditorModel() {
        const modelId = manualModelInput.text.trim()
        if (!modelId)
            return
        setModelSelected(modelId, true, false)
        root.testEntry(modelId)
        manualModelInput.clear()
    }

    function discover() {
        modelService.ensureProviderMetadata(editingProviderId)
        discoveryRequestId = editingConfigId.length > 0
                ? editingConfigId : "new:" + editingProviderId
        discovering = true
        discoveredModels = []
        discoverySearch.clear()
        statusKind = "busy"
        statusMessage = qsTr("正在读取模型列表。")
        modelService.discoverModels(
            discoveryRequestId,
            editingConfigId,
            editingProviderId,
            baseUrlInput.text,
            apiKeyInput.text,
            parseInt(timeoutInput.text || "120")
        )
    }

    function saveEditor() {
        if (!providerNameInput.text.trim() || !baseUrlInput.text.trim()) {
            statusKind = "error"
            statusMessage = qsTr("请填写配置名称和 Base URL。")
            return
        }
        modelService.saveProviderConfig(
            editingConfigId,
            editingProviderId,
            providerNameInput.text,
            baseUrlInput.text,
            apiKeyInput.text,
            parseInt(timeoutInput.text || "120"),
            "",
            selectedModels,
            root.modelSettingsPayload()
        )
        apiKeyInput.clear()
        mode = "list"
        statusKind = "success"
        statusMessage = qsTr("配置已保存。")
    }

    function applyMetadataToEntries(providerType) {
        if (providerType !== root.editingProviderId)
            return
        const entries = modelEntries.slice()
        let changed = false
        for (let index = 0; index < entries.length; index++) {
            const entry = entries[index]
            if (entry.contextSource === "manual")
                continue
            const metadata = modelService.metadataForModel(providerType, entry.id)
            if (!metadata)
                continue
            const hasContext = metadata.context !== undefined && metadata.context !== null
                    && Number(metadata.context) > 0
            const hasOutput = metadata.output !== undefined && metadata.output !== null
            if (!hasContext && !hasOutput)
                continue
            entries[index] = Object.assign({}, entry,
                hasContext ? {contextWindow: Number(metadata.context), contextKnown: true,
                    contextSource: "models.dev"} : {},
                hasOutput ? {outputTokens: Number(metadata.output)} : {})
            changed = true
        }
        if (changed)
            modelEntries = entries
    }

    Shortcut {
        sequence: "Ctrl+S"
        enabled: root.visible && root.mode === "editor"
        onActivated: root.saveEditor()
    }

    ScrollView {
        id: pageScroll
        anchors.fill: parent
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            x: Math.max(UI.Theme.space32, (pageScroll.availableWidth - width) / 2)
            width: Math.max(360, Math.min(UI.Theme.contentMaxWidth,
                                          pageScroll.availableWidth - UI.Theme.space32 * 2))
            spacing: UI.Theme.space20

            Item { Layout.preferredHeight: UI.Theme.space12 }

            ColumnLayout {
                id: listPane
                visible: root.mode === "list"
                Layout.fillWidth: true
                spacing: UI.Theme.space20

                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: UI.Theme.space4

                        Label {
                            text: qsTr("模型服务")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontTitle
                            font.weight: Font.DemiBold
                        }

                        Label {
                            text: qsTr("管理已保存的服务配置和可用模型。")
                            color: UI.Theme.textSecondary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                        }
                    }

                    SettingsButton {
                        id: addProviderButton
                        objectName: "addProviderButton"
                        text: qsTr("+ 新增服务")
                        primary: true
                        onClicked: root.beginCreate()
                    }
                }

                Rectangle {
                    visible: root.statusMessage.length > 0
                            && root.statusKind === "success"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    radius: UI.Theme.radiusMedium
                    color: UI.Theme.successSubtle

                    Label {
                        anchors.fill: parent
                        anchors.margins: UI.Theme.space12
                        text: root.statusMessage
                        color: UI.Theme.success
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                ColumnLayout {
                    id: providerConfigList
                    objectName: "providerConfigList"
                    Layout.fillWidth: true
                    spacing: UI.Theme.space12

                    Repeater {
                        id: providerConfigRepeater
                        objectName: "providerConfigRepeater"
                        model: modelService.providerConfigs

                        delegate: Rectangle {
                            id: providerCard
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: cardContent.implicitHeight + UI.Theme.space32
                            radius: UI.Theme.radiusLarge
                            color: UI.Theme.surface
                            border.color: UI.Theme.border
                            border.width: 1

                            Rectangle {
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                width: 5
                                radius: UI.Theme.radiusLarge
                                color: providerCard.modelData.accentColor
                            }

                            ColumnLayout {
                                id: cardContent
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: UI.Theme.space16
                                anchors.leftMargin: UI.Theme.space20
                                spacing: UI.Theme.space12

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: UI.Theme.space12

                                    Rectangle {
                                        Layout.preferredWidth: 36
                                        Layout.preferredHeight: 36
                                        radius: UI.Theme.radiusMedium
                                        color: providerCard.modelData.accentColor

                                        Label {
                                            anchors.centerIn: parent
                                            text: providerCard.modelData.mark
                                            color: "#ffffff"
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontSubtitle
                                            font.weight: Font.Bold
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 0

                                        Label {
                                            text: providerCard.modelData.displayName
                                            color: UI.Theme.textPrimary
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontSubtitle
                                            font.weight: Font.DemiBold
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }

                                        Label {
                                            text: providerCard.modelData.providerName + "  ·  "
                                                  + providerCard.modelData.baseUrl
                                            color: UI.Theme.textMuted
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontCaption
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Label {
                                        text: qsTr("%1 秒").arg(providerCard.modelData.timeout)
                                        color: UI.Theme.textSecondary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                    }

                                    SettingsButton {
                                        text: qsTr("编辑")
                                        onClicked: root.beginEdit(providerCard.modelData)
                                    }

                                    SettingsButton {
                                        objectName: "deleteProviderButton"
                                        text: qsTr("删除")
                                        destructive: true
                                        onClicked: modelService.deleteProviderConfig(providerCard.modelData.id)
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 1
                                    color: UI.Theme.border
                                }

                                Label {
                                    text: qsTr("模型  %1").arg(providerCard.modelData.models.length)
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontCaption
                                    font.weight: Font.DemiBold
                                }

                                Label {
                                    visible: providerCard.modelData.models.length === 0
                                    text: qsTr("尚未添加模型")
                                    color: UI.Theme.textMuted
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                }

                                Repeater {
                                    model: providerCard.modelData.modelEntries

                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: UI.Theme.controlHeight
                                        spacing: UI.Theme.space8

                                        Rectangle {
                                            Layout.preferredWidth: 8
                                            Layout.preferredHeight: 8
                                            radius: 4
                                            color: modelData.enabled ? UI.Theme.success : UI.Theme.disabled
                                        }

                                        Label {
                                            text: modelData.id
                                            color: modelData.enabled ? UI.Theme.textPrimary : UI.Theme.textMuted
                                            font.family: UI.Theme.monoFontFamily
                                            font.pixelSize: UI.Theme.fontBody
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }

                                        Label {
                                            text: modelData.apiProtocol === "responses" ? qsTr("Responses")
                                                                                         : qsTr("Chat")
                                            color: UI.Theme.textMuted
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontCaption
                                        }
                                    }
                                }

                            }
                        }
                    }

                    Rectangle {
                        visible: modelService.providerConfigs.length === 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        radius: UI.Theme.radiusLarge
                        color: UI.Theme.surface
                        border.color: UI.Theme.border
                        border.width: 1

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: UI.Theme.space8

                            Label {
                                text: qsTr("还没有模型服务")
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontSubtitle
                                font.weight: Font.DemiBold
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Label {
                                text: qsTr("新增一个服务配置，然后添加需要使用的模型。")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                id: editorPane
                visible: root.mode === "editor"
                Layout.fillWidth: true
                spacing: UI.Theme.space20

                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space12

                    ToolButton {
                        text: "‹"
                        font.pixelSize: 24
                        activeFocusOnTab: true
                        ToolTip.visible: hovered || activeFocus
                        ToolTip.text: qsTr("返回服务列表")
                        onClicked: root.cancelEditor()
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Label {
                            text: root.editingConfigId.length > 0
                                    ? qsTr("编辑模型服务") : qsTr("新增模型服务")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontTitle
                            font.weight: Font.DemiBold
                        }

                        Label {
                            text: qsTr("密钥仅保存在 Windows 凭据管理器中。")
                            color: UI.Theme.textMuted
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontCaption
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("提供商类型")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    Flow {
                        id: providerPresetGrid
                        objectName: "providerPresetGrid"
                        Layout.fillWidth: true
                        spacing: UI.Theme.space8

                        Repeater {
                            model: modelService.providerPresets

                            delegate: Button {
                                id: presetButton
                                required property var modelData
                                width: 168
                                height: 48
                                activeFocusOnTab: true
                                onClicked: root.selectPreset(modelData)

                                contentItem: RowLayout {
                                    spacing: UI.Theme.space8

                                    Rectangle {
                                        Layout.preferredWidth: 28
                                        Layout.preferredHeight: 28
                                        radius: UI.Theme.radiusSmall
                                        color: presetButton.modelData.accentColor

                                        Label {
                                            anchors.centerIn: parent
                                            text: presetButton.modelData.mark
                                            color: "#ffffff"
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontBody
                                            font.weight: Font.Bold
                                        }
                                    }

                                    Label {
                                        text: presetButton.modelData.displayName
                                        color: UI.Theme.textPrimary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontBody
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }
                                }

                                background: Rectangle {
                                    radius: UI.Theme.radiusMedium
                                    color: presetButton.down ? UI.Theme.surfacePressed
                                         : presetButton.hovered ? UI.Theme.surfaceHover
                                         : UI.Theme.surface
                                    border.width: root.editingProviderId
                                            === presetButton.modelData.id ? 2 : 1
                                    border.color: root.editingProviderId
                                            === presetButton.modelData.id
                                            ? presetButton.modelData.accentColor
                                            : UI.Theme.border
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: UI.Theme.space8

                        Label {
                            text: qsTr("配置名称")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            font.weight: Font.DemiBold
                        }

                        SettingsTextField {
                            id: providerNameInput
                            objectName: "providerNameInput"
                            Layout.fillWidth: true
                            placeholderText: qsTr("例如：工作用 OpenAI")
                        }
                    }

                    ColumnLayout {
                        Layout.preferredWidth: 150
                        spacing: UI.Theme.space8

                        Label {
                            text: qsTr("超时时间（秒）")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            font.weight: Font.DemiBold
                        }

                        SettingsTextField {
                            id: timeoutInput
                            objectName: "providerTimeoutInput"
                            Layout.fillWidth: true
                            text: "120"
                            inputMethodHints: Qt.ImhDigitsOnly
                            validator: IntValidator { bottom: 1; top: 600 }
                        }
                    }
                }

                Item {
                    objectName: "apiProtocolSelector"
                    visible: false
                    width: 0
                    height: 0
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("Base URL")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    SettingsTextField {
                        id: baseUrlInput
                        objectName: "baseUrlInput"
                        Layout.fillWidth: true
                        placeholderText: qsTr("https://example.com/v1")
                        inputMethodHints: Qt.ImhUrlCharactersOnly
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("API Key")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    SettingsTextField {
                        id: apiKeyInput
                        objectName: "apiKeyInput"
                        Layout.fillWidth: true
                        echoMode: TextInput.Password
                        placeholderText: qsTr("留空则保留已保存的密钥")
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: modelEditorContent.implicitHeight + UI.Theme.space32
                    radius: UI.Theme.radiusLarge
                    color: UI.Theme.surface
                    border.color: UI.Theme.border
                    border.width: 1

                    ColumnLayout {
                        id: modelEditorContent
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: UI.Theme.space16
                        spacing: UI.Theme.space12

                        RowLayout {
                            Layout.fillWidth: true

                            Label {
                                text: qsTr("已选择的模型")
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontSubtitle
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                            }

                            Label {
                                text: qsTr("%1 个").arg(root.selectedModels.length)
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                            }
                        }

                        Repeater {
                            model: root.modelEntries

                            delegate: RowLayout {
                                required property var modelData
                                id: modelEditorRow
                                Layout.fillWidth: true
                                Layout.preferredHeight: UI.Theme.controlHeight
                                spacing: UI.Theme.space4

                                Label {
                                    text: modelData.id
                                    color: modelData.enabled ? UI.Theme.textPrimary : UI.Theme.textMuted
                                    font.family: UI.Theme.monoFontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                Label {
                                    text: modelData.testing ? qsTr("测试中") : modelData.testMessage
                                    color: modelData.testing ? UI.Theme.textSecondary
                                          : modelData.testState === "error" ? UI.Theme.danger : UI.Theme.success
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontCaption
                                    Layout.preferredWidth: 76
                                    horizontalAlignment: Text.AlignRight
                                    opacity: modelData.testing
                                             || String(modelData.testMessage || "").length > 0 ? 1 : 0
                                    elide: Text.ElideRight
                                }

                                Switch {
                                    id: enabledSwitch
                                    objectName: "modelEnabledSwitch"
                                    checked: modelData.enabled
                                    enabled: !modelData.testing
                                    implicitWidth: 42
                                    implicitHeight: 32
                                    activeFocusOnTab: true
                                    ToolTip.visible: hovered || activeFocus
                                    ToolTip.text: modelData.enabled ? qsTr("停用模型") : qsTr("启用模型")
                                    contentItem: Item {}
                                    indicator: Rectangle {
                                        x: (enabledSwitch.width - width) / 2
                                        y: (enabledSwitch.height - height) / 2
                                        width: 36
                                        height: 20
                                        radius: 10
                                        color: enabledSwitch.checked ? UI.Theme.accent
                                              : enabledSwitch.hovered ? UI.Theme.surfaceHover
                                              : UI.Theme.surfaceSecondary
                                        border.width: enabledSwitch.visualFocus ? UI.Theme.focusWidth : 1
                                        border.color: enabledSwitch.visualFocus ? UI.Theme.focus
                                                    : enabledSwitch.checked ? UI.Theme.accent
                                                    : UI.Theme.borderStrong

                                        Rectangle {
                                            y: 3
                                            x: enabledSwitch.checked ? parent.width - width - 3 : 3
                                            width: 14
                                            height: 14
                                            radius: 7
                                            color: enabledSwitch.checked ? "#ffffff" : UI.Theme.textMuted

                                            Behavior on x {
                                                NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
                                            }
                                        }
                                    }
                                    onToggled: {
                                        root.updateEntry(modelData.id, {enabled: checked})
                                        if (root.editingConfigId.length > 0)
                                            modelService.setModelEnabled(root.editingConfigId,
                                                                         modelData.id, checked)
                                    }
                                }

                                RowLayout {
                                    spacing: UI.Theme.space2

                                    ToolButton {
                                        id: testModelButton
                                        objectName: "testModelButton"
                                        text: "↻"
                                        enabled: !modelData.testing
                                        implicitWidth: 32
                                        implicitHeight: 32
                                        activeFocusOnTab: true
                                        ToolTip.visible: hovered || activeFocus
                                        ToolTip.text: qsTr("测试连通性")
                                        contentItem: Text {
                                            text: testModelButton.text
                                            color: testModelButton.enabled ? UI.Theme.accent : UI.Theme.disabled
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontSubtitle
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        background: Rectangle {
                                            radius: UI.Theme.radiusSmall
                                            color: testModelButton.down ? UI.Theme.surfacePressed
                                                  : testModelButton.hovered ? UI.Theme.surfaceHover : "transparent"
                                            border.width: testModelButton.visualFocus ? UI.Theme.focusWidth : 0
                                            border.color: UI.Theme.focus
                                        }
                                        onClicked: root.testEntry(modelData.id)
                                    }

                                    ToolButton {
                                        id: modelSettingsButton
                                        objectName: "modelSettingsButton"
                                        text: "⚙"
                                        implicitWidth: 32
                                        implicitHeight: 32
                                        activeFocusOnTab: true
                                        ToolTip.visible: hovered || activeFocus
                                        ToolTip.text: qsTr("模型设置")
                                        contentItem: Text {
                                            text: modelSettingsButton.text
                                            color: UI.Theme.textSecondary
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontBody
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        background: Rectangle {
                                            radius: UI.Theme.radiusSmall
                                            color: modelSettingsButton.down ? UI.Theme.surfacePressed
                                                  : modelSettingsButton.hovered ? UI.Theme.surfaceHover : "transparent"
                                            border.width: modelSettingsButton.visualFocus ? UI.Theme.focusWidth : 0
                                            border.color: UI.Theme.focus
                                        }
                                        onClicked: root.openModelSettings(modelData.id)
                                    }

                                    ToolButton {
                                        id: removeModelButton
                                        objectName: "removeModelButton"
                                        text: "×"
                                        implicitWidth: 32
                                        implicitHeight: 32
                                        activeFocusOnTab: true
                                        ToolTip.visible: hovered || activeFocus
                                        ToolTip.text: qsTr("移除模型")
                                        contentItem: Text {
                                            text: removeModelButton.text
                                            color: removeModelButton.hovered ? UI.Theme.danger : UI.Theme.textMuted
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontSubtitle
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        background: Rectangle {
                                            radius: UI.Theme.radiusSmall
                                            color: removeModelButton.down ? UI.Theme.dangerSubtle
                                                  : removeModelButton.hovered ? UI.Theme.dangerSubtle : "transparent"
                                            border.width: removeModelButton.visualFocus ? UI.Theme.focusWidth : 0
                                            border.color: UI.Theme.focus
                                        }
                                        onClicked: root.setModelSelected(modelData.id, false)
                                    }
                                }
                            }
                        }

                        Dialog {
                            id: modelSettingsDialog
                            objectName: "modelSettingsPanel"
                            title: qsTr("模型设置 · %1").arg(root.settingsModelId)
                            modal: true
                            focus: true
                            width: Math.min(520, root.width - UI.Theme.space32 * 2)
                            anchors.centerIn: Overlay.overlay
                            padding: UI.Theme.space24
                            closePolicy: Popup.CloseOnEscape
                            onOpened: modelContextInput.forceActiveFocus()
                            onRejected: root.selectedModelId = ""
                            onClosed: root.selectedModelId = ""

                            background: Rectangle {
                                color: UI.Theme.surface
                                border.color: UI.Theme.border
                                radius: UI.Theme.radiusLarge
                            }

                            header: Label {
                                text: modelSettingsDialog.title
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontSubtitle
                                font.weight: Font.DemiBold
                                leftPadding: UI.Theme.space24
                                rightPadding: UI.Theme.space24
                                topPadding: UI.Theme.space20
                                bottomPadding: UI.Theme.space8
                            }

                            contentItem: ColumnLayout {
                                spacing: UI.Theme.space12

                                Label {
                                    text: qsTr("模型能力")
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontCaption
                                }

                                SettingsTextField {
                                    id: modelCapabilitiesInput
                                    objectName: "modelCapabilitiesInput"
                                    Layout.fillWidth: true
                                    text: root.settingsCapabilities
                                    placeholderText: qsTr("文本、图片、工具调用（暂留空）")
                                    activeFocusOnTab: true
                                    onTextChanged: root.settingsCapabilities = text
                                }

                                Label {
                                    text: qsTr("模型上下文窗口大小")
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontCaption
                                }

                                SettingsTextField {
                                    id: modelContextInput
                                    objectName: "modelContextInput"
                                    Layout.fillWidth: true
                                    text: root.settingsContextText
                                    placeholderText: qsTr("未获取，可手动填写")
                                    inputMethodHints: Qt.ImhDigitsOnly
                                    validator: RegularExpressionValidator {
                                        regularExpression: /^(|[1-9][0-9]{0,15})$/
                                    }
                                    activeFocusOnTab: true
                                    onTextChanged: {
                                        root.settingsContextText = text
                                        root.settingsContextWindow = Number(text || 0)
                                        root.settingsContextKnown = text.trim().length > 0
                                    }
                                }

                                Label {
                                    Layout.fillWidth: true
                                    text: root.settingsContextKnown
                                          ? (root.settingsContextSource === "manual"
                                             ? (root.settingsDefaultContextKnown
                                                ? qsTr("已使用手动值，默认值为 %1").arg(
                                                    root.settingsDefaultContext)
                                                : qsTr("已使用手动值"))
                                             : qsTr("默认值来自 Models.dev"))
                                          : qsTr("暂未获取模型元数据")
                                    color: root.settingsContextSource === "manual"
                                           ? UI.Theme.textSecondary : UI.Theme.textMuted
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontCaption
                                    wrapMode: Text.Wrap
                                }

                                Label {
                                    text: qsTr("模型调用协议")
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontCaption
                                }

                                SettingsComboBox {
                                    id: modelProtocolSelector
                                    objectName: "modelProtocolSelector"
                                    Layout.fillWidth: true
                                    model: [qsTr("Responses"), qsTr("Chat Completions")]
                                    currentIndex: root.settingsApiProtocol === "chat_completions" ? 1 : 0
                                    activeFocusOnTab: true
                                    onActivated: root.settingsApiProtocol = currentIndex === 1
                                        ? "chat_completions" : "responses"
                                }
                            }

                            footer: DialogButtonBox {
                                spacing: UI.Theme.space8
                                leftPadding: UI.Theme.space24
                                rightPadding: UI.Theme.space24
                                topPadding: UI.Theme.space8
                                bottomPadding: UI.Theme.space20
                                background: Item {}

                                SettingsButton {
                                    text: qsTr("取消")
                                    activeFocusOnTab: true
                                    DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                                }

                                SettingsButton {
                                    text: qsTr("保存")
                                    primary: true
                                    activeFocusOnTab: true
                                    DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                                }

                                onAccepted: root.saveModelSettings()
                                onRejected: modelSettingsDialog.close()
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: UI.Theme.space8

                            SettingsTextField {
                                id: manualModelInput
                                objectName: "manualModelInput"
                                Layout.fillWidth: true
                                placeholderText: root.currentPreset
                                        ? root.currentPreset.modelHints.join(", ") : ""
                                onAccepted: root.addEditorModel()
                            }

                            SettingsButton {
                                text: qsTr("添加自定义模型")
                                enabled: manualModelInput.text.trim().length > 0
                                onClicked: root.addEditorModel()
                            }

                            SettingsButton {
                                id: discoverModelsButton
                                objectName: "discoverModelsButton"
                                text: root.discovering ? qsTr("获取中…") : qsTr("获取模型列表")
                                enabled: !root.discovering && baseUrlInput.text.trim().length > 0
                                onClicked: root.discover()
                            }
                        }

                        Rectangle {
                            id: discoveryStatus
                            objectName: "modelDiscoveryStatus"
                            visible: root.statusMessage.length > 0
                                    && root.mode === "editor"
                            Layout.fillWidth: true
                            Layout.preferredHeight: statusLabel.implicitHeight + UI.Theme.space16
                            radius: UI.Theme.radiusMedium
                            color: root.statusKind === "error" ? UI.Theme.dangerSubtle
                                 : root.statusKind === "success" ? UI.Theme.successSubtle
                                 : UI.Theme.accentSubtle

                            Label {
                                id: statusLabel
                                anchors.fill: parent
                                anchors.margins: UI.Theme.space8
                                text: root.statusMessage
                                color: root.statusKind === "error" ? UI.Theme.danger
                                     : root.statusKind === "success" ? UI.Theme.success
                                     : UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                wrapMode: Text.Wrap
                            }
                        }

                        ColumnLayout {
                            id: discoveryResults
                            objectName: "modelDiscoveryResults"
                            visible: root.discoveredModels.length > 0
                            Layout.fillWidth: true
                            spacing: UI.Theme.space8

                            SettingsTextField {
                                id: discoverySearch
                                objectName: "discoveredModelSearch"
                                Layout.fillWidth: true
                                placeholderText: qsTr("搜索发现的模型")
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: Math.min(240,
                                    Math.max(56, root.filteredModels.length
                                             * UI.Theme.controlHeightLarge))
                                radius: UI.Theme.radiusMedium
                                color: UI.Theme.background
                                border.color: UI.Theme.border
                                border.width: 1
                                clip: true

                                ListView {
                                    id: discoveredModelList
                                    objectName: "discoveredModelList"
                                    anchors.fill: parent
                                    model: root.filteredModels
                                    clip: true
                                    boundsBehavior: Flickable.StopAtBounds

                                    delegate: CheckDelegate {
                                        required property string modelData
                                        width: ListView.view.width
                                        height: UI.Theme.controlHeightLarge
                                        text: modelData
                                        checked: root.hasModel(modelData)
                                        onClicked: root.setModelSelected(modelData, checked, true)
                                    }

                                    ScrollBar.vertical: ScrollBar {}
                                }

                                Label {
                                    anchors.centerIn: parent
                                    visible: root.filteredModels.length === 0
                                    text: qsTr("没有匹配的模型")
                                    color: UI.Theme.textMuted
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Item { Layout.fillWidth: true }

                    SettingsButton {
                        text: qsTr("取消")
                        onClicked: root.cancelEditor()
                    }

                    SettingsButton {
                        id: saveProviderButton
                        objectName: "saveProviderButton"
                        text: qsTr("保存配置")
                        primary: true
                        onClicked: root.saveEditor()
                    }
                }
            }

            Item { Layout.preferredHeight: UI.Theme.space24 }
        }
    }

    Connections {
        target: modelService

        function onModelsDiscovered(requestId, models) {
            if (requestId !== root.discoveryRequestId)
                return
            root.discovering = false
            root.discoveredModels = models
            root.statusKind = "success"
            root.statusMessage = qsTr("发现 %1 个模型，请勾选需要保存的模型。")
                .arg(models.length)
        }

        function onDiscoveryFailed(requestId, message) {
            if (requestId !== root.discoveryRequestId)
                return
            root.discovering = false
            root.statusKind = "error"
            root.statusMessage = message
        }

        function onModelProbeFinished(requestId, modelId, ok, message, protocol) {
            if (!requestId.startsWith((root.editingConfigId || "new") + ":" + modelId + ":"))
                return
            const values = {testing: false, testState: ok ? "success" : "error",
                testMessage: message}
            const entry = root.entryFor(modelId)
            if (entry && entry.autoProbe) {
                values.autoProbe = false
                if (ok) {
                    values.apiProtocol = protocol
                    values.enabled = true
                }
            }
            root.updateEntry(modelId, values)
            if (ok)
                root.statusMessage = qsTr("模型 %1 测试通过（%2，%3）。").arg(modelId)
                    .arg(protocol === "responses" ? qsTr("Responses") : qsTr("Chat Completions"))
                    .arg(message)
            else
                root.statusMessage = qsTr("模型 %1 测试失败：%2").arg(modelId).arg(message)
            root.statusKind = ok ? "success" : "error"
        }

        function onModelMetadataChanged(providerType) {
            root.applyMetadataToEntries(providerType)
        }
    }
}
