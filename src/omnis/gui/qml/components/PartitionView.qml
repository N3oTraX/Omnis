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
    signal diskSelected(string disk)
    signal modeSelected(string mode)
    // Auto-mode option signals (engine slots added in parallel by bridge agent)
    signal filesystemSelected(string fs)          // "ext4" | "btrfs"
    signal swapStrategySelected(string strategy)  // "file" | "none" | "hibernate"
    signal encryptionToggled(bool enabled)
    signal encryptionPassphraseSet(string passphrase)
    signal efiSizeChanged(int sizeMb)

    // External properties
    property var disksModel: []  // Array of disk objects: {name, size, type, removable, partitions}
    property string selectedDisk: ""
    property string partitionMode: "auto"  // "auto" or "manual"

    // Auto-mode option state (UI-local, pushed up via signals)
    property string filesystem: "ext4"        // "ext4" | "btrfs"
    property string swapStrategy: "file"       // "file" | "none" | "hibernate"
    property bool encryptionEnabled: false
    readonly property int efiSizeMb: 512       // fixed for MVP

    // Encryption passphrase validity (passphrase is NOT bound downward, security)
    readonly property bool encryptionPassValid:
        !encryptionEnabled ||
        (encPassField.text.length >= 8 && encPassField.text === encPassConfirmField.text)

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

    // Histobar partition palette (by partType, with fstype fallback)
    property color colorEfi: "#5597e6"        // efi / vfat
    property color colorLinux: "#10B981"      // ext4 / linux
    property color colorBtrfs: "#F59E0B"      // btrfs
    property color colorWindows: "#38BDF8"    // ntfs / windows
    property color colorSwap: "#A78BFA"       // swap
    property color colorOther: "#9CA3AF"      // other
    property color colorFree: Qt.rgba(0.196, 0.216, 0.235, 0.6)  // free space (surface, semi-transparent)

    // Map a partition (partType/fstype) to its histobar color
    function partitionColor(partType, fstype) {
        var t = (partType || "").toLowerCase()
        var f = (fstype || "").toLowerCase()
        if (t === "efi" || f === "vfat") return colorEfi
        if (t === "swap" || f === "swap") return colorSwap
        if (t === "windows" || f === "ntfs") return colorWindows
        if (f === "btrfs") return colorBtrfs
        if (t === "linux" || f === "ext4" || f === "ext3" || f === "ext2" || f === "xfs") return colorLinux
        return colorOther
    }

    // Human-readable byte size for tooltips/legend
    function humanSize(bytes) {
        if (!bytes || bytes <= 0) return "0 o"
        var units = ["o", "Ko", "Mo", "Go", "To"]
        var i = 0
        var v = bytes
        while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
        return (v >= 100 ? v.toFixed(0) : v.toFixed(1)) + " " + units[i]
    }

    readonly property bool canProceed:
        selectedDisk !== "" && (
            partitionMode === "auto" ? encryptionPassValid : engine.manualPlanValid
        )

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
                    Layout.preferredHeight: warningColumn.implicitHeight + 32
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
                            Layout.preferredHeight: diskColumn.implicitHeight + 32
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

                                        // Device kind detection: nvme > ssd > hdd
                                        property string diskKind: {
                                            var n = (modelData.name || "").toLowerCase()
                                            if (n.indexOf("nvme") !== -1) return "nvme"
                                            if ((modelData.type || "").toUpperCase() === "SSD") return "ssd"
                                            return "hdd"
                                        }

                                        // QML-drawn vector icons (always render, no missing-glyph squares)
                                        Item {
                                            anchors.centerIn: parent
                                            width: 28
                                            height: 28

                                            // --- HDD: classic drive body + platter circle ---
                                            Item {
                                                anchors.fill: parent
                                                visible: parent.parent.diskKind === "hdd"

                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 26
                                                    height: 20
                                                    radius: 3
                                                    color: "transparent"
                                                    border.color: textColor
                                                    border.width: 2

                                                    Rectangle {  // platter
                                                        anchors.centerIn: parent
                                                        anchors.horizontalCenterOffset: -3
                                                        width: 11
                                                        height: 11
                                                        radius: 6
                                                        color: "transparent"
                                                        border.color: textColor
                                                        border.width: 2

                                                        Rectangle {  // spindle
                                                            anchors.centerIn: parent
                                                            width: 3
                                                            height: 3
                                                            radius: 2
                                                            color: textColor
                                                        }
                                                    }

                                                    Rectangle {  // head arm
                                                        anchors.right: parent.right
                                                        anchors.rightMargin: 4
                                                        anchors.bottom: parent.bottom
                                                        anchors.bottomMargin: 4
                                                        width: 8
                                                        height: 2
                                                        rotation: -35
                                                        color: textColor
                                                    }
                                                }
                                            }

                                            // --- SSD: 2.5" enclosure with connector pins ---
                                            Item {
                                                anchors.fill: parent
                                                visible: parent.parent.diskKind === "ssd"

                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 26
                                                    height: 18
                                                    radius: 3
                                                    color: "transparent"
                                                    border.color: textColor
                                                    border.width: 2

                                                    Row {  // chip dots
                                                        anchors.centerIn: parent
                                                        spacing: 4
                                                        Repeater {
                                                            model: 3
                                                            Rectangle {
                                                                width: 4; height: 4; radius: 1
                                                                color: primaryColor
                                                            }
                                                        }
                                                    }

                                                    Row {  // connector pins (bottom edge)
                                                        anchors.bottom: parent.bottom
                                                        anchors.bottomMargin: -3
                                                        anchors.left: parent.left
                                                        anchors.leftMargin: 4
                                                        spacing: 2
                                                        Repeater {
                                                            model: 4
                                                            Rectangle {
                                                                width: 2; height: 3
                                                                color: textColor
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            // --- NVMe: M.2 stick (long thin) with notch + chips ---
                                            Item {
                                                anchors.fill: parent
                                                visible: parent.parent.diskKind === "nvme"

                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 28
                                                    height: 11
                                                    radius: 2
                                                    color: "transparent"
                                                    border.color: textColor
                                                    border.width: 2

                                                    Row {  // chips
                                                        anchors.centerIn: parent
                                                        anchors.horizontalCenterOffset: 2
                                                        spacing: 3
                                                        Repeater {
                                                            model: 2
                                                            Rectangle {
                                                                width: 6; height: 5; radius: 1
                                                                color: primaryColor
                                                            }
                                                        }
                                                    }

                                                    Rectangle {  // edge connector pins
                                                        anchors.left: parent.left
                                                        anchors.leftMargin: 2
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 4
                                                        height: 7
                                                        color: textColor
                                                    }
                                                }

                                                Rectangle {  // mounting notch (semicircle hint)
                                                    anchors.right: parent.right
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    width: 4
                                                    height: 4
                                                    radius: 2
                                                    color: "transparent"
                                                    border.color: textColor
                                                    border.width: 1
                                                }
                                            }
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

                                // Histobar: geometric layout of this disk (partitions + free space)
                                Item {
                                    id: histoBar
                                    width: parent.width
                                    // Match the cumulative height of the 2 text lines (name 18 + size 14 + spacing 4)
                                    implicitHeight: 36
                                    height: implicitHeight

                                    // Capture disk-level data so the inner Repeater's modelData
                                    // (a segment) does not shadow it.
                                    property var diskData: modelData
                                    property real diskBytes: (diskData && diskData.sizeBytes > 0) ? diskData.sizeBytes : 0
                                    // Ordered segments (kind: "partition" | "free") covering the
                                    // whole disk, positioned as they physically sit on the medium.
                                    property var segs: (diskData && diskData.segments) ? diskData.segments : []

                                    Rectangle {
                                        id: histoBarBg
                                        anchors.fill: parent
                                        radius: 6
                                        color: colorFree
                                        clip: true

                                        Row {
                                            anchors.fill: parent
                                            spacing: 0

                                            Repeater {
                                                model: histoBar.segs

                                                Rectangle {
                                                    height: histoBarBg.height
                                                    width: histoBar.diskBytes > 0
                                                        ? histoBarBg.width * (modelData.sizeBytes > 0 ? modelData.sizeBytes : 0) / histoBar.diskBytes
                                                        : 0
                                                    color: modelData.kind === "free"
                                                        ? colorFree
                                                        : partitionColor(modelData.partType, modelData.fstype)
                                                    border.color: modelData.kind === "free" ? "transparent" : Qt.rgba(0, 0, 0, 0.25)
                                                    border.width: modelData.kind === "free" ? 0 : 1

                                                    ToolTip.visible: segHover.hovered && width > 4
                                                    ToolTip.text: modelData.kind === "free"
                                                        ? qsTr("Free space") + "  " + humanSize(modelData.sizeBytes)
                                                        : (modelData.name || "")
                                                            + "  " + humanSize(modelData.sizeBytes)
                                                            + (modelData.fstype ? "  (" + modelData.fstype + ")" : "")

                                                    HoverHandler { id: segHover }
                                                }
                                            }
                                        }
                                    }

                                    // Subtle outline on the whole bar
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 6
                                        color: "transparent"
                                        border.color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                                        border.width: 1
                                    }
                                }

                                // Manual mode: assign existing partitions (mount + format)
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
                                        text: qsTr("Assign existing partitions")
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: textColor
                                    }

                                    Repeater {
                                        model: modelData.partitions || []

                                        RowLayout {
                                            width: parent.width
                                            spacing: 10

                                            Rectangle {
                                                Layout.preferredWidth: 10
                                                Layout.preferredHeight: 10
                                                radius: 5
                                                color: partitionColor(modelData.partType, modelData.fstype)
                                            }

                                            Text {
                                                Layout.preferredWidth: 160
                                                text: modelData.name + "  " + humanSize(modelData.sizeBytes)
                                                    + (modelData.fstype ? "  " + modelData.fstype : "")
                                                font.pixelSize: 13
                                                color: textColor
                                                elide: Text.ElideRight
                                            }

                                            // Mount point
                                            ComboBox {
                                                id: mpCombo
                                                Layout.preferredWidth: 130
                                                property string pname: modelData.name
                                                model: ["—", "/", "/boot", "/boot/efi", "/home", "swap"]
                                                Component.onCompleted: {
                                                    var mp = engine.partitionMount(pname)
                                                    var idx = mp === "" ? 0 : model.indexOf(mp)
                                                    currentIndex = idx < 0 ? 0 : idx
                                                }
                                                onActivated: engine.setPartitionMount(
                                                    pname, currentIndex === 0 ? "" : model[currentIndex])
                                            }

                                            // Format toggle
                                            CheckBox {
                                                id: fmtCheck
                                                text: qsTr("Format")
                                                property string pname: modelData.name
                                                Component.onCompleted: checked = engine.partitionFormat(pname)
                                                onToggled: engine.setPartitionFormat(pname, checked)
                                            }

                                            // Target filesystem (only relevant when formatting)
                                            ComboBox {
                                                Layout.preferredWidth: 100
                                                enabled: fmtCheck.checked
                                                opacity: enabled ? 1.0 : 0.4
                                                property string pname: modelData.name
                                                model: ["ext4", "btrfs", "vfat", "swap"]
                                                Component.onCompleted: {
                                                    var fs = engine.partitionFsType(pname) || modelData.fstype || "ext4"
                                                    var idx = model.indexOf(fs)
                                                    currentIndex = idx < 0 ? 0 : idx
                                                    if (engine.partitionFsType(pname) === "")
                                                        engine.setPartitionFsType(pname, model[currentIndex])
                                                }
                                                onActivated: engine.setPartitionFsType(pname, model[currentIndex])
                                            }

                                            Item { Layout.fillWidth: true }
                                        }
                                    }

                                    // Validation hint
                                    Text {
                                        width: parent.width
                                        visible: !engine.manualPlanValid
                                        text: {
                                            switch (engine.manualPlanState) {
                                            case "no_root": return qsTr("Assign a partition to / (root) to continue")
                                            case "multi_root": return qsTr("Only one partition can be mounted at /")
                                            case "dupe": return qsTr("Two partitions share the same mount point")
                                            default: return ""
                                            }
                                        }
                                        color: "#E0A83C"
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
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
                            height: autoModeColumn.implicitHeight + 32
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
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 16
                                spacing: 12

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
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
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
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
                            height: manualModeColumn.implicitHeight + 32
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
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 16
                                spacing: 12

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
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
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
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

                // Auto-mode options card (visible only in auto mode + disk selected)
                Rectangle {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
                    Layout.preferredHeight: optionsColumn.implicitHeight + 40
                    radius: 16
                    color: surfaceColor
                    visible: selectedDisk !== "" && partitionMode === "auto"

                    Column {
                        id: optionsColumn
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 20
                        spacing: 18

                        Text {
                            text: qsTr("Options")
                            font.pixelSize: 20
                            font.bold: true
                            color: textColor
                        }

                        // --- Filesystem ---
                        Column {
                            width: parent.width
                            spacing: 8

                            Text {
                                text: qsTr("Filesystem")
                                font.pixelSize: 15
                                font.bold: true
                                color: textColor
                            }

                            Row {
                                spacing: 24

                                RadioButton {
                                    text: qsTr("ext4")
                                    checked: filesystem === "ext4"
                                    onClicked: { filesystem = "ext4"; filesystemSelected("ext4") }
                                    contentItem: Text {
                                        text: parent.text
                                        color: textColor
                                        font.pixelSize: 14
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: parent.indicator.width + parent.spacing
                                    }
                                }

                                RadioButton {
                                    text: qsTr("btrfs")
                                    checked: filesystem === "btrfs"
                                    onClicked: { filesystem = "btrfs"; filesystemSelected("btrfs") }
                                    contentItem: Text {
                                        text: parent.text
                                        color: textColor
                                        font.pixelSize: 14
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: parent.indicator.width + parent.spacing
                                    }
                                }
                            }
                        }

                        // --- Swap ---
                        Column {
                            width: parent.width
                            spacing: 8

                            Text {
                                text: qsTr("Swap")
                                font.pixelSize: 15
                                font.bold: true
                                color: textColor
                            }

                            Row {
                                spacing: 24

                                RadioButton {
                                    text: qsTr("File (auto)")
                                    checked: swapStrategy === "file"
                                    onClicked: { swapStrategy = "file"; swapStrategySelected("file") }
                                    contentItem: Text {
                                        text: parent.text
                                        color: textColor
                                        font.pixelSize: 14
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: parent.indicator.width + parent.spacing
                                    }
                                }

                                RadioButton {
                                    text: qsTr("None")
                                    checked: swapStrategy === "none"
                                    onClicked: { swapStrategy = "none"; swapStrategySelected("none") }
                                    contentItem: Text {
                                        text: parent.text
                                        color: textColor
                                        font.pixelSize: 14
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: parent.indicator.width + parent.spacing
                                    }
                                }

                                RadioButton {
                                    text: qsTr("Hibernation")
                                    checked: swapStrategy === "hibernate"
                                    onClicked: { swapStrategy = "hibernate"; swapStrategySelected("hibernate") }
                                    contentItem: Text {
                                        text: parent.text
                                        color: textColor
                                        font.pixelSize: 14
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: parent.indicator.width + parent.spacing
                                    }
                                }
                            }
                        }

                        // --- LUKS encryption ---
                        Column {
                            width: parent.width
                            spacing: 12

                            CheckBox {
                                id: encryptionCheck
                                text: qsTr("Enable encryption (LUKS)")
                                checked: encryptionEnabled
                                onToggled: {
                                    encryptionEnabled = checked
                                    encryptionToggled(checked)
                                }
                                contentItem: Text {
                                    text: encryptionCheck.text
                                    color: textColor
                                    font.pixelSize: 15
                                    font.bold: true
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: encryptionCheck.indicator.width + encryptionCheck.spacing
                                }
                            }

                            // Passphrase fields (collapse when disabled)
                            ColumnLayout {
                                width: parent.width
                                spacing: 8
                                visible: encryptionEnabled
                                // collapse: zero height contribution when hidden
                                height: visible ? implicitHeight : 0

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        spacing: 8

                                        TextField {
                                            id: encPassField
                                            Layout.fillWidth: true
                                            height: 40
                                            placeholderText: qsTr("Passphrase (min 8 characters)")
                                            font.pixelSize: 16
                                            echoMode: showEncPassCheck.checked ? TextInput.Normal : TextInput.Password

                                            onTextChanged: {
                                                if (encryptionPassValid && encryptionEnabled)
                                                    encryptionPassphraseSet(text)
                                            }

                                            background: Rectangle {
                                                radius: 8
                                                color: encPassField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                                border.color: {
                                                    if (!encPassField.activeFocus) return textMutedColor;
                                                    if (encPassField.text.length === 0) return primaryColor;
                                                    return encPassField.text.length >= 8 ? successColor : errorColor;
                                                }
                                                border.width: 2
                                                Behavior on border.color { ColorAnimation { duration: 150 } }
                                            }

                                            color: textColor
                                            selectionColor: primaryColor
                                            selectedTextColor: textColor
                                            leftPadding: 16
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        spacing: 8

                                        TextField {
                                            id: encPassConfirmField
                                            Layout.fillWidth: true
                                            height: 40
                                            placeholderText: qsTr("Confirm passphrase")
                                            font.pixelSize: 16
                                            echoMode: showEncPassCheck.checked ? TextInput.Normal : TextInput.Password

                                            onTextChanged: {
                                                if (encryptionPassValid && encryptionEnabled)
                                                    encryptionPassphraseSet(encPassField.text)
                                            }

                                            background: Rectangle {
                                                radius: 8
                                                color: encPassConfirmField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                                border.color: {
                                                    if (!encPassConfirmField.activeFocus) return textMutedColor;
                                                    if (encPassConfirmField.text.length === 0) return primaryColor;
                                                    return (encPassConfirmField.text === encPassField.text) ? successColor : errorColor;
                                                }
                                                border.width: 2
                                                Behavior on border.color { ColorAnimation { duration: 150 } }
                                            }

                                            color: textColor
                                            selectionColor: primaryColor
                                            selectedTextColor: textColor
                                            leftPadding: 16
                                        }

                                        // Match indicator
                                        Row {
                                            Layout.fillWidth: true
                                            spacing: 8
                                            visible: encPassConfirmField.text.length > 0

                                            Text {
                                                text: (encPassConfirmField.text === encPassField.text) ? "✓" : "✗"
                                                font.pixelSize: 13
                                                color: (encPassConfirmField.text === encPassField.text) ? successColor : errorColor
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            Text {
                                                text: (encPassConfirmField.text === encPassField.text)
                                                    ? qsTr("Passphrases match")
                                                    : qsTr("Passphrases do not match")
                                                font.pixelSize: 11
                                                color: (encPassConfirmField.text === encPassField.text) ? successColor : errorColor
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }
                                    }
                                }

                                CheckBox {
                                    id: showEncPassCheck
                                    text: qsTr("Show passphrase")
                                    contentItem: Text {
                                        text: showEncPassCheck.text
                                        color: textMutedColor
                                        font.pixelSize: 13
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: showEncPassCheck.indicator.width + showEncPassCheck.spacing
                                    }
                                }
                            }
                        }

                        // --- EFI partition (read-only info, MVP) ---
                        Column {
                            width: parent.width
                            spacing: 8

                            Text {
                                text: qsTr("EFI Partition")
                                font.pixelSize: 15
                                font.bold: true
                                color: textColor
                            }

                            Text {
                                text: qsTr("512 MB (mounted on /boot)")
                                font.pixelSize: 14
                                color: textMutedColor
                            }
                        }
                    }
                }

                // Histobar legend (compact)
                Row {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
                    spacing: 16
                    visible: disksModel.length > 0

                    Repeater {
                        model: [
                            { c: colorEfi, label: qsTr("EFI") },
                            { c: colorLinux, label: qsTr("Linux") },
                            { c: colorBtrfs, label: qsTr("btrfs") },
                            { c: colorWindows, label: qsTr("Windows") },
                            { c: colorSwap, label: qsTr("Swap") },
                            { c: colorFree, label: qsTr("Free") }
                        ]

                        Row {
                            spacing: 6

                            Rectangle {
                                width: 12
                                height: 12
                                radius: 3
                                color: modelData.c
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: modelData.label
                                font.pixelSize: 12
                                color: textMutedColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }

                Item { height: 24 }
            }
        }
    }
}
