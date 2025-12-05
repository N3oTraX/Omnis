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

    // Properties from parent/backend
    property var requirements: []
    property bool canProceed: true
    property bool isLoading: false
    property string summaryText: ""

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
    layer.enabled: true
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
                color: canProceed ? Qt.rgba(successColor.r, successColor.g, successColor.b, 0.2)
                                  : Qt.rgba(errorColor.r, errorColor.g, errorColor.b, 0.2)

                Text {
                    anchors.centerIn: parent
                    text: canProceed ? "✓" : "!"
                    font.pixelSize: 20
                    font.bold: true
                    color: canProceed ? successColor : errorColor
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
                    text: summaryText || (canProceed ? qsTr("Your system meets all requirements")
                                                     : qsTr("Some requirements not met"))
                    font.pixelSize: 13
                    color: textMutedColor
                }
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
