/*
 * PartitionView - Disk Selection and Partitioning
 *
 * Displays:
 * - List of available disks with details
 * - Partitioning mode selection (Auto/Manual)
 * - Data loss warning
 * - Partition details for manual mode
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // Signals
    signal nextClicked()
    signal previousClicked()
    signal diskSelected(string disk)
    signal modeSelected(string mode)

    // External properties
    property var disksModel: []  // Array of disk objects: {name, size, type, removable, partitions}
    property string selectedDisk: ""
    property string partitionMode: "auto"  // "auto" or "manual"

    // Emit signals when selections change
    onSelectedDiskChanged: if (selectedDisk) diskSelected(selectedDisk)
    onPartitionModeChanged: if (partitionMode) modeSelected(partitionMode)

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

    readonly property bool canProceed: selectedDisk !== ""

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
                    text: qsTr("Select Installation Disk")
                    font.pixelSize: 32
                    font.bold: true
                    color: textColor
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: qsTr("Choose where to install the system")
                    font.pixelSize: 16
                    color: textMutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                // Warning banner
                Rectangle {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
                    Layout.preferredHeight: warningColumn.height + 32
                    radius: 12
                    color: Qt.rgba(errorColor.r, errorColor.g, errorColor.b, 0.15)
                    border.color: errorColor
                    border.width: 2
                    visible: selectedDisk !== ""

                    Column {
                        id: warningColumn
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        Row {
                            spacing: 12

                            Text {
                                text: "\u{26A0}\u{FE0F}"  // Warning sign
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("WARNING: All data on the selected disk will be erased!")
                                font.pixelSize: 16
                                font.bold: true
                                color: errorColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            text: qsTr("Make sure you have backed up all important data before proceeding. This operation cannot be undone.")
                            font.pixelSize: 14
                            color: textColor
                            wrapMode: Text.WordWrap
                            width: parent.width
                        }
                    }
                }

                Item { Layout.preferredHeight: 8 }

                // Disks list
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
                    spacing: 16

                    Text {
                        text: qsTr("Available Disks")
                        font.pixelSize: 20
                        font.bold: true
                        color: textColor
                    }

                    Repeater {
                        model: disksModel

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: diskColumn.height + 32
                            radius: 16
                            color: selectedDisk === modelData.name ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2) : surfaceColor
                            border.color: selectedDisk === modelData.name ? primaryColor : "transparent"
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }

                            Behavior on border.color {
                                ColorAnimation { duration: 150 }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: selectedDisk = modelData.name
                            }

                            Column {
                                id: diskColumn
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                // Disk header
                                Row {
                                    width: parent.width
                                    spacing: 12

                                    Rectangle {
                                        width: 48
                                        height: 48
                                        radius: 8
                                        color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2)

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.removable ? "\u{1F4BE}" : (modelData.type === "SSD" ? "\u{1F4BD}" : "\u{1F4BF}")
                                            font.pixelSize: 24
                                        }
                                    }

                                    Column {
                                        width: parent.width - 60
                                        spacing: 4

                                        Row {
                                            spacing: 8

                                            Text {
                                                text: modelData.name
                                                font.pixelSize: 18
                                                font.bold: true
                                                color: textColor
                                            }

                                            Rectangle {
                                                height: 20
                                                width: typeLabel.width + 16
                                                radius: 4
                                                color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.3)
                                                anchors.verticalCenter: parent.verticalCenter

                                                Text {
                                                    id: typeLabel
                                                    anchors.centerIn: parent
                                                    text: modelData.type || "HDD"
                                                    font.pixelSize: 12
                                                    font.bold: true
                                                    color: textColor
                                                }
                                            }

                                            Rectangle {
                                                height: 20
                                                width: removableLabel.width + 16
                                                radius: 4
                                                color: Qt.rgba(warningColor.r, warningColor.g, warningColor.b, 0.3)
                                                anchors.verticalCenter: parent.verticalCenter
                                                visible: modelData.removable

                                                Text {
                                                    id: removableLabel
                                                    anchors.centerIn: parent
                                                    text: qsTr("REMOVABLE")
                                                    font.pixelSize: 12
                                                    font.bold: true
                                                    color: textColor
                                                }
                                            }
                                        }

                                        Text {
                                            text: qsTr("Size: ") + modelData.size
                                            font.pixelSize: 14
                                            color: textMutedColor
                                        }
                                    }
                                }

                                // Partitions (if manual mode and disk selected)
                                Column {
                                    width: parent.width
                                    spacing: 8
                                    visible: selectedDisk === modelData.name && partitionMode === "manual" && modelData.partitions && modelData.partitions.length > 0

                                    Rectangle {
                                        width: parent.width
                                        height: 1
                                        color: textMutedColor
                                        opacity: 0.3
                                    }

                                    Text {
                                        text: qsTr("Current Partitions:")
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: textColor
                                    }

                                    Repeater {
                                        model: modelData.partitions || []

                                        Row {
                                            spacing: 12
                                            width: parent.width

                                            Rectangle {
                                                width: 8
                                                height: 8
                                                radius: 4
                                                color: accentColor
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            Text {
                                                text: modelData.name + " - " + modelData.size + " (" + modelData.fstype + ")"
                                                font.pixelSize: 13
                                                color: textMutedColor
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }
                                    }
                                }

                                // Selected indicator
                                Rectangle {
                                    width: parent.width
                                    height: 40
                                    radius: 8
                                    color: Qt.rgba(successColor.r, successColor.g, successColor.b, 0.2)
                                    visible: selectedDisk === modelData.name

                                    Row {
                                        anchors.centerIn: parent
                                        spacing: 8

                                        Text {
                                            text: "\u2713"
                                            font.pixelSize: 18
                                            color: successColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: qsTr("Selected for installation")
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: successColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty state
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 200
                        radius: 16
                        color: surfaceColor
                        visible: disksModel.length === 0

                        Column {
                            anchors.centerIn: parent
                            spacing: 16

                            Text {
                                text: "\u{1F4BE}"
                                font.pixelSize: 48
                                anchors.horizontalCenter: parent.horizontalCenter
                            }

                            Text {
                                text: qsTr("No disks found")
                                font.pixelSize: 18
                                font.bold: true
                                color: textColor
                                anchors.horizontalCenter: parent.horizontalCenter
                            }

                            Text {
                                text: qsTr("Please ensure a disk is connected and detected by the system")
                                font.pixelSize: 14
                                color: textMutedColor
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                        }
                    }
                }

                // Partition mode selection
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
                    spacing: 16
                    visible: selectedDisk !== ""

                    Text {
                        text: qsTr("Partitioning Mode")
                        font.pixelSize: 20
                        font.bold: true
                        color: textColor
                    }

                    Row {
                        Layout.fillWidth: true
                        spacing: 16

                        // Auto mode
                        Rectangle {
                            width: (parent.width - 16) / 2
                            height: autoModeColumn.height + 32
                            radius: 16
                            color: partitionMode === "auto" ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2) : surfaceColor
                            border.color: partitionMode === "auto" ? primaryColor : "transparent"
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: partitionMode = "auto"
                            }

                            Column {
                                id: autoModeColumn
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                Row {
                                    spacing: 8

                                    Text {
                                        text: "\u{2699}\u{FE0F}"
                                        font.pixelSize: 24
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    Text {
                                        text: qsTr("Automatic")
                                        font.pixelSize: 18
                                        font.bold: true
                                        color: textColor
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                Text {
                                    width: parent.width
                                    text: qsTr("Erase entire disk and create optimal partition layout automatically")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    wrapMode: Text.WordWrap
                                }

                                Row {
                                    spacing: 8
                                    visible: partitionMode === "auto"

                                    Text {
                                        text: "\u2713"
                                        font.pixelSize: 16
                                        color: successColor
                                    }

                                    Text {
                                        text: qsTr("Recommended for most users")
                                        font.pixelSize: 13
                                        color: successColor
                                    }
                                }
                            }
                        }

                        // Manual mode
                        Rectangle {
                            width: (parent.width - 16) / 2
                            height: manualModeColumn.height + 32
                            radius: 16
                            color: partitionMode === "manual" ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2) : surfaceColor
                            border.color: partitionMode === "manual" ? primaryColor : "transparent"
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: partitionMode = "manual"
                            }

                            Column {
                                id: manualModeColumn
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                Row {
                                    spacing: 8

                                    Text {
                                        text: "\u{1F6E0}\u{FE0F}"
                                        font.pixelSize: 24
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    Text {
                                        text: qsTr("Manual")
                                        font.pixelSize: 18
                                        font.bold: true
                                        color: textColor
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                Text {
                                    width: parent.width
                                    text: qsTr("Choose partitions manually (advanced users)")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    wrapMode: Text.WordWrap
                                }

                                Row {
                                    spacing: 8
                                    visible: partitionMode === "manual"

                                    Text {
                                        text: "\u26A0\uFE0F"
                                        font.pixelSize: 16
                                        color: warningColor
                                    }

                                    Text {
                                        text: qsTr("Requires partitioning knowledge")
                                        font.pixelSize: 13
                                        color: warningColor
                                    }
                                }
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 16 }

                // Navigation buttons
                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
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
                        text: qsTr("Next")
                        Layout.preferredWidth: 150
                        Layout.preferredHeight: 48
                        font.pixelSize: 16
                        font.bold: true
                        enabled: canProceed

                        background: Rectangle {
                            radius: 8
                            color: {
                                if (!parent.enabled) return Qt.darker(surfaceColor, 1.2)
                                if (parent.pressed) return Qt.darker(primaryColor, 1.3)
                                if (parent.hovered) return Qt.lighter(primaryColor, 1.15)
                                return primaryColor
                            }
                            border.color: parent.enabled ? Qt.lighter(primaryColor, 1.3) : "transparent"
                            border.width: 1

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }
                        }

                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: parent.enabled ? textColor : textMutedColor
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: root.nextClicked()
                    }
                }

                Item { height: 24 }
            }
        }
    }
}
