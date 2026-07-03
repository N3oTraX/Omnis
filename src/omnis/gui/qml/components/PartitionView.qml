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
    // Sélections : miroirs descendants (lecture seule) de la source de vérité
    // `engine`. Jamais réassignés impérativement (les clics émettent des signaux
    // relayés par Main.qml vers engine.setX), donc ces bindings restent vivants
    // et reflètent toujours l'état courant après un retour arrière / le résumé.
    readonly property string selectedDisk: engine.selectedDisk
    readonly property string partitionMode: engine.partitionMode  // "auto" | "manual"
    readonly property string filesystem: engine.filesystem        // "ext4" | "btrfs"
    readonly property string swapStrategy: engine.swapStrategy     // "file" | "none" | "hibernate"
    readonly property bool encryptionEnabled: engine.encryption
    readonly property int efiSizeMb: 512       // fixed for MVP

    // Encryption passphrase validity (passphrase is NOT bound downward, security)
    readonly property bool encryptionPassValid:
        !encryptionEnabled ||
        (encPassField.text.length >= 8 && encPassField.text === encPassConfirmField.text)

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

    // --- Manual editor: unit conversions (1 MiB = 2048 sectors of 512 bytes) ---
    readonly property int sectorsPerMib: 2048
    function mibToSectors(mib) { return Math.round(mib) * sectorsPerMib }
    function sectorsToMib(sectors) { return Math.floor((sectors || 0) / sectorsPerMib) }
    function sectorsToBytes(sectors) { return (sectors || 0) * 512 }

    // Color for a simulated segment (existing/new/free) reusing partitionColor.
    function segmentColor(seg) {
        if (!seg) return colorFree
        if (seg.kind === "free") return colorFree
        return partitionColor(seg.partType, seg.fstype)
    }

    // --- Manual editor: defensive readonly mirrors of the (parallel) backend ---
    // These Property/slots are implemented by the bridge agent. Until then the
    // `|| []` / fallbacks keep the UI inert but crash-free.
    readonly property var simulatedSegments: (engine.simulatedSegments || [])
    readonly property var pendingOperations: (engine.pendingOperations || [])
    readonly property var commandPreview: (engine.commandPreview || [])
    readonly property string manualPlanError: (engine.manualPlanError || "")

    // Local UI state for the interactive editor. `selectedSegmentIndex` points
    // into `simulatedSegments`; the derived object is exposed for the action
    // panel and forms. Reset whenever the disk or the simulated geometry changes.
    property int selectedSegmentIndex: -1
    readonly property var selectedSegment:
        (selectedSegmentIndex >= 0 && selectedSegmentIndex < simulatedSegments.length)
            ? simulatedSegments[selectedSegmentIndex]
            : null

    // Which contextual form is open: "" | "create" | "resize" | "format" | "flags"
    property string activeForm: ""

    // Clear the selection/forms when the disk or simulated layout changes.
    onSelectedDiskChanged: { selectedSegmentIndex = -1; activeForm = "" }
    onSimulatedSegmentsChanged: { selectedSegmentIndex = -1; activeForm = "" }

    // Human-readable description of a pending operation for the file list.
    function operationLabel(op) {
        if (!op) return ""
        var p = op.params || {}
        switch (op.type) {
        case "create": {
            var mib = sectorsToMib(p.size_sectors)
            var mp = p.mountpoint ? " " + p.mountpoint : ""
            return qsTr("Create") + mp + " " + (p.fstype || "") + " "
                + humanSize(sectorsToBytes(p.size_sectors))
        }
        case "delete":
            return qsTr("Delete") + " " + (op.target || "")
        case "format":
            return qsTr("Format") + " " + (p.path || op.target || "")
                + " → " + (p.fstype || "")
                + (p.mountpoint ? " (" + p.mountpoint + ")" : "")
        case "setflag":
            return qsTr("Flag") + " " + (op.target || "") + " " + (p.flag || "")
                + " " + (p.state ? qsTr("on") : qsTr("off"))
        case "resize":
            return qsTr("Resize") + " " + (p.path || op.target || "")
                + " → " + humanSize(sectorsToBytes(p.new_size_sectors))
        default:
            return op.type + " " + (op.target || "")
        }
    }

    // Safe wrappers around the (parallel) backend slots. No-op if absent so the
    // offscreen harness and pre-integration runs never throw.
    function addOperation(op) {
        // Pass as JSON: a plain QML object does not marshal reliably to the
        // QVariant slot across PySide6 versions (the slot would never fire).
        if (engine.addPartitionOperation) engine.addPartitionOperation(JSON.stringify(op))
        activeForm = ""
    }
    function removeOperation(index) {
        if (engine.removePartitionOperation) engine.removePartitionOperation(index)
    }
    function resetOperations() {
        if (engine.resetPartitionOperations) engine.resetPartitionOperations()
        selectedSegmentIndex = -1
        activeForm = ""
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
                                onClicked: diskSelected(modelData.name)
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
                                onClicked: modeSelected("auto")
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
                                onClicked: modeSelected("manual")
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
                                    onClicked: filesystemSelected("ext4")
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
                                    onClicked: filesystemSelected("btrfs")
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
                                    onClicked: swapStrategySelected("file")
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
                                    onClicked: swapStrategySelected("none")
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
                                    onClicked: swapStrategySelected("hibernate")
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
                                onToggled: encryptionToggled(checked)
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

                // ============================================================
                // Manual editor card (GParted-style): interactive histobar,
                // contextual actions, create/resize forms, pending operations.
                // Visible only in manual mode with a disk selected.
                // ============================================================
                Rectangle {
                    id: manualEditorCard
                    objectName: "manualEditorCard"
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 900
                    Layout.preferredHeight: manualEditorColumn.implicitHeight + 40
                    radius: 16
                    color: surfaceColor
                    visible: selectedDisk !== "" && partitionMode === "manual"

                    Column {
                        id: manualEditorColumn
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 20
                        spacing: 18

                        Text {
                            text: qsTr("Partition Editor")
                            font.pixelSize: 20
                            font.bold: true
                            color: textColor
                        }

                        Text {
                            width: parent.width
                            text: qsTr("Click a segment on the bar below, choose an action and "
                                + "Add to queue, then click Apply changes to write them to the disk.")
                            font.pixelSize: 13
                            color: textMutedColor
                            wrapMode: Text.WordWrap
                        }

                        // ---- Interactive histobar (from simulatedSegments) ----
                        Item {
                            id: editorBar
                            width: parent.width
                            implicitHeight: 56
                            height: implicitHeight

                            property var segs: simulatedSegments
                            property real totalSectors: {
                                var t = 0
                                for (var i = 0; i < segs.length; i++)
                                    t += (segs[i].sizeSectors || 0)
                                return t
                            }

                            Rectangle {
                                id: editorBarBg
                                anchors.fill: parent
                                radius: 8
                                color: colorFree
                                clip: true

                                Row {
                                    anchors.fill: parent
                                    spacing: 0

                                    Repeater {
                                        model: editorBar.segs

                                        Rectangle {
                                            id: segRect
                                            height: editorBarBg.height
                                            width: editorBar.totalSectors > 0
                                                ? editorBarBg.width * (modelData.sizeSectors > 0 ? modelData.sizeSectors : 0) / editorBar.totalSectors
                                                : 0
                                            color: {
                                                var base = segmentColor(modelData)
                                                if (modelData.pendingDelete)
                                                    return Qt.rgba(errorColor.r, errorColor.g, errorColor.b, 0.35)
                                                return base
                                            }
                                            border.width: (selectedSegmentIndex === index) ? 3 : 1
                                            border.color: (selectedSegmentIndex === index)
                                                ? primaryColor
                                                : (modelData.kind === "free"
                                                    ? Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.3)
                                                    : Qt.rgba(0, 0, 0, 0.25))

                                            // "new" segments get a primaryColor inner liseré
                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: 3
                                                color: "transparent"
                                                visible: modelData.kind === "new"
                                                border.color: primaryColor
                                                border.width: 1
                                            }

                                            // pendingDelete hatch hint
                                            Text {
                                                anchors.centerIn: parent
                                                visible: modelData.pendingDelete && segRect.width > 24
                                                text: "✕"
                                                color: errorColor
                                                font.pixelSize: 16
                                            }

                                            // Small in-bar label when wide enough
                                            Text {
                                                anchors.centerIn: parent
                                                visible: !modelData.pendingDelete && segRect.width > 60
                                                width: parent.width - 8
                                                horizontalAlignment: Text.AlignHCenter
                                                elide: Text.ElideRight
                                                text: modelData.kind === "free"
                                                    ? qsTr("Free")
                                                    : (modelData.name || modelData.fstype || "")
                                                color: textColor
                                                font.pixelSize: 11
                                                font.bold: true
                                            }

                                            ToolTip.visible: editSegHover.hovered && segRect.width > 4
                                            ToolTip.text: modelData.kind === "free"
                                                ? qsTr("Free space") + "  " + humanSize(modelData.sizeBytes)
                                                : (modelData.name || "")
                                                    + "  " + humanSize(modelData.sizeBytes)
                                                    + (modelData.fstype ? "  (" + modelData.fstype + ")" : "")
                                                    + (modelData.mountpoint ? "  → " + modelData.mountpoint : "")

                                            HoverHandler { id: editSegHover }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    selectedSegmentIndex = index
                                                    activeForm = ""
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Whole-bar outline
                            Rectangle {
                                anchors.fill: parent
                                radius: 8
                                color: "transparent"
                                border.color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                                border.width: 1
                            }
                        }

                        // Empty-geometry hint (backend not ready or no segments)
                        Text {
                            width: parent.width
                            visible: simulatedSegments.length === 0
                            text: qsTr("No partition geometry available for this disk yet.")
                            font.pixelSize: 13
                            color: textMutedColor
                            wrapMode: Text.WordWrap
                        }

                        // ---- Apply bar (always visible; GParted-style live apply) ----
                        Rectangle {
                            width: parent.width
                            visible: simulatedSegments.length > 0
                            implicitHeight: applyBarRow.implicitHeight + 20
                            height: implicitHeight
                            radius: 10
                            color: Qt.rgba(0, 0, 0, 0.18)

                            RowLayout {
                                id: applyBarRow
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: 12
                                spacing: 12

                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 13
                                    color: pendingOperations.length === 0
                                        ? textMutedColor
                                        : (engine.operationsApplicable ? textColor : errorColor)
                                    text: pendingOperations.length === 0
                                        ? qsTr("No pending operation yet — select a segment and Add to queue.")
                                        : (engine.operationsApplicable
                                            ? qsTr("%1 operation(s) queued").replace("%1", pendingOperations.length)
                                            : qsTr("Cannot apply: %1").replace("%1", engine.operationsApplicableError))
                                }

                                Button {
                                    text: qsTr("Reset")
                                    enabled: pendingOperations.length > 0 && !engine.partitionApplying
                                    onClicked: resetOperations()
                                }

                                Button {
                                    text: engine.partitionApplying
                                        ? qsTr("Applying…")
                                        : qsTr("Apply changes")
                                    highlighted: true
                                    // GParted-style: gate on structural applicability, NOT the full
                                    // installable-layout rule (root/ESP) which gates navigation.
                                    enabled: pendingOperations.length > 0
                                        && engine.operationsApplicable && !engine.partitionApplying
                                    onClicked: engine.applyPartitionOperations()
                                }
                            }
                        }

                        // Live-apply result feedback (GParted-style apply).
                        Text {
                            id: applyResultText
                            width: parent.width
                            visible: text.length > 0
                            wrapMode: Text.WordWrap
                            font.pixelSize: 12
                            property bool ok: false
                            color: ok ? successColor : errorColor
                        }

                        Connections {
                            target: engine
                            function onPartitionApplyFinished(success, message) {
                                applyResultText.ok = success
                                applyResultText.text = (success
                                    ? qsTr("Applied. ") : qsTr("Apply failed: ")) + message
                            }
                        }

                        // ---- Selection summary ----
                        Rectangle {
                            width: parent.width
                            visible: selectedSegment !== null
                            implicitHeight: selInfoRow.implicitHeight + 20
                            height: implicitHeight
                            radius: 10
                            color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.12)
                            border.color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.4)
                            border.width: 1

                            Row {
                                id: selInfoRow
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: 12
                                spacing: 12

                                Rectangle {
                                    width: 12; height: 12; radius: 3
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: segmentColor(selectedSegment)
                                }

                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: {
                                        if (!selectedSegment) return ""
                                        if (selectedSegment.kind === "free")
                                            return qsTr("Free space") + "  " + humanSize(selectedSegment.sizeBytes)
                                        return (selectedSegment.name || "")
                                            + "  " + humanSize(selectedSegment.sizeBytes)
                                            + (selectedSegment.fstype ? "  " + selectedSegment.fstype : "")
                                            + (selectedSegment.mountpoint ? "  → " + selectedSegment.mountpoint : "")
                                    }
                                    color: textColor
                                    font.pixelSize: 14
                                    font.bold: true
                                }
                            }
                        }

                        // ---- Contextual action panel ----
                        Flow {
                            width: parent.width
                            spacing: 10
                            visible: selectedSegment !== null

                            // Helper: is the selected segment an editable existing partition?
                            property bool isFree: selectedSegment && selectedSegment.kind === "free"
                            property bool isExisting: selectedSegment
                                && (selectedSegment.kind === "existing" || selectedSegment.kind === "new")
                                && !(selectedSegment.pendingDelete === true)

                            // New partition (free only)
                            Button {
                                text: qsTr("+ New partition")
                                enabled: parent.isFree
                                onClicked: activeForm = (activeForm === "create" ? "" : "create")
                            }
                            // Delete (existing)
                            Button {
                                text: qsTr("Delete")
                                enabled: parent.isExisting && selectedSegment && selectedSegment.kind === "existing"
                                onClicked: {
                                    addOperation({
                                        type: "delete",
                                        target: selectedSegment.name,
                                        params: { number: (selectedSegment.number || 0) }
                                    })
                                }
                            }
                            // Resize (existing)
                            Button {
                                text: qsTr("Resize")
                                enabled: parent.isExisting
                                onClicked: activeForm = (activeForm === "resize" ? "" : "resize")
                            }
                            // Format (existing)
                            Button {
                                text: qsTr("Format")
                                enabled: parent.isExisting
                                onClicked: activeForm = (activeForm === "format" ? "" : "format")
                            }
                            // Flags (existing)
                            Button {
                                text: qsTr("Flags")
                                enabled: parent.isExisting
                                onClicked: activeForm = (activeForm === "flags" ? "" : "flags")
                            }
                        }

                        // ==== FORM: New partition (on selected free segment) ====
                        Rectangle {
                            width: parent.width
                            visible: activeForm === "create" && selectedSegment
                                && selectedSegment.kind === "free"
                            implicitHeight: createForm.implicitHeight + 28
                            height: implicitHeight
                            radius: 10
                            color: Qt.rgba(0, 0, 0, 0.18)
                            border.color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                            border.width: 1

                            // Free size in MiB (bound to the selected free segment).
                            property int freeMib: selectedSegment
                                ? sectorsToMib(selectedSegment.sizeSectors) : 0

                            Column {
                                id: createForm
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 14
                                spacing: 12

                                Text {
                                    text: qsTr("New partition")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                }

                                // Size (slider + numeric field), bounded by free size
                                Column {
                                    width: parent.width
                                    spacing: 6

                                    Text {
                                        text: qsTr("Size (MiB)")
                                        font.pixelSize: 13
                                        color: textMutedColor
                                    }

                                    Row {
                                        width: parent.width
                                        spacing: 12

                                        Slider {
                                            id: createSizeSlider
                                            width: parent.width - createSizeField.width - 12
                                            anchors.verticalCenter: parent.verticalCenter
                                            from: 1
                                            to: Math.max(1, parent.parent.parent.freeMib)
                                            stepSize: 1
                                            value: Math.max(1, Math.min(
                                                parent.parent.parent.freeMib,
                                                Math.round(parent.parent.parent.freeMib)))
                                            onMoved: createSizeField.text = Math.round(value).toString()
                                        }

                                        TextField {
                                            id: createSizeField
                                            width: 120
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: Math.round(createSizeSlider.value).toString()
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            validator: IntValidator {
                                                bottom: 1
                                                top: Math.max(1, createForm.parent.freeMib)
                                            }
                                            color: textColor
                                            onEditingFinished: {
                                                var v = parseInt(text)
                                                if (isNaN(v)) v = 1
                                                v = Math.max(1, Math.min(createForm.parent.freeMib, v))
                                                createSizeSlider.value = v
                                                text = v.toString()
                                            }
                                        }
                                    }

                                    Text {
                                        text: qsTr("Available") + ": " + createForm.parent.freeMib + " MiB ("
                                            + humanSize(sectorsToBytes(mibToSectors(createForm.parent.freeMib))) + ")"
                                        font.pixelSize: 11
                                        color: textMutedColor
                                    }
                                }

                                // Filesystem + mount point + flags
                                Row {
                                    width: parent.width
                                    spacing: 16

                                    Column {
                                        spacing: 4
                                        Text {
                                            text: qsTr("Filesystem")
                                            font.pixelSize: 12
                                            color: textMutedColor
                                        }
                                        ComboBox {
                                            id: createFsCombo
                                            width: 130
                                            model: ["ext4", "btrfs", "vfat", "swap"]
                                        }
                                    }

                                    Column {
                                        spacing: 4
                                        Text {
                                            text: qsTr("Mount point")
                                            font.pixelSize: 12
                                            color: textMutedColor
                                        }
                                        ComboBox {
                                            id: createMountCombo
                                            width: 150
                                            model: ["(none)", "/", "/home", "/boot", "swap"]
                                        }
                                    }

                                    Column {
                                        spacing: 4
                                        Text {
                                            text: qsTr("Flags")
                                            font.pixelSize: 12
                                            color: textMutedColor
                                        }
                                        Row {
                                            spacing: 12
                                            CheckBox {
                                                id: createEspFlag
                                                text: "esp"
                                                contentItem: Text {
                                                    text: createEspFlag.text
                                                    color: textColor
                                                    font.pixelSize: 13
                                                    verticalAlignment: Text.AlignVCenter
                                                    leftPadding: createEspFlag.indicator.width + createEspFlag.spacing
                                                }
                                            }
                                            CheckBox {
                                                id: createBootFlag
                                                text: "boot"
                                                contentItem: Text {
                                                    text: createBootFlag.text
                                                    color: textColor
                                                    font.pixelSize: 13
                                                    verticalAlignment: Text.AlignVCenter
                                                    leftPadding: createBootFlag.indicator.width + createBootFlag.spacing
                                                }
                                            }
                                        }
                                    }
                                }

                                Row {
                                    spacing: 10
                                    Button {
                                        text: qsTr("Add to queue")
                                        highlighted: true
                                        onClicked: {
                                            var mib = Math.max(1, Math.min(
                                                createForm.parent.freeMib,
                                                Math.round(createSizeSlider.value)))
                                            var flags = []
                                            if (createEspFlag.checked) flags.push("esp")
                                            if (createBootFlag.checked) flags.push("boot")
                                            var mp = createMountCombo.currentIndex === 0
                                                ? "" : createMountCombo.currentText
                                            addOperation({
                                                type: "create",
                                                target: "free:" + selectedSegment.startSector,
                                                params: {
                                                    start_sector: selectedSegment.startSector,
                                                    size_sectors: mibToSectors(mib),
                                                    fstype: createFsCombo.currentText,
                                                    mountpoint: mp,
                                                    flags: flags
                                                }
                                            })
                                        }
                                    }
                                    Button {
                                        text: qsTr("Cancel")
                                        onClicked: activeForm = ""
                                    }
                                }
                            }
                        }

                        // ==== FORM: Resize (on selected existing partition) ====
                        Rectangle {
                            width: parent.width
                            visible: activeForm === "resize" && selectedSegment
                                && selectedSegment.kind !== "free"
                            implicitHeight: resizeForm.implicitHeight + 28
                            height: implicitHeight
                            radius: 10
                            color: Qt.rgba(0, 0, 0, 0.18)
                            border.color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                            border.width: 1

                            // Adjacent free space after this partition (if provided by
                            // the backend as `freeAfterSectors`), else 0. Upper bound is
                            // current size + adjacent free; lower bound is minFs.
                            property int curMib: selectedSegment ? sectorsToMib(selectedSegment.sizeSectors) : 0
                            property int freeAfterMib: selectedSegment
                                ? sectorsToMib(selectedSegment.freeAfterSectors || 0) : 0
                            property int minMib: selectedSegment
                                ? Math.max(1, sectorsToMib(selectedSegment.minSizeSectors || 0)) : 1
                            property int maxMib: curMib + freeAfterMib

                            Column {
                                id: resizeForm
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 14
                                spacing: 12

                                Text {
                                    text: qsTr("Resize partition")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                }

                                Column {
                                    width: parent.width
                                    spacing: 6

                                    Text {
                                        text: qsTr("New size (MiB)")
                                        font.pixelSize: 13
                                        color: textMutedColor
                                    }

                                    Row {
                                        width: parent.width
                                        spacing: 12

                                        Slider {
                                            id: resizeSlider
                                            width: parent.width - resizeField.width - 12
                                            anchors.verticalCenter: parent.verticalCenter
                                            from: resizeForm.parent.minMib
                                            to: Math.max(resizeForm.parent.minMib, resizeForm.parent.maxMib)
                                            stepSize: 1
                                            value: resizeForm.parent.curMib
                                            onMoved: resizeField.text = Math.round(value).toString()
                                        }

                                        TextField {
                                            id: resizeField
                                            width: 120
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: Math.round(resizeSlider.value).toString()
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            validator: IntValidator {
                                                bottom: resizeForm.parent.minMib
                                                top: Math.max(resizeForm.parent.minMib, resizeForm.parent.maxMib)
                                            }
                                            color: textColor
                                            onEditingFinished: {
                                                var v = parseInt(text)
                                                if (isNaN(v)) v = resizeForm.parent.minMib
                                                v = Math.max(resizeForm.parent.minMib,
                                                    Math.min(resizeForm.parent.maxMib, v))
                                                resizeSlider.value = v
                                                text = v.toString()
                                            }
                                        }
                                    }

                                    Text {
                                        text: qsTr("Range") + ": " + resizeForm.parent.minMib
                                            + " – " + resizeForm.parent.maxMib + " MiB"
                                        font.pixelSize: 11
                                        color: textMutedColor
                                    }
                                }

                                Row {
                                    spacing: 10
                                    Button {
                                        text: qsTr("Add to queue")
                                        highlighted: true
                                        onClicked: {
                                            var v = Math.max(resizeForm.parent.minMib,
                                                Math.min(resizeForm.parent.maxMib,
                                                    Math.round(resizeSlider.value)))
                                            addOperation({
                                                type: "resize",
                                                target: selectedSegment.name,
                                                params: {
                                                    path: selectedSegment.name,
                                                    number: (selectedSegment.number || 0),
                                                    new_size_sectors: mibToSectors(v),
                                                    fstype: (selectedSegment.fstype || "")
                                                }
                                            })
                                        }
                                    }
                                    Button {
                                        text: qsTr("Cancel")
                                        onClicked: activeForm = ""
                                    }
                                }
                            }
                        }

                        // ==== FORM: Format (fstype + mount point) ====
                        Rectangle {
                            width: parent.width
                            visible: activeForm === "format" && selectedSegment
                                && selectedSegment.kind !== "free"
                            implicitHeight: formatForm.implicitHeight + 28
                            height: implicitHeight
                            radius: 10
                            color: Qt.rgba(0, 0, 0, 0.18)
                            border.color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                            border.width: 1

                            Column {
                                id: formatForm
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 14
                                spacing: 12

                                Text {
                                    text: qsTr("Format partition")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                }

                                Row {
                                    spacing: 16

                                    Column {
                                        spacing: 4
                                        Text {
                                            text: qsTr("Filesystem")
                                            font.pixelSize: 12
                                            color: textMutedColor
                                        }
                                        ComboBox {
                                            id: formatFsCombo
                                            width: 130
                                            model: ["ext4", "btrfs", "vfat", "swap"]
                                        }
                                    }

                                    Column {
                                        spacing: 4
                                        Text {
                                            text: qsTr("Mount point")
                                            font.pixelSize: 12
                                            color: textMutedColor
                                        }
                                        ComboBox {
                                            id: formatMountCombo
                                            width: 150
                                            model: ["(none)", "/", "/home", "/boot", "swap"]
                                        }
                                    }
                                }

                                Row {
                                    spacing: 10
                                    Button {
                                        text: qsTr("Add to queue")
                                        highlighted: true
                                        onClicked: {
                                            var mp = formatMountCombo.currentIndex === 0
                                                ? "" : formatMountCombo.currentText
                                            addOperation({
                                                type: "format",
                                                target: selectedSegment.name,
                                                params: {
                                                    path: selectedSegment.name,
                                                    fstype: formatFsCombo.currentText,
                                                    mountpoint: mp
                                                }
                                            })
                                        }
                                    }
                                    Button {
                                        text: qsTr("Cancel")
                                        onClicked: activeForm = ""
                                    }
                                }
                            }
                        }

                        // ==== FORM: Flags (esp / boot toggles) ====
                        Rectangle {
                            width: parent.width
                            visible: activeForm === "flags" && selectedSegment
                                && selectedSegment.kind !== "free"
                            implicitHeight: flagsForm.implicitHeight + 28
                            height: implicitHeight
                            radius: 10
                            color: Qt.rgba(0, 0, 0, 0.18)
                            border.color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                            border.width: 1

                            Column {
                                id: flagsForm
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 14
                                spacing: 12

                                Text {
                                    text: qsTr("Partition flags")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                }

                                Row {
                                    spacing: 12
                                    Repeater {
                                        model: ["esp", "boot"]
                                        Button {
                                            required property string modelData
                                            text: qsTr("Set") + " " + modelData
                                            onClicked: {
                                                addOperation({
                                                    type: "setflag",
                                                    target: selectedSegment.name,
                                                    params: {
                                                        number: (selectedSegment.number || 0),
                                                        flag: modelData,
                                                        state: true
                                                    }
                                                })
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: ["esp", "boot"]
                                        Button {
                                            required property string modelData
                                            text: qsTr("Clear") + " " + modelData
                                            onClicked: {
                                                addOperation({
                                                    type: "setflag",
                                                    target: selectedSegment.name,
                                                    params: {
                                                        number: (selectedSegment.number || 0),
                                                        flag: modelData,
                                                        state: false
                                                    }
                                                })
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ---- Divider ----
                        Rectangle {
                            width: parent.width
                            height: 1
                            color: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.25)
                        }

                        // ---- Pending operations queue ----
                        Column {
                            width: parent.width
                            spacing: 8

                            Row {
                                width: parent.width
                                spacing: 8

                                Text {
                                    text: qsTr("Pending operations")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    height: 20
                                    width: opCountLabel.width + 14
                                    radius: 10
                                    color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.3)
                                    Text {
                                        id: opCountLabel
                                        anchors.centerIn: parent
                                        text: pendingOperations.length.toString()
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: textColor
                                    }
                                }
                            }

                            Text {
                                width: parent.width
                                visible: pendingOperations.length === 0
                                text: qsTr("No operation queued.")
                                font.pixelSize: 13
                                color: textMutedColor
                            }

                            Repeater {
                                model: pendingOperations

                                Rectangle {
                                    width: parent.width
                                    implicitHeight: opRow.implicitHeight + 16
                                    height: implicitHeight
                                    radius: 8
                                    color: Qt.rgba(0, 0, 0, 0.18)

                                    Row {
                                        id: opRow
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.margins: 12
                                        spacing: 10

                                        Text {
                                            width: parent.width - removeOpBtn.width - 10
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: operationLabel(modelData)
                                            font.pixelSize: 13
                                            color: textColor
                                            wrapMode: Text.WordWrap
                                        }

                                        Button {
                                            id: removeOpBtn
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "✕"
                                            implicitWidth: 32
                                            onClicked: removeOperation(index)
                                        }
                                    }
                                }
                            }

                            Row {
                                spacing: 10
                                visible: commandPreview.length > 0

                                Button {
                                    text: commandPreviewColumn.expanded
                                        ? qsTr("Hide command preview")
                                        : qsTr("Show command preview")
                                    onClicked: commandPreviewColumn.expanded = !commandPreviewColumn.expanded
                                }
                            }

                            // Collapsible command preview
                            Column {
                                id: commandPreviewColumn
                                width: parent.width
                                spacing: 4
                                property bool expanded: false
                                visible: expanded && commandPreview.length > 0

                                Rectangle {
                                    width: parent.width
                                    implicitHeight: cmdPreviewInner.implicitHeight + 20
                                    height: implicitHeight
                                    radius: 8
                                    color: Qt.rgba(0, 0, 0, 0.28)

                                    Column {
                                        id: cmdPreviewInner
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 12
                                        spacing: 4

                                        Repeater {
                                            model: commandPreview
                                            Text {
                                                width: parent.width
                                                text: modelData
                                                font.pixelSize: 12
                                                font.family: "monospace"
                                                color: textMutedColor
                                                wrapMode: Text.WrapAnywhere
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ---- Validation banner ----
                        Rectangle {
                            width: parent.width
                            visible: !engine.manualPlanValid && manualPlanError !== ""
                            implicitHeight: manualErrRow.implicitHeight + 20
                            height: implicitHeight
                            radius: 8
                            color: Qt.rgba(warningColor.r, warningColor.g, warningColor.b, 0.15)
                            border.color: warningColor
                            border.width: 1

                            Row {
                                id: manualErrRow
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "⚠️"
                                    font.pixelSize: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    width: parent.width - 30
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: manualPlanError
                                    font.pixelSize: 13
                                    color: warningColor
                                    wrapMode: Text.WordWrap
                                }
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
