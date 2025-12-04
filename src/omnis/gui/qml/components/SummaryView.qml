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
    signal installClicked()
    signal previousClicked()
    signal editSection(string section)
    signal editLocale()
    signal editUsers()
    signal editPartition()

    // External properties - selections from previous steps
    property var selections: ({
        "locale": "en_US.UTF-8",
        "timezone": "UTC",
        "keymap": "us",
        "username": "",
        "fullName": "",
        "hostname": "",
        "autoLogin": false,
        "isAdmin": true,
        "disk": "",
        "diskSize": "",
        "partitionMode": "auto"
    })

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
            anchors.fill: parent
            contentWidth: availableWidth
            clip: true

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
                        Layout.preferredHeight: systemColumn.height + 48
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
                                            text: selections.hostname || qsTr("Not set")
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
                        Layout.preferredHeight: localeColumn.height + 48
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
                                            text: selections.locale || qsTr("Not set")
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
                                            text: selections.timezone || qsTr("Not set")
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
                                            text: selections.keymap || qsTr("Not set")
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
                        Layout.preferredHeight: userColumn.height + 48
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
                                            text: selections.username || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Full name
                                    Row {
                                        spacing: 12
                                        width: parent.width
                                        visible: (selections.fullName || "").length > 0

                                        Text {
                                            text: qsTr("Full Name:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: selections.fullName || ""
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
                                                text: selections.isAdmin ? "\u2713" : "\u2717"
                                                font.pixelSize: 14
                                                color: selections.isAdmin ? successColor : textMutedColor
                                            }

                                            Text {
                                                text: selections.isAdmin ? qsTr("Yes") : qsTr("No")
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
                                                text: selections.autoLogin ? "\u2713" : "\u2717"
                                                font.pixelSize: 14
                                                color: selections.autoLogin ? successColor : textMutedColor
                                            }

                                            Text {
                                                text: selections.autoLogin ? qsTr("Enabled") : qsTr("Disabled")
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

                    // Storage section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: storageColumn.height + 48
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
                                            text: selections.disk || qsTr("Not set")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }
                                    }

                                    // Size
                                    Row {
                                        spacing: 12
                                        width: parent.width
                                        visible: (selections.diskSize || "").length > 0

                                        Text {
                                            text: qsTr("Size:")
                                            font.pixelSize: 14
                                            color: textMutedColor
                                            width: 160
                                        }

                                        Text {
                                            text: selections.diskSize || qsTr("Unknown")
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
                                            text: selections.partitionMode === "auto" ? qsTr("Automatic") : qsTr("Manual")
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
                    Layout.preferredHeight: finalWarningColumn.height + 32
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
                    }
                }

                Item { Layout.preferredHeight: 16 }

                // Navigation buttons
                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 800
                    spacing: 16

                    Button {
                        text: qsTr("Previous")
                        Layout.preferredWidth: 150
                        Layout.preferredHeight: 48
                        font.pixelSize: 16

                        background: Rectangle {
                            radius: 8
                            color: parent.pressed ? Qt.darker(surfaceColor, 1.2) : surfaceColor
                            border.color: textMutedColor
                            border.width: 1

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }
                        }

                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: textColor
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: root.previousClicked()
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: qsTr("Install Now")
                        Layout.preferredWidth: 200
                        Layout.preferredHeight: 56
                        font.pixelSize: 18
                        font.bold: true

                        background: Rectangle {
                            radius: 12
                            color: {
                                if (parent.pressed) return Qt.darker(successColor, 1.3)
                                if (parent.hovered) return Qt.lighter(successColor, 1.15)
                                return successColor
                            }
                            border.color: Qt.lighter(successColor, 1.3)
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }

                            // Gradient overlay
                            Rectangle {
                                anchors.fill: parent
                                radius: parent.radius
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.15) }
                                    GradientStop { position: 0.5; color: "transparent" }
                                }
                            }
                        }

                        contentItem: Row {
                            spacing: 12
                            anchors.centerIn: parent

                            Text {
                                text: parent.parent.text
                                font: parent.parent.font
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: "\u{1F680}"
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        onClicked: root.installClicked()
                    }
                }

                Item { height: 24 }
            }
        }
    }
}
