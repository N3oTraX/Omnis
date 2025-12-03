/*
 * Omnis Installer - Main QML Interface
 *
 * Modern, fluid UI with dynamic branding support.
 * Colors and text are loaded from branding configuration.
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

ApplicationWindow {
    id: root

    width: 1024
    height: 768
    minimumWidth: 800
    minimumHeight: 600
    visible: true
    title: branding.name + " Installer"

    // Dynamic color palette from branding
    readonly property color primaryColor: branding.primaryColor
    readonly property color secondaryColor: branding.secondaryColor
    readonly property color accentColor: branding.accentColor
    readonly property color backgroundColor: branding.backgroundColor
    readonly property color surfaceColor: branding.surfaceColor
    readonly property color textColor: branding.textColor
    readonly property color textMutedColor: branding.textMutedColor

    // Current state
    property int currentStep: 0
    property bool isInstalling: false

    color: backgroundColor

    // Background wallpaper (with gradient fallback)
    Image {
        id: backgroundImage
        anchors.fill: parent
        source: branding.backgroundUrl
        fillMode: Image.PreserveAspectCrop
        visible: status === Image.Ready

        // Dark overlay for readability
        Rectangle {
            anchors.fill: parent
            color: backgroundColor
            opacity: 0.3
        }
    }

    // Fallback gradient when no wallpaper
    Rectangle {
        anchors.fill: parent
        visible: backgroundImage.status !== Image.Ready
        gradient: Gradient {
            GradientStop { position: 0.0; color: backgroundColor }
            GradientStop { position: 1.0; color: Qt.darker(backgroundColor, 1.3) }
        }
    }

    // Main content
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            // Logo
            Item {
                width: 48
                height: 48

                Image {
                    id: headerLogo
                    anchors.fill: parent
                    source: branding.logoSmallUrl
                    fillMode: Image.PreserveAspectFit
                    visible: status === Image.Ready
                }

                // Fallback when logo not available
                Rectangle {
                    anchors.fill: parent
                    radius: 12
                    color: primaryColor
                    visible: headerLogo.status !== Image.Ready

                    Text {
                        anchors.centerIn: parent
                        text: branding.name.charAt(0)
                        font.pixelSize: 24
                        font.bold: true
                        color: textColor
                    }
                }
            }

            Column {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: branding.name
                    font.pixelSize: 24
                    font.bold: true
                    color: textColor
                }

                Text {
                    text: branding.version + (branding.edition ? " " + branding.edition : "")
                    font.pixelSize: 14
                    color: textMutedColor
                }
            }

            // Step indicator
            Row {
                spacing: 8
                visible: currentStep > 0

                Repeater {
                    model: engine.totalJobs

                    Rectangle {
                        width: 32
                        height: 4
                        radius: 2
                        color: index < currentStep ? primaryColor :
                               index === currentStep ? accentColor : surfaceColor

                        Behavior on color {
                            ColorAnimation { duration: 300 }
                        }
                    }
                }
            }
        }

        // Content area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 16
            color: surfaceColor

            // Welcome screen (step 0)
            Item {
                anchors.fill: parent
                anchors.margins: 48
                visible: currentStep === 0
                opacity: visible ? 1 : 0

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 24
                    width: Math.min(parent.width, 500)

                    // Welcome logo
                    Item {
                        Layout.alignment: Qt.AlignHCenter
                        width: 128
                        height: 128

                        Image {
                            id: welcomeLogo
                            anchors.fill: parent
                            source: branding.logoUrl
                            fillMode: Image.PreserveAspectFit
                            visible: status === Image.Ready
                        }

                        // Fallback circle with initial
                        Rectangle {
                            anchors.fill: parent
                            radius: 64
                            color: primaryColor
                            opacity: 0.2
                            visible: welcomeLogo.status !== Image.Ready

                            Rectangle {
                                anchors.centerIn: parent
                                width: 100
                                height: 100
                                radius: 50
                                color: primaryColor

                                Text {
                                    anchors.centerIn: parent
                                    text: branding.name.charAt(0)
                                    font.pixelSize: 48
                                    font.bold: true
                                    color: textColor
                                }
                            }
                        }
                    }

                    // Welcome text
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: branding.welcomeTitle
                        font.pixelSize: 32
                        font.bold: true
                        color: textColor
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        text: branding.welcomeSubtitle
                        font.pixelSize: 16
                        color: textMutedColor
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }

                    // Spacer
                    Item { Layout.preferredHeight: 24 }

                    // Install button
                    Button {
                        id: installButton
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 240
                        Layout.preferredHeight: 56

                        text: branding.installButton
                        font.pixelSize: 18
                        font.bold: true

                        background: Rectangle {
                            radius: 12
                            color: installButton.pressed ? Qt.darker(primaryColor, 1.2) :
                                   installButton.hovered ? Qt.lighter(primaryColor, 1.1) : primaryColor

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }
                        }

                        contentItem: Text {
                            text: installButton.text
                            font: installButton.font
                            color: textColor
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            currentStep = 1
                            // TODO: Navigate to next step
                        }
                    }

                    // Debug indicator
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Debug Mode"
                        font.pixelSize: 12
                        color: accentColor
                        visible: engine.debugMode
                    }
                }
            }

            // Installation progress (step > 0)
            Item {
                anchors.fill: parent
                anchors.margins: 48
                visible: currentStep > 0 && isInstalling
                opacity: visible ? 1 : 0

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 24
                    width: Math.min(parent.width, 500)

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Installing..."
                        font.pixelSize: 24
                        font.bold: true
                        color: textColor
                    }

                    // Progress bar
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 8
                        radius: 4
                        color: backgroundColor

                        Rectangle {
                            width: parent.width * 0.45
                            height: parent.height
                            radius: 4
                            color: primaryColor

                            Behavior on width {
                                NumberAnimation { duration: 300 }
                            }
                        }
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Preparing system..."
                        font.pixelSize: 14
                        color: textMutedColor
                    }
                }
            }
        }

        // Footer
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Text {
                text: "Powered by Omnis Installer"
                font.pixelSize: 12
                color: textMutedColor
            }

            Item { Layout.fillWidth: true }

            // Navigation buttons (visible after welcome)
            Button {
                visible: currentStep > 0 && !isInstalling
                text: "Back"
                onClicked: currentStep = Math.max(0, currentStep - 1)

                background: Rectangle {
                    radius: 8
                    color: parent.pressed ? Qt.darker(surfaceColor, 1.2) : surfaceColor
                    border.color: textMutedColor
                    border.width: 1
                }

                contentItem: Text {
                    text: parent.text
                    font.pixelSize: 14
                    color: textColor
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                visible: currentStep > 0 && !isInstalling
                text: currentStep < engine.totalJobs ? "Next" : "Finish"

                background: Rectangle {
                    radius: 8
                    color: parent.pressed ? Qt.darker(primaryColor, 1.2) : primaryColor
                }

                contentItem: Text {
                    text: parent.text
                    font.pixelSize: 14
                    font.bold: true
                    color: textColor
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                onClicked: {
                    if (currentStep < engine.totalJobs) {
                        currentStep++
                    } else {
                        Qt.quit()
                    }
                }
            }
        }
    }

    // Engine connections
    Connections {
        target: engine

        function onInstallationStarted() {
            isInstalling = true
        }

        function onInstallationFinished(success) {
            isInstalling = false
            if (success) {
                currentStep = engine.totalJobs + 1
            }
        }

        function onJobProgress(jobName, percent, message) {
            // Update progress UI
            console.log("Progress:", jobName, percent, message)
        }

        function onErrorOccurred(jobName, errorMessage) {
            console.error("Error in", jobName, ":", errorMessage)
        }
    }
}
