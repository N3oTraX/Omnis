/*
 * Omnis Installer - Main QML Interface
 *
 * Modern, fluid UI with dynamic branding support.
 * Colors and text are loaded from branding configuration.
 *
 * Wizard Steps:
 * 0 - Welcome (requirements check)
 * 1 - Locale (language, timezone, keyboard)
 * 2 - Users (username, password, options)
 * 3 - Partition (disk selection)
 * 4 - Summary (review selections)
 * 5 - Progress (installation)
 * 6 - Finished (reboot/shutdown)
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "components"

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
    readonly property color successColor: branding.successColor || "#10B981"
    readonly property color warningColor: branding.warningColor || "#F59E0B"
    readonly property color errorColor: branding.errorColor || "#EF4444"

    // Wizard state
    property int currentStep: 0
    readonly property int totalSteps: 7  // 0-6
    readonly property var stepNames: ["Welcome", "Locale", "Users", "Partition", "Summary", "Installing", "Finished"]

    // Installation state
    property bool isInstalling: false
    property bool installationSuccess: false

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

        // Header (hidden on Welcome and Finished)
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            visible: currentStep > 0 && currentStep < 6

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
                    text: branding.name + " Installer"
                    font.pixelSize: 20
                    font.bold: true
                    color: textColor
                }

                Text {
                    text: stepNames[currentStep] || ""
                    font.pixelSize: 14
                    color: textMutedColor
                }
            }

            // Step indicator (steps 1-4 only)
            Row {
                spacing: 8
                visible: currentStep >= 1 && currentStep <= 4

                Repeater {
                    model: 4  // Steps 1-4

                    Rectangle {
                        width: 40
                        height: 4
                        radius: 2
                        color: (index + 1) < currentStep ? primaryColor :
                               (index + 1) === currentStep ? accentColor : Qt.darker(surfaceColor, 1.2)

                        Behavior on color {
                            ColorAnimation { duration: 300 }
                        }
                    }
                }
            }
        }

        // Content area
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Step 0: Welcome
            WelcomeView {
                id: welcomeView
                anchors.fill: parent
                visible: currentStep === 0
                opacity: visible ? 1 : 0

                welcomeWallpaper: branding.welcomeWallpaperUrl || branding.backgroundUrl
                logoUrl: branding.logoUrl
                welcomeTitle: branding.welcomeTitle
                welcomeSubtitle: branding.welcomeSubtitle
                installButtonText: branding.installButton

                showRequirements: engine.showRequirements
                requirements: engine.requirementsModel
                canProceed: engine.canProceed
                isCheckingRequirements: engine.isCheckingRequirements

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                successColor: root.successColor
                warningColor: root.warningColor
                errorColor: root.errorColor

                onInstallClicked: {
                    engine.loadLocaleData()
                    currentStep = 1
                }

                onRequirementsChecked: {
                    engine.checkRequirements()
                }

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }

            // Step 1: Locale
            LocaleView {
                id: localeView
                anchors.fill: parent
                visible: currentStep === 1
                opacity: visible ? 1 : 0

                localesModel: engine.localesModel
                timezonesModel: engine.timezonesModel
                keymapsModel: engine.keymapsModel
                selectedLocale: engine.selectedLocale
                selectedTimezone: engine.selectedTimezone
                selectedKeymap: engine.selectedKeymap

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                accentColor: root.accentColor

                onLocaleSelected: function(locale) {
                    engine.setSelectedLocale(locale)
                }
                onTimezoneSelected: function(timezone) {
                    engine.setSelectedTimezone(timezone)
                }
                onKeymapSelected: function(keymap) {
                    engine.setSelectedKeymap(keymap)
                }

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }

            // Step 2: Users
            UsersView {
                id: usersView
                anchors.fill: parent
                visible: currentStep === 2
                opacity: visible ? 1 : 0

                username: engine.username
                fullName: engine.fullName
                hostname: engine.hostname
                autoLogin: engine.autoLogin
                isAdmin: engine.isAdmin

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                accentColor: root.accentColor
                errorColor: root.errorColor
                successColor: root.successColor

                onUsernameChanged: engine.setUsername(username)
                onFullNameChanged: engine.setFullName(fullName)
                onHostnameChanged: engine.setHostname(hostname)
                onPasswordChanged: engine.setPassword(password)
                onAutoLoginChanged: engine.setAutoLogin(autoLogin)
                onIsAdminChanged: engine.setIsAdmin(isAdmin)

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }

            // Step 3: Partition
            PartitionView {
                id: partitionView
                anchors.fill: parent
                visible: currentStep === 3
                opacity: visible ? 1 : 0

                disksModel: engine.disksModel
                selectedDisk: engine.selectedDisk
                partitionMode: engine.partitionMode

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                accentColor: root.accentColor
                warningColor: root.warningColor
                errorColor: root.errorColor

                onDiskSelected: function(disk) {
                    engine.setSelectedDisk(disk)
                }
                onModeSelected: function(mode) {
                    engine.setPartitionMode(mode)
                }

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }

            // Step 4: Summary
            SummaryView {
                id: summaryView
                anchors.fill: parent
                visible: currentStep === 4
                opacity: visible ? 1 : 0

                selections: engine.selections
                distroName: branding.name
                distroVersion: branding.version
                distroLogo: branding.logoSmallUrl

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                accentColor: root.accentColor
                warningColor: root.warningColor

                onEditLocale: currentStep = 1
                onEditUsers: currentStep = 2
                onEditPartition: currentStep = 3

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }

            // Step 5: Progress
            ProgressView {
                id: progressView
                anchors.fill: parent
                visible: currentStep === 5
                opacity: visible ? 1 : 0

                overallProgress: engine.overallProgress
                currentJobProgress: engine.currentJobProgress
                currentJobName: engine.currentJobName
                currentJobMessage: engine.currentJobMessage
                jobsList: engine.jobsList
                installationStatus: engine.installationStatus
                errorMessage: engine.errorMessage

                distroName: branding.name
                distroLogo: branding.logoSmallUrl

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                accentColor: root.accentColor
                successColor: root.successColor
                errorColor: root.errorColor

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }

            // Step 6: Finished
            FinishedView {
                id: finishedView
                anchors.fill: parent
                visible: currentStep === 6
                opacity: visible ? 1 : 0

                success: installationSuccess
                errorMessage: engine.errorMessage
                summary: engine.installationSummary

                distroName: branding.name
                distroLogo: branding.logoUrl
                backgroundUrl: branding.backgroundUrl

                primaryColor: root.primaryColor
                backgroundColor: root.backgroundColor
                surfaceColor: root.surfaceColor
                textColor: root.textColor
                textMutedColor: root.textMutedColor
                successColor: root.successColor
                errorColor: root.errorColor

                onRebootClicked: engine.executeFinishAction("reboot")
                onShutdownClicked: engine.executeFinishAction("shutdown")
                onContinueClicked: Qt.quit()

                Behavior on opacity {
                    NumberAnimation { duration: 300 }
                }
            }
        }

        // Footer with navigation (hidden on Welcome, Progress, Finished)
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            visible: currentStep >= 1 && currentStep <= 4

            Text {
                text: "Powered by Omnis Installer"
                font.pixelSize: 12
                color: textMutedColor
            }

            Item { Layout.fillWidth: true }

            // Back button
            Button {
                text: "Back"
                onClicked: navigateBack()

                background: Rectangle {
                    implicitWidth: 100
                    implicitHeight: 40
                    radius: 8
                    color: parent.pressed ? Qt.darker(surfaceColor, 1.2) :
                           parent.hovered ? Qt.lighter(surfaceColor, 1.1) : surfaceColor
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

            // Next/Install button
            Button {
                text: currentStep === 4 ? "Install" : "Next"
                enabled: canProceedToNext()

                background: Rectangle {
                    implicitWidth: 120
                    implicitHeight: 40
                    radius: 8
                    color: !parent.enabled ? Qt.darker(surfaceColor, 1.3) :
                           parent.pressed ? Qt.darker(primaryColor, 1.2) :
                           parent.hovered ? Qt.lighter(primaryColor, 1.1) : primaryColor
                }

                contentItem: Text {
                    text: parent.text
                    font.pixelSize: 14
                    font.bold: true
                    color: parent.enabled ? textColor : textMutedColor
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                onClicked: navigateNext()
            }
        }
    }

    // Navigation functions
    function navigateBack() {
        if (currentStep > 0 && currentStep <= 4) {
            if (currentStep === 1) {
                currentStep = 0  // Back to Welcome
            } else {
                currentStep--
            }
        }
    }

    function navigateNext() {
        if (currentStep === 4) {
            // Start installation
            startInstallation()
        } else if (currentStep < 4) {
            // Load data for next step if needed
            if (currentStep === 2) {
                engine.refreshDisks()  // Load disks before partition step
            }
            currentStep++
        }
    }

    function canProceedToNext() {
        switch (currentStep) {
            case 1:  // Locale
                return engine.selectedLocale !== "" &&
                       engine.selectedTimezone !== "" &&
                       engine.selectedKeymap !== ""
            case 2:  // Users
                return usersView.isValid
            case 3:  // Partition
                return engine.selectedDisk !== ""
            case 4:  // Summary
                return true  // Always can install from summary
            default:
                return true
        }
    }

    function startInstallation() {
        engine.applySelectionsToContext()
        currentStep = 5
        isInstalling = true
        engine.startInstallation()
    }

    // Step change handler
    onCurrentStepChanged: {
        console.log("Step changed to:", currentStep, "-", stepNames[currentStep])
    }

    // Engine connections
    Connections {
        target: engine

        function onInstallationStarted() {
            isInstalling = true
        }

        function onInstallationFinished(success) {
            isInstalling = false
            installationSuccess = success
            currentStep = 6  // Go to Finished view
        }

        function onJobProgress(jobName, percent, message) {
            console.log("Progress:", jobName, percent + "%", message)
        }

        function onErrorOccurred(jobName, errorMessage) {
            console.error("Error in", jobName + ":", errorMessage)
        }
    }

    // Keyboard shortcuts
    Shortcut {
        sequence: "Escape"
        enabled: currentStep > 0 && currentStep <= 4
        onActivated: navigateBack()
    }

    Shortcut {
        sequence: "Return"
        enabled: currentStep >= 1 && currentStep <= 4 && canProceedToNext()
        onActivated: navigateNext()
    }

    // Initialize
    Component.onCompleted: {
        console.log("Omnis Installer started")
        console.log("Debug mode:", engine.debugMode)
        console.log("Dry run:", engine.dryRun)
        engine.checkRequirements()
    }
}
