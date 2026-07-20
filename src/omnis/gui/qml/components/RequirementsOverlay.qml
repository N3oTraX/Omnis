/*
 * RequirementsOverlay - Modern glassmorphism requirements display
 *
 * Displays system requirements check results with:
 * - Status icons (pass/warn/fail)
 * - Current vs required values
 * - Overall installation readiness
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Rectangle {
    id: root

    // Signals
    signal configureNetworkClicked()
    signal recheckRequested()

    // Properties from parent/backend
    property var requirements: []
    property bool canProceed: true
    // canProceed only reflects blocking checks: warnings must be surfaced
    // separately, otherwise orange indicators are reported as a full pass.
    property bool hasWarnings: false
    property bool isLoading: false
    property string summaryText: ""

    readonly property color overallStatusColor: !canProceed ? errorColor
                                                            : (hasWarnings ? warningColor
                                                                           : successColor)
    readonly property string defaultSummaryText: {
        if (!canProceed)
            return qsTr("Some requirements not met")
        if (hasWarnings)
            return qsTr("Your system meets the minimum requirements, but some recommendations are not met")
        return qsTr("Your system meets all requirements")
    }

    // Theme-based requirement icons (object with ram_pass, ram_warn, etc.)
    property var requirementIcons: ({})

    // Color scheme (inherited from parent)
    property color primaryColor: "#5597e6"
    property color backgroundColor: "#1a1a1a"
    property color surfaceColor: "#32373c"
    property color textColor: "#fffded"
    property color textMutedColor: "#9CA3AF"
    property color successColor: "#10B981"
    property color warningColor: "#F59E0B"
    property color errorColor: "#EF4444"

    // Helper function to get icon URL for a requirement
    function getIconUrl(name, status) {
        // Map requirement names to icon keys
        var iconKey = ""
        switch(name) {
            case "ram": iconKey = "ram"; break
            case "disk": iconKey = "disk"; break
            case "gpu": iconKey = "gpu"; break
            default: return ""
        }
        // Build the key like "ram_pass", "disk_warn", etc.
        var fullKey = iconKey + "_" + status
        return requirementIcons[fullKey] || ""
    }

    // Glassmorphism style
    color: Qt.rgba(surfaceColor.r, surfaceColor.g, surfaceColor.b, 0.85)
    radius: 20
    border.color: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.1)
    border.width: 1

    // Drop shadow effect
    layer.enabled: !engine.softwareRendering
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: Qt.rgba(0, 0, 0, 0.4)
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 8
        shadowBlur: 0.5
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Status indicator
            Rectangle {
                width: 40
                height: 40
                radius: 20
                color: Qt.rgba(root.overallStatusColor.r, root.overallStatusColor.g,
                               root.overallStatusColor.b, 0.2)

                Text {
                    anchors.centerIn: parent
                    text: (canProceed && !hasWarnings) ? "✓" : "!"
                    font.pixelSize: 20
                    font.bold: true
                    color: root.overallStatusColor
                }
            }

            Column {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: qsTr("System Requirements")
                    font.pixelSize: 18
                    font.bold: true
                    color: textColor
                }

                Text {
                    width: parent.width
                    text: summaryText || root.defaultSummaryText
                    font.pixelSize: 13
                    color: textMutedColor
                    wrapMode: Text.WordWrap
                }
            }

            Button {
                id: recheckButton
                Layout.alignment: Qt.AlignVCenter
                text: qsTr("Re-check")
                font.pixelSize: 12
                enabled: !root.isLoading

                background: Rectangle {
                    implicitWidth: 100
                    implicitHeight: 30
                    radius: 6
                    color: recheckButton.pressed ? Qt.darker(root.primaryColor, 1.2) :
                           recheckButton.hovered ? Qt.lighter(root.primaryColor, 1.1) : root.primaryColor
                    border.color: Qt.lighter(root.primaryColor, 1.3)
                    border.width: 1
                    opacity: recheckButton.enabled ? 1.0 : 0.5
                }

                contentItem: Text {
                    text: recheckButton.text
                    font: recheckButton.font
                    color: root.textColor
                    opacity: recheckButton.enabled ? 1.0 : 0.5
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                onClicked: root.recheckRequested()
            }
        }

        // Separator
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.1)
        }

        // Loading indicator
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 100
            visible: isLoading

            BusyIndicator {
                anchors.centerIn: parent
                running: isLoading
                palette.dark: primaryColor
            }
        }

        // Requirements list
        ScrollView {
            id: requirementsScrollView
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !isLoading
            clip: true

            // Improve wheel scroll speed (3x faster)
            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: function(event) {
                    var flickable = requirementsScrollView.contentItem
                    var multiplier = 3.0
                    var deltaY = event.angleDelta.y * multiplier
                    var newY = flickable.contentY - (deltaY / 120.0 * 40)
                    flickable.contentY = Math.max(0, Math.min(flickable.contentHeight - flickable.height, newY))
                    event.accepted = true
                }
            }

            ListView {
                id: requirementsList
                width: parent.width
                implicitHeight: contentHeight
                model: requirements
                spacing: 8

                delegate: RequirementItem {
                    width: requirementsList.width
                    name: modelData.name || ""
                    description: modelData.description || ""
                    status: modelData.status || "skip"
                    currentValue: modelData.currentValue || ""
                    requiredValue: modelData.requiredValue || ""
                    recommendedValue: modelData.recommendedValue || ""
                    details: modelData.details || ""

                    // Pass theme icons based on requirement name
                    passIconUrl: root.getIconUrl(modelData.name, "pass")
                    warnIconUrl: root.getIconUrl(modelData.name, "warn")
                    failIconUrl: root.getIconUrl(modelData.name, "fail")

                    primaryColor: root.primaryColor
                    surfaceColor: root.surfaceColor
                    textColor: root.textColor
                    textMutedColor: root.textMutedColor
                    successColor: root.successColor
                    warningColor: root.warningColor
                    errorColor: root.errorColor

                    // Propagate network configuration signal
                    onConfigureNetworkClicked: root.configureNetworkClicked()
                }
            }
        }

        // Footer with action hint
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: !isLoading && !canProceed

            Rectangle {
                width: 16
                height: 16
                radius: 8
                color: Qt.rgba(warningColor.r, warningColor.g, warningColor.b, 0.2)

                Text {
                    anchors.centerIn: parent
                    text: "!"
                    font.pixelSize: 10
                    font.bold: true
                    color: warningColor
                }
            }

            Text {
                Layout.fillWidth: true
                text: qsTr("Please resolve the issues above before proceeding")
                font.pixelSize: 12
                color: warningColor
                wrapMode: Text.WordWrap
            }
        }
    }
}
