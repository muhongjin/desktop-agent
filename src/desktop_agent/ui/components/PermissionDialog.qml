import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: root
    property string capability: ""
    property string targetPath: ""
    signal resolved(bool allowed)

    title: qsTr("需要确认")
    modal: true
    standardButtons: Dialog.NoButton
    width: 480

    ColumnLayout {
        width: parent.width
        spacing: 12

        Label {
            text: root.capability
            font.weight: Font.DemiBold
            Layout.fillWidth: true
        }

        TextField {
            text: root.targetPath
            readOnly: true
            selectByMouse: true
            Layout.fillWidth: true
        }

        DialogButtonBox {
            Layout.fillWidth: true

            Button {
                text: qsTr("拒绝")
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                onClicked: {
                    root.resolved(false)
                    root.close()
                }
            }

            Button {
                text: qsTr("允许一次")
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                onClicked: {
                    root.resolved(true)
                    root.close()
                }
            }
        }
    }
}
