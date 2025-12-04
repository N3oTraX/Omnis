/*
 * RequirementItem - Single requirement display row
 *
 * Shows individual requirement check with status, values, and details.
 * Supports theme-based icons for requirements and status indicators.
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    // Required properties
    property string name: ""
    property string description: ""
    property string status: "skip"  // pass, warn, fail, skip
    property string currentValue: ""
    property string requiredValue: ""
    property string recommendedValue: ""
    property string details: ""

    // Theme-based icon URLs (optional, falls back to emoji if not provided)
    property string passIconUrl: ""
    property string warnIconUrl: ""
    property string failIconUrl: ""

    // Color scheme
    property color primaryColor: "#5597e6"
    property color surfaceColor: "#32373c"
    property color textColor: "#fffded"
    property color textMutedColor: "#9CA3AF"
    property color successColor: "#10B981"
    property color warningColor: "#F59E0B"
    property color errorColor: "#EF4444"

    // Internal
    readonly property color statusColor: {
        switch(status) {
            case "pass": return successColor
            case "warn": return warningColor
            case "fail": return errorColor
            default: return textMutedColor
        }
    }

    readonly property string statusIcon: {
        switch(status) {
            case "pass": return "\u2713"  // Check mark
            case "warn": return "\u26a0"  // Warning
            case "fail": return "\u2717"  // X mark
            default: return "\u2212"      // Minus
        }
    }

    // Get the appropriate icon URL based on status
    readonly property string currentIconUrl: {
        switch(status) {
            case "pass": return passIconUrl
            case "warn": return warnIconUrl
            case "fail": return failIconUrl
            default: return ""
        }
    }

    readonly property string requirementIcon: {
        switch(name) {
            case "ram": return "\ud83d\udcbe"       // Floppy disk
            case "disk": return "\ud83d\udcbf"      // CD
            case "cpu_arch": return "\ud83d\udda5"  // Desktop
            case "efi": return "\u26a1"             // Lightning
            case "secure_boot": return "\ud83d\udd12" // Lock
            case "internet": return "\ud83c\udf10"  // Globe
            case "power": return "\ud83d\udd0c"     // Plug
            case "battery": return "\ud83d\udd0b"   // Battery
            case "gpu": return "\ud83c\udfae"       // Gamepad
            default: return "\ud83d\udccb"          // Clipboard
        }
    }

    // Check if we have a valid icon URL
    readonly property bool hasIconUrl: currentIconUrl !== ""

    height: contentColumn.height + 16
    radius: 12
    color: Qt.rgba(surfaceColor.r, surfaceColor.g, surfaceColor.b, 0.5)
    border.color: Qt.rgba(statusColor.r, statusColor.g, statusColor.b, 0.3)
    border.width: status === "fail" ? 1 : 0

    RowLayout {
        id: contentColumn
        anchors {
            left: parent.left
            right: parent.right
            verticalCenter: parent.verticalCenter
            margins: 12
        }
        spacing: 12

        // Requirement icon - prefer SVG from theme, fallback to emoji
        Item {
            width: 32
            height: 32

            // Theme SVG icon (if available)
            Image {
                id: themeIcon
                anchors.fill: parent
                source: root.hasIconUrl ? root.currentIconUrl : ""
                fillMode: Image.PreserveAspectFit
                visible: root.hasIconUrl && themeIcon.status === Image.Ready
                sourceSize.width: 32
                sourceSize.height: 32
            }

            // Fallback emoji icon
            Text {
                anchors.centerIn: parent
                text: root.requirementIcon
                font.pixelSize: 20
                visible: !root.hasIconUrl || themeIcon.status !== Image.Ready
            }
        }

        // Details
        Column {
            Layout.fillWidth: true
            spacing: 2

            Text {
                text: description || name
                font.pixelSize: 14
                font.bold: true
                color: textColor
            }

            // Values row
            Row {
                spacing: 8
                visible: currentValue !== ""

                Text {
                    text: currentValue
                    font.pixelSize: 12
                    color: statusColor
                    font.bold: true
                }

                Text {
                    text: requiredValue ? "/ " + qsTr("Required:") + " " + requiredValue : ""
                    font.pixelSize: 12
                    color: textMutedColor
                    visible: requiredValue !== ""
                }

                Text {
                    text: recommendedValue ? "(" + qsTr("Recommended:") + " " + recommendedValue + ")" : ""
                    font.pixelSize: 11
                    color: textMutedColor
                    visible: recommendedValue !== "" && status === "warn"
                }
            }

            // Details/error message
            Text {
                text: details
                font.pixelSize: 11
                color: status === "fail" ? errorColor : textMutedColor
                visible: details !== "" && (status === "fail" || status === "skip")
                wrapMode: Text.WordWrap
                width: parent.width
            }
        }

        // Status badge with tooltip on hover for warn/fail
        Rectangle {
            id: statusBadge
            width: 28
            height: 28
            radius: 14
            color: Qt.rgba(statusColor.r, statusColor.g, statusColor.b, 0.2)

            Text {
                anchors.centerIn: parent
                text: statusIcon
                font.pixelSize: 14
                font.bold: true
                color: statusColor
            }

            // Mouse area for tooltip
            MouseArea {
                id: badgeMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: (root.status === "warn" || root.status === "fail") && root.details !== ""
                    ? Qt.PointingHandCursor
                    : Qt.ArrowCursor
            }

            // Tooltip showing details on hover for warn/fail
            ToolTip {
                id: statusTooltip
                visible: badgeMouseArea.containsMouse && (root.status === "warn" || root.status === "fail") && root.details !== ""
                delay: 300
                timeout: 10000
                text: root.details

                contentItem: Text {
                    text: statusTooltip.text
                    font.pixelSize: 12
                    color: root.textColor
                    wrapMode: Text.WordWrap
                }

                background: Rectangle {
                    color: Qt.rgba(root.surfaceColor.r, root.surfaceColor.g, root.surfaceColor.b, 0.95)
                    radius: 8
                    border.color: Qt.rgba(root.statusColor.r, root.statusColor.g, root.statusColor.b, 0.5)
                    border.width: 1

                    // Shadow effect
                    layer.enabled: true
                    layer.effect: null
                }
            }
        }
    }
}
