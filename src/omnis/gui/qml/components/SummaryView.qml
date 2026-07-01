/*
 * SummaryView - Installation Summary and Confirmation
 *
 * Displays:
 * - Complete summary of all selections
 * - Edit buttons to modify specific sections
 * - Final confirmation and Install button
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // Signals
    signal editSection(string section)
    signal editLocale()
    signal editUsers()
    signal editEnvironment()
    signal editPartition()

    // Final confirmation gate (ITEM 2): emitted when the user (dis)arms the
    // destructive installation via the confirmation checkbox. Main.qml wires
    // this to engine.setConfirmed() and only enables "Install" when checked.
    signal confirmedToggled(bool confirmed)

    // Two-way reflectable state of the confirmation checkbox. Bound in Main.qml
    // to engine.confirmed so the gate survives navigation back/forth.
    property bool confirmed: false

    // External properties - selections from previous steps.
    //
    // NOTE (fix persistance résumé): ces valeurs sont exposées comme des
    // propriétés SCALAIRES individuelles et bindées dans Main.qml directement
    // aux getters notifiés du bridge (engine.username, engine.hostname, ...).
    // On N'utilise PLUS un unique `property var selections` (dict) : un
    // @Property(object) renvoie une nouvelle copie de dict à chaque lecture, si
    // bien que les bindings `text: selections.X` ne se ré-évaluaient jamais sur
    // selectionsChanged (les sous-propriétés d'un objet JS ne sont pas suivies
    // par QML). Des propriétés scalaires notifiées se propagent de façon fiable.
    property string localeValue: "en_US.UTF-8"
    property string timezoneValue: "UTC"
    property string keymapValue: "us"
    property string usernameValue: ""
    property string fullNameValue: ""
    property string hostnameValue: ""
    property bool autoLoginValue: false
    property bool isAdminValue: true
    property string desktopEnvironmentValue: "gnome"
    property string editionValue: "standard"
    property string diskValue: ""
    property string diskSizeValue: ""
    property string partitionModeValue: "auto"

    // Distro info
    property string distroName: ""
    property string distroVersion: ""
    property string distroLogo: ""

    // Theme colors
    property color primaryColor: "#5597e6"
    property color secondaryColor: "#3a7bc8"
    property color accentColor: "#6b9ce8"
    property color backgroundColor: "#1a1a1a"
    property color surfaceColor: "#32373c"
    property color textColor: "#fffded"
    property color textMutedColor: "#9CA3AF"
    property color successColor: "#10B981"
    property color warningColor: "#F59E0B"
    property color errorColor: "#EF4444"

    // Content container
    Rectangle {
        anchors.fill: parent
        color: "transparent"

        ScrollView {
            id: scrollView
            anchors.fill: parent
            contentWidth: availableWidth
            clip: true

            // Improve wheel scroll speed (3x faster)
            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function(event) {
                    var flickable = scrollView.contentItem
                    var multiplier = 3.0
                    var deltaY = event.angleDelta.y * multiplier
                    var newY = flickable.contentY - (deltaY / 120.0 * 40)
                    flickable.contentY = Math.max(0, Math.min(flickable.contentHeight - flickable.height, newY))
                    event.accepted = true
                }
            }

            ColumnLayout {
                width: parent.width
                anchors.margins: 48
                spacing: 32

                Item { height: 24 }

                // Title
                Text {
                    text: qsTr("Review Installation")
                    font.pixelSize: 32
                    font.bold: true
                    color: textColor
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: qsTr("Please review your selections before starting the installation")
                    font.pixelSize: 16
                    color: textMutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                Item { Layout.preferredHeight: 8 }

                // Summary cards
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 800
                    spacing: 16

                    // System section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: systemColumn.implicitHeight + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: systemColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                Column {
                                    width: parent.width - editSystemButton.width - 12
                                    spacing: 12

                                    Row {
                                        spacing: 12

                                        Text {
                                            text: "\u{1F5A5}\u{FE0F}"
                                            font.pixelSize: 24
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: qsTr("System")
                                            font.pixelSize: 20
                                            font.bold: true
                                            color: textColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }

                                    // Hostname
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Computer Name:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: hostnameValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }
                                }

                                Button {
                                    id: editSystemButton
                                    text: qsTr("Edit")
                                    width: 80
                                    height: 36
                                    anchors.verticalCenter: parent.verticalCenter

                                    background: Rectangle {
                                        radius: 8
                                        color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                        border.color: accentColor
                                        border.width: 1

                                        Behavior on color {
                                            ColorAnimation { duration: 150 }
                                        }
                                    }

                                    contentItem: Text {
                                        text: parent.text
                                        font.pixelSize: 13
                                        color: textColor
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    onClicked: root.editSection("users")
                                }
                            }
                        }
                    }

                    // Locale section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: localeColumn.implicitHeight + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: localeColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                Column {
                                    width: parent.width - editLocaleButton.width - 12
                                    spacing: 12

                                    Row {
                                        spacing: 12

                                        Text {
                                            text: "\u{1F310}"
                                            font.pixelSize: 24
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: qsTr("Locale & Keyboard")
                                            font.pixelSize: 20
                                            font.bold: true
                                            color: textColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }

                                    // Language
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Language:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: localeValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Timezone
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Timezone:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: timezoneValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Keyboard
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Keyboard Layout:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: keymapValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }
                                }

                                Button {
                                    id: editLocaleButton
                                    text: qsTr("Edit")
                                    width: 80
                                    height: 36
                                    anchors.verticalCenter: parent.verticalCenter

                                    background: Rectangle {
                                        radius: 8
                                        color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                        border.color: accentColor
                                        border.width: 1

                                        Behavior on color {
                                            ColorAnimation { duration: 150 }
                                        }
                                    }

                                    contentItem: Text {
                                        text: parent.text
                                        font.pixelSize: 13
                                        color: textColor
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    onClicked: root.editSection("locale")
                                }
                            }
                        }
                    }

                    // User section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: userColumn.implicitHeight + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: userColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                Column {
                                    width: parent.width - editUserButton.width - 12
                                    spacing: 12

                                    Row {
                                        spacing: 12

                                        Text {
                                            text: "\u{1F464}"
                                            font.pixelSize: 24
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: qsTr("User Account")
                                            font.pixelSize: 20
                                            font.bold: true
                                            color: textColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }

                                    // Username
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Username:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: usernameValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Full name
                                    Row {
                                        spacing: 12
                                        width: parent.width
                                        visible: (fullNameValue || "").length > 0

                                        Text {
                                            text: qsTr("Full Name:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: fullNameValue || ""
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Admin status
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Administrator:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Row {
                                            spacing: 6

                                            Text {
                                                text: isAdminValue ? "\u2713" : "\u2717"
                                                font.pixelSize: 14
                                                color: isAdminValue ? successColor : textMutedColor
                                            }

                                            Text {
                                                text: isAdminValue ? qsTr("Yes") : qsTr("No")
                                                font.pixelSize: 14
                                                font.bold: true
                                                color: textColor
                                            }
                                        }
                                    }

                                    // Auto login
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Auto Login:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Row {
                                            spacing: 6

                                            Text {
                                                text: autoLoginValue ? "\u2713" : "\u2717"
                                                font.pixelSize: 14
                                                color: autoLoginValue ? successColor : textMutedColor
                                            }

                                            Text {
                                                text: autoLoginValue ? qsTr("Enabled") : qsTr("Disabled")
                                                font.pixelSize: 14
                                                font.bold: true
                                                color: textColor
                                            }
                                        }
                                    }
                                }

                                Button {
                                    id: editUserButton
                                    text: qsTr("Edit")
                                    width: 80
                                    height: 36
                                    anchors.verticalCenter: parent.verticalCenter

                                    background: Rectangle {
                                        radius: 8
                                        color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                        border.color: accentColor
                                        border.width: 1

                                        Behavior on color {
                                            ColorAnimation { duration: 150 }
                                        }
                                    }

                                    contentItem: Text {
                                        text: parent.text
                                        font.pixelSize: 13
                                        color: textColor
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    onClicked: root.editSection("users")
                                }
                            }
                        }
                    }

                    // Desktop environment & edition section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: environmentColumn.implicitHeight + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: environmentColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                Column {
                                    width: parent.width - editEnvironmentButton.width - 12
                                    spacing: 12

                                    Row {
                                        spacing: 12

                                        Text {
                                            text: "\u{1F5A5}\u{FE0F}"
                                            font.pixelSize: 24
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: qsTr("Desktop & Edition")
                                            font.pixelSize: 20
                                            font.bold: true
                                            color: textColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }

                                    // Desktop environment
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Desktop Environment:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: desktopEnvironmentValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Edition
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Edition:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: editionValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }
                                }

                                Button {
                                    id: editEnvironmentButton
                                    text: qsTr("Edit")
                                    width: 80
                                    height: 36
                                    anchors.verticalCenter: parent.verticalCenter

                                    background: Rectangle {
                                        radius: 8
                                        color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                        border.color: accentColor
                                        border.width: 1

                                        Behavior on color {
                                            ColorAnimation { duration: 150 }
                                        }
                                    }

                                    contentItem: Text {
                                        text: parent.text
                                        font.pixelSize: 13
                                        color: textColor
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    onClicked: root.editEnvironment()
                                }
                            }
                        }
                    }

                    // Storage section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: storageColumn.implicitHeight + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: storageColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                Column {
                                    width: parent.width - editStorageButton.width - 12
                                    spacing: 12

                                    Row {
                                        spacing: 12

                                        Text {
                                            text: "\u{1F4BE}"
                                            font.pixelSize: 24
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: qsTr("Storage")
                                            font.pixelSize: 20
                                            font.bold: true
                                            color: textColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }

                                    // Disk
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Installation Disk:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: diskValue || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Size
                                    Row {
                                        spacing: 12
                                        width: parent.width
                                        visible: (diskSizeValue || "").length > 0

                                        Text {
                                            text: qsTr("Size:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: diskSizeValue || qsTr("Unknown")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Partition mode
                                    Row {
                                        spacing: 12
                                        width: parent.width

                                        Text {
                                            text: qsTr("Partitioning:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: partitionModeValue === "auto" ? qsTr("Automatic") : qsTr("Manual")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }
                                }

                                Button {
                                    id: editStorageButton
                                    text: qsTr("Edit")
                                    width: 80
                                    height: 36
                                    anchors.verticalCenter: parent.verticalCenter

                                    background: Rectangle {
                                        radius: 8
                                        color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                        border.color: accentColor
                                        border.width: 1

                                        Behavior on color {
                                            ColorAnimation { duration: 150 }
                                        }
                                    }

                                    contentItem: Text {
                                        text: parent.text
                                        font.pixelSize: 13
                                        color: textColor
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    onClicked: root.editSection("partition")
                                }
                            }
                        }
                    }
                }

                // Final warning
                Rectangle {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 800
                    Layout.preferredHeight: finalWarningColumn.implicitHeight + 32
                    radius: 12
                    color: Qt.rgba(warningColor.r, warningColor.g, warningColor.b, 0.15)
                    border.color: warningColor
                    border.width: 2

                    Column {
                        id: finalWarningColumn
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        Row {
                            spacing: 12

                            Text {
                                text: "\u{1F4E2}"
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Ready to Install")
                                font.pixelSize: 16
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            text: qsTr("The installation will begin once you click the Install button. This process will modify your disk and cannot be undone. Please ensure all data is backed up.")
                            font.pixelSize: 14
                            color: textColor
                            wrapMode: Text.WordWrap
                            width: parent.width
                        }

                        // ITEM 2: mandatory confirmation checkbox. The "Install"
                        // action stays disabled until this is checked.
                        CheckBox {
                            id: confirmCheckBox
                            width: parent.width
                            checked: root.confirmed
                            onToggled: root.confirmedToggled(checked)

                            contentItem: Text {
                                text: qsTr("I understand that the selected disk (%1) will be modified and erased.")
                                    .arg(diskValue || qsTr("target disk"))
                                font.pixelSize: 14
                                font.bold: true
                                color: textColor
                                wrapMode: Text.WordWrap
                                leftPadding: confirmCheckBox.indicator.width + 8
                                verticalAlignment: Text.AlignVCenter
                                width: parent.width
                            }
                        }
                    }
                }

                Item { height: 24 }
            }
        }
    }
}
