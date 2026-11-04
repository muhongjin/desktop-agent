import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as UI

Item {
    id: root
    objectName: "knowledgePage"

    property var embeddingProviders: []
    property bool creating: false
    property var retrievalHits: []
    property string retrievalSummary: ""
    property string retrievalError: ""
    property bool retrievalTesting: false
    property string errorMessage: ""
    property string statusMessage: ""
    property string createError: ""
    property string settingsError: ""

    readonly property bool hasKnowledgeBases: knowledgeBaseList.count > 0
    readonly property bool hasSelection: knowledgeService.currentKnowledgeBaseId.length > 0
    readonly property bool hasEmbeddingProviders: embeddingProviders.length > 0

    function refreshEmbeddingOptions() {
        root.embeddingProviders = knowledgeService.embeddingProviders()
    }

    function loadEmbeddingModels() {
        const provider = embeddingProviders[embeddingProviderCombo.currentIndex]
        if (provider === undefined || provider === null)
            return
        knowledgeService.loadEmbeddingModels(provider.providerId)
    }

    function clearMessages() {
        root.errorMessage = ""
        root.statusMessage = ""
    }

    function clearRetrieval() {
        root.retrievalHits = []
        root.retrievalSummary = ""
        root.retrievalError = ""
        root.retrievalTesting = false
    }

    function openCreateDialog() {
        refreshEmbeddingOptions()
        createError = ""
        kbNameInput.text = ""
        kbDescriptionInput.text = ""
        chunkSizeInput.text = "512"
        embeddingProviderCombo.currentIndex = 0
        embeddingModelCombo.currentIndex = 0
        embeddingModelInput.text = ""
        manualModelToggle.checked = false
        creating = false
        clearMessages()
        createDialog.open()
        loadEmbeddingModels()
    }

    function submitCreate() {
        if (root.creating)
            return
        const name = kbNameInput.text.trim()
        if (name.length === 0) {
            createError = qsTr("请填写知识库名称。")
            return
        }
        if (!hasEmbeddingProviders) {
            createError = qsTr("还没有可用的模型服务，请先在「模型服务」中配置。")
            return
        }
        const provider = embeddingProviders[embeddingProviderCombo.currentIndex]
        if (provider === undefined || provider === null) {
            createError = qsTr("请选择一个模型服务。")
            return
        }
        let modelId = ""
        if (manualModelToggle.checked) {
            modelId = embeddingModelInput.text.trim()
        } else if (embeddingModelCombo.currentIndex >= 0 && embeddingModelCombo.count > 0) {
            const options = knowledgeService.embeddingModelOptions
            const option = options[embeddingModelCombo.currentIndex]
            if (option !== undefined && option !== null)
                modelId = option.modelId
        }
        if (modelId.length === 0) {
            createError = qsTr("请先从列表选择嵌入模型，或勾选「手动输入」填写模型 ID。")
            return
        }
        const chunkSize = parseInt(chunkSizeInput.text)
        if (isNaN(chunkSize) || chunkSize < 128 || chunkSize > 2048) {
            createError = qsTr("分块大小需要是 128 到 2048 之间的整数。")
            return
        }
        createError = ""
        clearMessages()
        clearRetrieval()
        statusMessage = qsTr("正在创建知识库，请稍候…")
        root.creating = true
        knowledgeService.createKnowledgeBase(name, kbDescriptionInput.text.trim(),
                                             provider.providerId, modelId, chunkSize)
    }

    function selectKnowledgeBase(kbId) {
        if (kbId === knowledgeService.currentKnowledgeBaseId)
            return
        clearRetrieval()
        knowledgeService.selectKnowledgeBase(kbId)
    }

    function requestDeleteKnowledgeBase() {
        if (!hasSelection)
            return
        deleteDialog.open()
    }

    function openSettingsDialog() {
        if (!hasSelection)
            return
        const settings = knowledgeService.knowledgeBaseSettings(
                    knowledgeService.currentKnowledgeBaseId)
        settingsChunkSizeInput.text = String(settings.chunkSize || 512)
        settingsChunkOverlapInput.text = String(settings.chunkOverlap || 50)
        settingsTopMFinalInput.text = String(settings.topMFinal || 5)
        settingsError = ""
        settingsDialog.open()
    }

    function saveKnowledgeSettings() {
        const kbId = knowledgeService.currentKnowledgeBaseId
        if (kbId.length === 0)
            return
        const chunkSize = parseInt(settingsChunkSizeInput.text)
        const chunkOverlap = parseInt(settingsChunkOverlapInput.text)
        const topMFinal = parseInt(settingsTopMFinalInput.text)
        if (isNaN(chunkSize) || chunkSize < 128 || chunkSize > 2048) {
            settingsError = qsTr("分块大小需要是 128 到 2048 之间的整数。")
            return
        }
        if (isNaN(chunkOverlap) || chunkOverlap < 0 || chunkOverlap >= chunkSize) {
            settingsError = qsTr("重复段大小需要小于分块大小。")
            return
        }
        if (isNaN(topMFinal) || topMFinal < 1 || topMFinal > 20) {
            settingsError = qsTr("返回条数需要是 1 到 20 之间的整数。")
            return
        }
        knowledgeService.updateKnowledgeBaseSettings(
                    kbId, chunkSize, chunkOverlap, topMFinal)
        statusMessage = qsTr("知识库设置已保存。")
        settingsDialog.close()
    }

    function confirmDeleteKnowledgeBase() {
        const kbId = knowledgeService.currentKnowledgeBaseId
        deleteDialog.close()
        if (kbId.length === 0)
            return
        clearMessages()
        clearRetrieval()
        knowledgeService.deleteKnowledgeBase(kbId)
        statusMessage = qsTr("已删除知识库。")
    }

    function importDocuments() {
        if (!hasSelection || knowledgeService.indexing)
            return
        clearMessages()
        knowledgeService.importDocuments(knowledgeService.currentKnowledgeBaseId)
    }

    function deleteDocument(docId) {
        if (!hasSelection || knowledgeService.indexing)
            return
        clearMessages()
        clearRetrieval()
        knowledgeService.deleteDocument(knowledgeService.currentKnowledgeBaseId, docId)
    }

    function runRetrievalTest() {
        if (!hasSelection || retrievalTesting)
            return
        const query = retrievalQueryInput.text.trim()
        if (query.length === 0) {
            retrievalError = qsTr("请先输入要检索的问题。")
            return
        }
        clearRetrieval()
        retrievalTesting = true
        knowledgeService.testRetrieval(knowledgeService.currentKnowledgeBaseId, query)
    }

    function formatSize(bytes) {
        const value = Number(bytes || 0)
        if (value >= 1024 * 1024)
            return (value / (1024 * 1024)).toFixed(1) + " MB"
        if (value >= 1024)
            return (value / 1024).toFixed(1) + " KB"
        return value + " B"
    }

    function statusLabel(status) {
        if (status === "ready")
            return qsTr("就绪")
        if (status === "indexing")
            return qsTr("索引中")
        if (status === "failed")
            return qsTr("失败")
        return qsTr("待处理")
    }

    function statusColor(status) {
        if (status === "ready")
            return UI.Theme.success
        if (status === "failed")
            return UI.Theme.danger
        return UI.Theme.warning
    }

    function statusBackground(status) {
        if (status === "ready")
            return UI.Theme.successSubtle
        if (status === "failed")
            return UI.Theme.dangerSubtle
        return UI.Theme.warningSubtle
    }

    function hitLocation(hit) {
        const parts = []
        const heading = hit.heading ? String(hit.heading) : ""
        if (heading.length > 0)
            parts.push(heading)
        if (hit.page !== null && hit.page !== undefined && Number(hit.page) > 0)
            parts.push(qsTr("第 %1 页").arg(Number(hit.page)))
        return parts.join(" · ")
    }

    function formatSimilarity(similarity) {
        return (Number(similarity || 0) * 100).toFixed(1) + "%"
    }

    Component.onCompleted: refreshEmbeddingOptions()

    onVisibleChanged: {
        if (visible)
            refreshEmbeddingOptions()
    }

    Connections {
        target: knowledgeService

        function onRetrievalTestFinished(payload) {
            root.retrievalTesting = false
            let parsed = null
            try {
                parsed = JSON.parse(payload)
            } catch (error) {
                parsed = null
            }
            if (parsed === null) {
                root.retrievalError = qsTr("检索失败：无法解析检索结果。")
                return
            }
            if (parsed.error) {
                root.retrievalHits = []
                root.retrievalSummary = ""
                root.retrievalError = qsTr("检索失败：%1").arg(parsed.error)
                return
            }
            root.retrievalError = ""
            root.retrievalHits = parsed.hits || []
            root.retrievalSummary = qsTr("共 %1 条结果 · 耗时 %2 ms")
                    .arg(root.retrievalHits.length).arg(Number(parsed.elapsed_ms || 0))
        }

        function onErrorOccurred(message) {
            root.creating = false
            root.statusMessage = ""
            if (createDialog.opened) {
                root.createError = message
            } else {
                root.errorMessage = message
            }
        }

        function onKnowledgeBaseCreated(kbId) {
            root.creating = false
            root.createError = ""
            root.errorMessage = ""
            root.statusMessage = qsTr("知识库已创建。")
            createDialog.close()
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: listPane
            Layout.preferredWidth: Math.max(220, Math.min(260, root.width * 0.32))
            Layout.fillHeight: true
            color: UI.Theme.surfaceSecondary

            Rectangle {
                width: 1
                height: parent.height
                anchors.right: parent.right
                color: UI.Theme.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: UI.Theme.space16
                spacing: UI.Theme.space12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space4

                    Label {
                        text: qsTr("知识库")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontTitle
                        font.weight: Font.DemiBold
                    }

                    Label {
                        text: qsTr("本地存储，按知识库检索文档。")
                        color: UI.Theme.textSecondary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontCaption
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

                ListView {
                    id: knowledgeBaseList
                    objectName: "knowledgeBaseList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: UI.Theme.space4
                    activeFocusOnTab: true
                    keyNavigationEnabled: true
                    model: knowledgeService.knowledgeBases
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: ItemDelegate {
                        id: knowledgeBaseItem
                        required property string kbId
                        required property string name
                        required property int documentCount
                        required property int chunkCount
                        required property string embeddingModel
                        width: ListView.view.width
                        height: 64
                        leftPadding: UI.Theme.space12
                        rightPadding: UI.Theme.space12
                        topPadding: UI.Theme.space8
                        bottomPadding: UI.Theme.space8
                        activeFocusOnTab: true
                        highlighted: kbId === knowledgeService.currentKnowledgeBaseId
                        onClicked: root.selectKnowledgeBase(kbId)

                        contentItem: ColumnLayout {
                            spacing: UI.Theme.space2

                            Label {
                                text: knowledgeBaseItem.name
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                font.weight: knowledgeBaseItem.highlighted ? Font.DemiBold : Font.Normal
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            Label {
                                text: qsTr("%1 文档 · %2 分块")
                                        .arg(knowledgeBaseItem.documentCount)
                                        .arg(knowledgeBaseItem.chunkCount)
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            Label {
                                text: knowledgeBaseItem.embeddingModel
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.monoFontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        background: Rectangle {
                            radius: UI.Theme.radiusMedium
                            color: parent.highlighted ? UI.Theme.accentSubtle
                                   : parent.hovered ? UI.Theme.surfaceHover
                                   : "transparent"
                            border.width: parent.visualFocus ? UI.Theme.focusWidth : 0
                            border.color: UI.Theme.focus
                        }
                    }
                }

                Label {
                    objectName: "knowledgeListEmptyState"
                    visible: !root.hasKnowledgeBases
                    text: qsTr("还没有知识库，从下方新建一个开始。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }

                Label {
                    objectName: "embeddingModelHint"
                    visible: !root.hasEmbeddingProviders
                    text: qsTr("先在「模型服务」中配置一个提供商，再填写嵌入模型。")
                    color: UI.Theme.warning
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }

                SettingsButton {
                    id: createKnowledgeBaseButton
                    objectName: "createKnowledgeBaseButton"
                    text: qsTr("＋ 新建知识库")
                    primary: true
                    Layout.fillWidth: true
                    enabled: root.hasEmbeddingProviders && !knowledgeService.indexing
                    onClicked: root.openCreateDialog()
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ScrollView {
                id: detailScroll
                anchors.fill: parent
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    x: UI.Theme.space24
                    width: Math.max(280, detailScroll.availableWidth - UI.Theme.space24 * 2)
                    spacing: UI.Theme.space16

                    Item { Layout.preferredHeight: UI.Theme.space4 }

                    ColumnLayout {
                        objectName: "knowledgeEmptyState"
                        visible: !root.hasKnowledgeBases
                        Layout.fillWidth: true
                        Layout.topMargin: UI.Theme.space32
                        spacing: UI.Theme.space8

                        Label {
                            text: qsTr("还没有知识库")
                            color: UI.Theme.textPrimary
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontSubtitle
                            font.weight: Font.DemiBold
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }

                        Label {
                            text: qsTr("创建知识库后，可以导入 PDF、Word、Excel 或文本文件，并在下方测试检索效果。")
                            color: UI.Theme.textMuted
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }

                        Label {
                            visible: !root.hasEmbeddingProviders
                            text: qsTr("当前还没有可用的模型服务，请先在「模型服务」中配置提供商。")
                            color: UI.Theme.warning
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }

                    ColumnLayout {
                        visible: root.hasKnowledgeBases
                        Layout.fillWidth: true
                        spacing: UI.Theme.space12

                        Repeater {
                            objectName: "knowledgeBaseHeaderRepeater"
                            model: knowledgeService.knowledgeBases

                            delegate: ColumnLayout {
                                id: baseHeader
                                required property string kbId
                                required property string name
                                required property string description
                                required property int documentCount
                                required property int chunkCount
                                required property string embeddingModel
                                required property int chunkSize
                                required property int chunkOverlap
                                required property int topMFinal
                                visible: baseHeader.kbId === knowledgeService.currentKnowledgeBaseId
                                Layout.fillWidth: true
                                spacing: UI.Theme.space8

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: UI.Theme.space8

                                    Label {
                                        text: baseHeader.name
                                        color: UI.Theme.textPrimary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontTitle
                                        font.weight: Font.DemiBold
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }

                                    SettingsButton {
                                        objectName: "importDocumentsButton"
                                        text: qsTr("导入文档")
                                        primary: true
                                        enabled: root.hasSelection && !knowledgeService.indexing
                                        onClicked: root.importDocuments()
                                    }

                                    SettingsButton {
                                        objectName: "knowledgeSettingsButton"
                                        text: qsTr("设置")
                                        enabled: root.hasSelection && !knowledgeService.indexing
                                        onClicked: root.openSettingsDialog()
                                    }

                                    SettingsButton {
                                        objectName: "deleteKnowledgeBaseButton"
                                        text: qsTr("删除知识库")
                                        destructive: true
                                        enabled: root.hasSelection && !knowledgeService.indexing
                                        onClicked: root.requestDeleteKnowledgeBase()
                                    }
                                }

                                Label {
                                    visible: baseHeader.description.length > 0
                                    text: baseHeader.description
                                    color: UI.Theme.textSecondary
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: UI.Theme.space12

                                    Label {
                                        text: qsTr("%1 个文档").arg(baseHeader.documentCount)
                                        color: UI.Theme.textSecondary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                    }

                                    Label {
                                        text: qsTr("%1 个分块").arg(baseHeader.chunkCount)
                                        color: UI.Theme.textSecondary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                    }

                                    Label {
                                        text: qsTr("嵌入模型 %1").arg(baseHeader.embeddingModel)
                                        color: UI.Theme.textMuted
                                        font.family: UI.Theme.monoFontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }

                                    Label {
                                        text: qsTr("块 %1 · 重叠 %2 · 返回 %3 条")
                                                .arg(baseHeader.chunkSize)
                                                .arg(baseHeader.chunkOverlap)
                                                .arg(baseHeader.topMFinal)
                                        color: UI.Theme.textMuted
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                    }
                                }
                            }
                        }

                        Rectangle {
                            objectName: "knowledgeIndexingBanner"
                            visible: knowledgeService.indexing
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            radius: UI.Theme.radiusMedium
                            color: UI.Theme.accentSubtle

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: UI.Theme.space12
                                spacing: UI.Theme.space8

                                BusyIndicator {
                                    running: knowledgeService.indexing
                                    implicitWidth: 20
                                    implicitHeight: 20
                                    Layout.preferredWidth: 20
                                    Layout.preferredHeight: 20
                                }

                                Label {
                                    text: knowledgeService.indexingStatus.length > 0
                                            ? knowledgeService.indexingStatus
                                            : qsTr("正在建立索引…")
                                    color: UI.Theme.accent
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontBody
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        Rectangle {
                            objectName: "knowledgeErrorBanner"
                            visible: root.errorMessage.length > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(40, errorMessageLabel.implicitHeight + UI.Theme.space16)
                            radius: UI.Theme.radiusMedium
                            color: UI.Theme.dangerSubtle

                            Label {
                                id: errorMessageLabel
                                anchors.left: parent.left
                                anchors.right: dismissErrorButton.left
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: UI.Theme.space12
                                anchors.rightMargin: UI.Theme.space4
                                text: root.errorMessage
                                color: UI.Theme.danger
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                wrapMode: Text.Wrap
                            }

                            ToolButton {
                                id: dismissErrorButton
                                text: "×"
                                implicitWidth: 32
                                implicitHeight: 32
                                anchors.right: parent.right
                                anchors.rightMargin: UI.Theme.space4
                                anchors.verticalCenter: parent.verticalCenter
                                activeFocusOnTab: true
                                ToolTip.visible: hovered || activeFocus
                                ToolTip.text: qsTr("关闭提示")
                                contentItem: Text {
                                    text: dismissErrorButton.text
                                    color: UI.Theme.danger
                                    font.family: UI.Theme.fontFamily
                                    font.pixelSize: UI.Theme.fontSubtitle
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    radius: UI.Theme.radiusSmall
                                    color: dismissErrorButton.hovered ? UI.Theme.dangerSubtle : "transparent"
                                    border.width: dismissErrorButton.visualFocus ? UI.Theme.focusWidth : 0
                                    border.color: UI.Theme.focus
                                }
                                onClicked: root.errorMessage = ""
                            }
                        }

                        Rectangle {
                            objectName: "knowledgeStatusBanner"
                            visible: root.statusMessage.length > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(40, statusMessageLabel.implicitHeight + UI.Theme.space16)
                            radius: UI.Theme.radiusMedium
                            color: UI.Theme.successSubtle

                            Label {
                                id: statusMessageLabel
                                anchors.fill: parent
                                anchors.leftMargin: UI.Theme.space12
                                anchors.rightMargin: UI.Theme.space12
                                text: root.statusMessage
                                color: UI.Theme.success
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                wrapMode: Text.Wrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: UI.Theme.space8

                            Label {
                                text: qsTr("文档")
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontSubtitle
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                            }

                            Label {
                                text: qsTr("%1 个").arg(documentList.count)
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                            }
                        }

                        RowLayout {
                            visible: documentList.count > 0
                            Layout.fillWidth: true
                            spacing: UI.Theme.space8

                            Label {
                                text: qsTr("文件名")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                Layout.fillWidth: true
                            }

                            Label {
                                text: qsTr("状态")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                Layout.preferredWidth: 64
                                horizontalAlignment: Text.AlignHCenter
                            }

                            Label {
                                text: qsTr("分块")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                Layout.preferredWidth: 44
                                horizontalAlignment: Text.AlignRight
                            }

                            Label {
                                text: qsTr("大小")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                Layout.preferredWidth: 60
                                horizontalAlignment: Text.AlignRight
                            }

                            Item { Layout.preferredWidth: 32 }
                        }

                        ListView {
                            id: documentList
                            objectName: "documentList"
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(320, Math.max(48, documentList.count * 56))
                            clip: true
                            spacing: UI.Theme.space4
                            activeFocusOnTab: true
                            model: knowledgeService.documents
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                            delegate: Rectangle {
                                id: documentRow
                                required property string docId
                                required property string filename
                                required property string status
                                required property int chunkCount
                                required property int byteSize
                                required property string error
                                width: ListView.view.width
                                height: documentRow.error.length > 0 && documentRow.status === "failed" ? 64 : 48
                                radius: UI.Theme.radiusMedium
                                color: UI.Theme.surface
                                border.width: 1
                                border.color: UI.Theme.border

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: UI.Theme.space12
                                    anchors.rightMargin: UI.Theme.space8
                                    spacing: UI.Theme.space8

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 0

                                        Label {
                                            text: documentRow.filename
                                            color: UI.Theme.textPrimary
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontBody
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }

                                        Label {
                                            visible: documentRow.status === "failed" && documentRow.error.length > 0
                                            text: documentRow.error
                                            color: UI.Theme.danger
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontCaption
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Rectangle {
                                        Layout.preferredWidth: 64
                                        Layout.preferredHeight: 22
                                        radius: UI.Theme.radiusSmall
                                        color: root.statusBackground(documentRow.status)

                                        Label {
                                            anchors.centerIn: parent
                                            text: root.statusLabel(documentRow.status)
                                            color: root.statusColor(documentRow.status)
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontCaption
                                        }
                                    }

                                    Label {
                                        text: qsTr("%1").arg(documentRow.chunkCount)
                                        color: UI.Theme.textSecondary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                        Layout.preferredWidth: 44
                                        horizontalAlignment: Text.AlignRight
                                    }

                                    Label {
                                        text: root.formatSize(documentRow.byteSize)
                                        color: UI.Theme.textSecondary
                                        font.family: UI.Theme.fontFamily
                                        font.pixelSize: UI.Theme.fontCaption
                                        Layout.preferredWidth: 60
                                        horizontalAlignment: Text.AlignRight
                                    }

                                    ToolButton {
                                        id: deleteDocumentButton
                                        objectName: "deleteDocumentButton"
                                        text: "×"
                                        implicitWidth: 32
                                        implicitHeight: 32
                                        enabled: !knowledgeService.indexing
                                        activeFocusOnTab: true
                                        ToolTip.visible: hovered || activeFocus
                                        ToolTip.text: qsTr("从知识库移除文档")
                                        contentItem: Text {
                                            text: deleteDocumentButton.text
                                            color: deleteDocumentButton.hovered && deleteDocumentButton.enabled
                                                   ? UI.Theme.danger : UI.Theme.textMuted
                                            font.family: UI.Theme.fontFamily
                                            font.pixelSize: UI.Theme.fontSubtitle
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        background: Rectangle {
                                            radius: UI.Theme.radiusSmall
                                            color: deleteDocumentButton.hovered ? UI.Theme.dangerSubtle : "transparent"
                                            border.width: deleteDocumentButton.visualFocus ? UI.Theme.focusWidth : 0
                                            border.color: UI.Theme.focus
                                        }
                                        onClicked: root.deleteDocument(documentRow.docId)
                                    }
                                }
                            }
                        }

                        Label {
                            objectName: "documentsEmptyState"
                            visible: documentList.count === 0
                            text: qsTr("还没有导入文档，点击「导入文档」添加。")
                            color: UI.Theme.textMuted
                            font.family: UI.Theme.fontFamily
                            font.pixelSize: UI.Theme.fontBody
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }

                        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: UI.Theme.border }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: UI.Theme.space8

                            Label {
                                text: qsTr("检索测试")
                                color: UI.Theme.textPrimary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontSubtitle
                                font.weight: Font.DemiBold
                            }

                            Label {
                                text: qsTr("用当前知识库测试检索效果，不会影响聊天记录。")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: UI.Theme.space8

                                SettingsTextField {
                                    id: retrievalQueryInput
                                    objectName: "retrievalQueryInput"
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("输入要检索的问题")
                                    enabled: root.hasSelection && !root.retrievalTesting
                                    onAccepted: root.runRetrievalTest()
                                }

                                SettingsButton {
                                    id: retrievalTestButton
                                    objectName: "retrievalTestButton"
                                    text: qsTr("测试")
                                    enabled: root.hasSelection && !root.retrievalTesting
                                    onClicked: root.runRetrievalTest()
                                }
                            }

                            Label {
                                objectName: "retrievalTestingState"
                                visible: root.retrievalTesting
                                text: qsTr("正在检索…")
                                color: UI.Theme.textSecondary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                            }

                            Label {
                                objectName: "retrievalSummary"
                                visible: root.retrievalSummary.length > 0
                                text: root.retrievalSummary
                                color: UI.Theme.textSecondary
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontCaption
                            }

                            Label {
                                objectName: "retrievalError"
                                visible: root.retrievalError.length > 0
                                text: root.retrievalError
                                color: UI.Theme.danger
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            Label {
                                objectName: "retrievalEmptyState"
                                visible: root.retrievalSummary.length > 0
                                        && root.retrievalHits.length === 0
                                        && root.retrievalError.length === 0
                                text: qsTr("没有找到相关内容。")
                                color: UI.Theme.textMuted
                                font.family: UI.Theme.fontFamily
                                font.pixelSize: UI.Theme.fontBody
                            }

                            ColumnLayout {
                                objectName: "retrievalResults"
                                visible: root.retrievalHits.length > 0
                                Layout.fillWidth: true
                                spacing: UI.Theme.space8

                                Repeater {
                                    model: root.retrievalHits

                                    delegate: Rectangle {
                                        id: retrievalHitCard
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: hitContent.implicitHeight + UI.Theme.space16
                                        radius: UI.Theme.radiusMedium
                                        color: UI.Theme.surface
                                        border.width: 1
                                        border.color: UI.Theme.border

                                        ColumnLayout {
                                            id: hitContent
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.top: parent.top
                                            anchors.margins: UI.Theme.space8
                                            spacing: UI.Theme.space2

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: UI.Theme.space8

                                                Label {
                                                    text: "[" + retrievalHitCard.modelData.n + "]"
                                                    color: UI.Theme.accent
                                                    font.family: UI.Theme.fontFamily
                                                    font.pixelSize: UI.Theme.fontCaption
                                                    font.weight: Font.DemiBold
                                                }

                                                Label {
                                                    text: retrievalHitCard.modelData.doc_name
                                                    color: UI.Theme.textPrimary
                                                    font.family: UI.Theme.fontFamily
                                                    font.pixelSize: UI.Theme.fontCaption
                                                    font.weight: Font.DemiBold
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                }

                                                Label {
                                                    visible: root.hitLocation(retrievalHitCard.modelData).length > 0
                                                    text: root.hitLocation(retrievalHitCard.modelData)
                                                    color: UI.Theme.textMuted
                                                    font.family: UI.Theme.fontFamily
                                                    font.pixelSize: UI.Theme.fontCaption
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                }

                                                Label {
                                                    text: qsTr("相似度 %1")
                                                            .arg(root.formatSimilarity(retrievalHitCard.modelData.similarity))
                                                    color: UI.Theme.accent
                                                    font.family: UI.Theme.fontFamily
                                                    font.pixelSize: UI.Theme.fontCaption
                                                }
                                            }

                                            Label {
                                                text: retrievalHitCard.modelData.snippet
                                                color: UI.Theme.textSecondary
                                                font.family: UI.Theme.fontFamily
                                                font.pixelSize: UI.Theme.fontCaption
                                                wrapMode: Text.Wrap
                                                maximumLineCount: 3
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: UI.Theme.space24 }
                }
            }
        }
    }

    Dialog {
        id: createDialog
        objectName: "createKnowledgeBaseDialog"
        title: qsTr("新建知识库")
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(460, root.width - UI.Theme.space32 * 2)
        padding: UI.Theme.space24
        closePolicy: Popup.CloseOnEscape
        onOpened: kbNameInput.forceActiveFocus()
        onRejected: root.createError = ""

        background: Rectangle {
            color: UI.Theme.surface
            border.color: UI.Theme.border
            radius: UI.Theme.radiusLarge
        }

        header: Label {
            text: createDialog.title
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
                text: qsTr("名称")
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.DemiBold
            }

            SettingsTextField {
                id: kbNameInput
                objectName: "knowledgeBaseNameInput"
                Layout.fillWidth: true
                placeholderText: qsTr("例如：产品手册")
            }

            Label {
                text: qsTr("描述（可选）")
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.DemiBold
            }

            SettingsTextField {
                id: kbDescriptionInput
                objectName: "knowledgeBaseDescriptionInput"
                Layout.fillWidth: true
                placeholderText: qsTr("简要说明这个知识库的用途")
            }

            Label {
                text: qsTr("模型服务")
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.DemiBold
            }

            SettingsComboBox {
                id: embeddingProviderCombo
                objectName: "embeddingProviderCombo"
                Layout.fillWidth: true
                model: root.embeddingProviders
                textRole: "displayName"
                onCurrentIndexChanged: {
                    if (createDialog.opened)
                        root.loadEmbeddingModels()
                }
            }

            Label {
                text: qsTr("嵌入模型")
                color: UI.Theme.textPrimary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                font.weight: Font.DemiBold
            }

            SettingsComboBox {
                id: embeddingModelCombo
                objectName: "embeddingModelCombo"
                Layout.fillWidth: true
                model: knowledgeService.embeddingModelOptions
                textRole: "modelId"
                enabled: !manualModelToggle.checked
                         && knowledgeService.embeddingModelOptions.length > 0
            }

            Label {
                visible: knowledgeService.embeddingModelsLoading
                text: qsTr("正在从服务商获取模型列表…")
                color: UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            Label {
                objectName: "embeddingModelListError"
                visible: !knowledgeService.embeddingModelsLoading
                         && knowledgeService.embeddingModelsError.length > 0
                text: knowledgeService.embeddingModelsError
                color: UI.Theme.warning
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            CheckBox {
                id: manualModelToggle
                objectName: "manualEmbeddingModelToggle"
                text: qsTr("手动输入模型 ID")
                checked: knowledgeService.embeddingModelsError.length > 0
                         && knowledgeService.embeddingModelOptions.length === 0
            }

            SettingsTextField {
                id: embeddingModelInput
                objectName: "embeddingModelInput"
                Layout.fillWidth: true
                visible: manualModelToggle.checked
                placeholderText: qsTr("如 BAAI/bge-m3 或 text-embedding-3-small")
            }

            Label {
                text: qsTr("列表会自动筛选支持 /embeddings 的模型；聊天模型不能用于嵌入。创建时会自动探测向量维度。")
                color: UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            Label {
                visible: !root.hasEmbeddingProviders
                text: qsTr("没有可用的模型服务，请先在「模型服务」中配置。")
                color: UI.Theme.warning
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("分块大小")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    SettingsTextField {
                        id: chunkSizeInput
                        objectName: "chunkSizeInput"
                        Layout.fillWidth: true
                        text: "512"
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: IntValidator { bottom: 128; top: 2048 }
                    }
                }

                Label {
                    text: qsTr("默认 512。数值越大，单个分块包含的内容越多。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Label {
                objectName: "createKnowledgeBaseError"
                visible: root.createError.length > 0
                text: root.createError
                color: UI.Theme.danger
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            Label {
                text: qsTr("索引文档时，文本会发送给所选嵌入模型服务；已有索引不会随模型更换自动重建。")
                color: UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        footer: Item {
            implicitHeight: 68

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: UI.Theme.space24
                anchors.rightMargin: UI.Theme.space24
                anchors.topMargin: UI.Theme.space8
                anchors.bottomMargin: UI.Theme.space20
                spacing: UI.Theme.space8

                Item { Layout.fillWidth: true }

                SettingsButton {
                    text: qsTr("取消")
                    enabled: !root.creating
                    onClicked: createDialog.reject()
                }

                SettingsButton {
                    objectName: "createKnowledgeBaseConfirmButton"
                    text: root.creating ? qsTr("创建中…") : qsTr("创建")
                    primary: true
                    enabled: root.hasEmbeddingProviders && !root.creating
                    onClicked: root.submitCreate()
                }
            }
        }
    }

    Dialog {
        id: settingsDialog
        objectName: "knowledgeSettingsDialog"
        title: qsTr("知识库设置")
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(480, root.width - UI.Theme.space32 * 2)
        padding: UI.Theme.space24
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            color: UI.Theme.surface
            border.color: UI.Theme.border
            radius: UI.Theme.radiusLarge
        }

        header: Label {
            text: settingsDialog.title
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

            RowLayout {
                Layout.fillWidth: true
                spacing: UI.Theme.space12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("分块大小")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    SettingsTextField {
                        id: settingsChunkSizeInput
                        objectName: "settingsChunkSizeInput"
                        Layout.fillWidth: true
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: IntValidator { bottom: 128; top: 2048 }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: UI.Theme.space8

                    Label {
                        text: qsTr("重复段大小")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    SettingsTextField {
                        id: settingsChunkOverlapInput
                        objectName: "settingsChunkOverlapInput"
                        Layout.fillWidth: true
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: IntValidator { bottom: 0; top: 2048 }
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
                        text: qsTr("返回条数")
                        color: UI.Theme.textPrimary
                        font.family: UI.Theme.fontFamily
                        font.pixelSize: UI.Theme.fontBody
                        font.weight: Font.DemiBold
                    }

                    SettingsTextField {
                        id: settingsTopMFinalInput
                        objectName: "settingsTopMFinalInput"
                        Layout.fillWidth: true
                        inputMethodHints: Qt.ImhDigitsOnly
                        validator: IntValidator { bottom: 1; top: 20 }
                    }
                }

                Label {
                    text: qsTr("每次检索最多注入多少条片段，立即生效。")
                    color: UI.Theme.textMuted
                    font.family: UI.Theme.fontFamily
                    font.pixelSize: UI.Theme.fontCaption
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            Label {
                text: qsTr("分块大小 / 重复段只影响之后导入的文档；已有文档不会自动重切，需要重新导入。")
                color: UI.Theme.textMuted
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontCaption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            Label {
                objectName: "knowledgeSettingsError"
                visible: root.settingsError.length > 0
                text: root.settingsError
                color: UI.Theme.danger
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        footer: Item {
            implicitHeight: 68

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: UI.Theme.space24
                anchors.rightMargin: UI.Theme.space24
                anchors.topMargin: UI.Theme.space8
                anchors.bottomMargin: UI.Theme.space20
                spacing: UI.Theme.space8

                Item { Layout.fillWidth: true }

                SettingsButton {
                    text: qsTr("取消")
                    onClicked: settingsDialog.reject()
                }

                SettingsButton {
                    objectName: "saveKnowledgeSettingsButton"
                    text: qsTr("保存")
                    primary: true
                    onClicked: root.saveKnowledgeSettings()
                }
            }
        }
    }

    Dialog {
        id: deleteDialog
        objectName: "deleteKnowledgeBaseDialog"
        title: qsTr("删除知识库？")
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(420, root.width - UI.Theme.space32 * 2)
        padding: UI.Theme.space24
        closePolicy: Popup.CloseOnEscape
        onOpened: cancelDeleteButton.forceActiveFocus()

        background: Rectangle {
            color: UI.Theme.surface
            border.color: UI.Theme.border
            radius: UI.Theme.radiusLarge
        }

        header: Label {
            text: deleteDialog.title
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
                text: qsTr("删除后，知识库中的文档与索引会一并移除，无法恢复。")
                color: UI.Theme.textSecondary
                font.family: UI.Theme.fontFamily
                font.pixelSize: UI.Theme.fontBody
                wrapMode: Text.Wrap
                Layout.fillWidth: true
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
                id: cancelDeleteButton
                text: qsTr("取消")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }

            SettingsButton {
                objectName: "confirmDeleteKnowledgeBaseButton"
                text: qsTr("删除知识库")
                destructive: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }

            onAccepted: root.confirmDeleteKnowledgeBase()
            onRejected: deleteDialog.reject()
        }
    }
}
