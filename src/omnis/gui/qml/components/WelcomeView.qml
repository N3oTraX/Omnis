/*
 * WelcomeView - Full welcome screen with wallpaper and requirements overlay
 *
 * Displays:
 * - Dynamic wallpaper background (dark/light mode)
 * - Logo and welcome text
 * - Requirements overlay panel
 * - Install button (enabled when requirements met)
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // Signals
    signal installClicked()
    signal requirementsChecked()

    // External properties
    property string welcomeWallpaper: ""
    property string logoUrl: ""
    property string welcomeTitle: ""
    property string welcomeSubtitle: ""
    property string installButtonText: ""
    property string brandingCodename: ""
    property string brandingEdition: ""
    property bool showRequirements: true
    property var requirements: []
    property bool canProceed: true
    property bool isCheckingRequirements: false

    // Theme-based requirement icons (object with ram_pass, ram_warn, etc.)
    property var requirementIcons: ({})

    // Theme colors (from branding)
    property color primaryColor: "#5597e6"
    property color backgroundColor: "#1a1a1a"
    property color surfaceColor: "#32373c"
    property color textColor: "#fffded"
    property color textMutedColor: "#9CA3AF"
    property color successColor: "#10B981"
    property color warningColor: "#F59E0B"
    property color errorColor: "#EF4444"

    // Full-screen wallpaper background
    Image {
        id: wallpaperImage
        anchors.fill: parent
        source: welcomeWallpaper
        fillMode: Image.PreserveAspectCrop
        visible: status === Image.Ready

        // Smooth loading animation
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity {
            NumberAnimation { duration: 500; easing.type: Easing.OutCubic }
        }
    }

    // Gradient fallback
    Rectangle {
        anchors.fill: parent
        visible: wallpaperImage.status !== Image.Ready
        gradient: Gradient {
            GradientStop { position: 0.0; color: backgroundColor }
            GradientStop { position: 0.5; color: Qt.darker(primaryColor, 2.5) }
            GradientStop { position: 1.0; color: Qt.darker(backgroundColor, 1.3) }
        }
    }

    // Dark overlay for better readability
    Rectangle {
        anchors.fill: parent
        color: backgroundColor
        opacity: 0.4
    }

    // Content layout
    RowLayout {
        anchors.fill: parent
        anchors.margins: 48
        spacing: 48

        // Left side: Welcome content - centered between left edge and requirements panel
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.maximumWidth: parent.width * 0.5

            ColumnLayout {
                anchors.fill: parent
                spacing: 24

                // Flexible spacer at top - centers content vertically
                Item { Layout.fillHeight: true }

                // Logo - centered horizontally
                Item {
                    Layout.preferredWidth: 160
                    Layout.preferredHeight: 160
                    Layout.alignment: Qt.AlignHCenter

                    Image {
                        id: logoImage
                        anchors.fill: parent
                        source: logoUrl
                        fillMode: Image.PreserveAspectFit
                        visible: status === Image.Ready

                        // Subtle glow effect
                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: primaryColor
                            shadowHorizontalOffset: 0
                            shadowVerticalOffset: 0
                            shadowBlur: 0.3
                        }
                    }

                    // Fallback logo placeholder
                    Rectangle {
                        anchors.fill: parent
                        radius: 80
                        color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.3)
                        visible: logoImage.status !== Image.Ready

                        Text {
                            anchors.centerIn: parent
                            text: welcomeTitle.charAt(0) || "O"
                            font.pixelSize: 72
                            font.bold: true
                            color: textColor
                        }
                    }
                }

                // Welcome text - centered
                Column {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 8

                    // Main title: "Welcome to GLF OS"
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: welcomeTitle
                        font.pixelSize: 42
                        font.bold: true
                        color: textColor

                        // Text shadow for readability
                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: Qt.rgba(0, 0, 0, 0.6)
                            shadowHorizontalOffset: 2
                            shadowVerticalOffset: 2
                            shadowBlur: 0.3
                        }
                    }

                    // Codename + Edition: "Omnislash 25.04"
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: brandingCodename + (brandingEdition ? " " + brandingEdition : "")
                        font.pixelSize: 42
                        font.bold: true
                        color: textColor
                        visible: brandingCodename !== ""

                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: Qt.rgba(0, 0, 0, 0.6)
                            shadowHorizontalOffset: 2
                            shadowVerticalOffset: 2
                            shadowBlur: 0.3
                        }
                    }

                    // Subtitle
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: welcomeSubtitle
                        font.pixelSize: 18
                        color: textMutedColor
                        wrapMode: Text.WordWrap
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                // Install button - centered horizontally with welcome text
                Button {
                    id: installButton
                    Layout.preferredWidth: 280
                    Layout.preferredHeight: 60
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 24
                    enabled: canProceed && !isCheckingRequirements

                    text: installButtonText || qsTr("Install")
                    font.pixelSize: 18
                    font.bold: true

                    background: Rectangle {
                        radius: 16
                        color: {
                            if (!installButton.enabled) return Qt.darker(surfaceColor, 1.2)
                            if (installButton.pressed) return Qt.darker(primaryColor, 1.3)
                            if (installButton.hovered) return Qt.lighter(primaryColor, 1.15)
                            return primaryColor
                        }
                        border.color: installButton.enabled ? Qt.lighter(primaryColor, 1.3) : "transparent"
                        border.width: 1

                        Behavior on color {
                            ColorAnimation { duration: 150 }
                        }

                        // Subtle gradient overlay
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.1) }
                                GradientStop { position: 0.5; color: "transparent" }
                            }
                            visible: installButton.enabled
                        }
                    }

                    contentItem: Item {
                        implicitWidth: buttonRow.implicitWidth
                        implicitHeight: buttonRow.implicitHeight

                        Row {
                            id: buttonRow
                            anchors.centerIn: parent
                            spacing: 8

                            Text {
                                text: installButton.text
                                font: installButton.font
                                color: installButton.enabled ? textColor : textMutedColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: "\u2192"  // Right arrow
                                font.pixelSize: 20
                                color: installButton.enabled ? textColor : textMutedColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                                visible: installButton.enabled
                            }
                        }
                    }

                    onClicked: root.installClicked()
                }

                // Disabled hint
                Text {
                    visible: !canProceed && !isCheckingRequirements
                    text: qsTr("Please resolve system requirements before installing")
                    font.pixelSize: 12
                    color: warningColor
                    Layout.alignment: Qt.AlignHCenter
                }

                // Flexible spacer at bottom - centers content vertically
                Item { Layout.fillHeight: true }
            }
        }

        // Right side: Requirements panel
        RequirementsOverlay {
            Layout.fillHeight: true
            Layout.preferredWidth: 420
            Layout.maximumWidth: 500
            visible: showRequirements

            requirements: root.requirements
            canProceed: root.canProceed
            isLoading: root.isCheckingRequirements
            requirementIcons: root.requirementIcons

            primaryColor: root.primaryColor
            backgroundColor: root.backgroundColor
            surfaceColor: root.surfaceColor
            textColor: root.textColor
            textMutedColor: root.textMutedColor
            successColor: root.successColor
            warningColor: root.warningColor
            errorColor: root.errorColor

            // Animation on show
            opacity: visible ? 1 : 0
            Behavior on opacity {
                NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
            }
        }
    }

    // Trigger requirements check on component completion
    Component.onCompleted: {
        if (showRequirements) {
            requirementsChecked()
        }
    }
}
