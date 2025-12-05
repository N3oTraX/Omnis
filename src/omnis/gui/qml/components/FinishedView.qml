/*
 * FinishedView - Installation Completion
 *
 * Displays:
 * - Success/failure status with icon
 * - Installation summary
 * - Action buttons (Reboot/Shutdown/Continue)
 * - Error details for failed installations
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // Signals
    signal rebootClicked()
    signal shutdownClicked()
    signal continueClicked()
    signal retryClicked()
    signal viewLogsClicked()

    // External properties
    property bool success: true
    property string errorMessage: ""
    property var summary: ({})  // Installation summary from engine
    property var installationSummary: summary  // Alias for backwards compatibility

    // Distro info
    property string distroName: ""
    property string distroLogo: ""
    property string backgroundUrl: ""
    property string websiteUrl: ""
    property string websiteLabel: ""

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

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 48
            spacing: 32

            Item { Layout.fillHeight: true }

            // Status icon and message
            Column {
                Layout.alignment: Qt.AlignHCenter
                spacing: 24

                // Animated icon
                Rectangle {
                    width: 120
                    height: 120
                    radius: 60
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: success ?
                           Qt.rgba(successColor.r, successColor.g, successColor.b, 0.2) :
                           Qt.rgba(errorColor.r, errorColor.g, errorColor.b, 0.2)

                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: success ? successColor : errorColor
                        shadowHorizontalOffset: 0
                        shadowVerticalOffset: 0
                        shadowBlur: 0.5
                    }

                    // Success checkmark animation
                    Canvas {
                        id: successCanvas
                        anchors.fill: parent
                        visible: success

                        property real progress: 0

                        SequentialAnimation {
                            running: success
                            PauseAnimation { duration: 300 }
                            NumberAnimation {
                                target: successCanvas
                                property: "progress"
                                from: 0
                                to: 1
                                duration: 600
                                easing.type: Easing.OutCubic
                            }
                        }

                        onProgressChanged: requestPaint()

                        onPaint: {
                            var ctx = getContext("2d");
                            ctx.clearRect(0, 0, width, height);

                            ctx.strokeStyle = successColor;
                            ctx.lineWidth = 6;
                            ctx.lineCap = "round";
                            ctx.lineJoin = "round";

                            // Draw checkmark
                            var startX = width * 0.25;
                            var startY = height * 0.5;
                            var midX = width * 0.45;
                            var midY = height * 0.65;
                            var endX = width * 0.75;
                            var endY = height * 0.35;

                            ctx.beginPath();
                            if (progress < 0.5) {
                                var p = progress * 2;
                                ctx.moveTo(startX, startY);
                                ctx.lineTo(startX + (midX - startX) * p, startY + (midY - startY) * p);
                            } else {
                                var p = (progress - 0.5) * 2;
                                ctx.moveTo(startX, startY);
                                ctx.lineTo(midX, midY);
                                ctx.lineTo(midX + (endX - midX) * p, midY + (endY - midY) * p);
                            }
                            ctx.stroke();
                        }
                    }

                    // Error X animation
                    Item {
                        anchors.fill: parent
                        visible: !success

                        Rectangle {
                            width: parent.width * 0.6
                            height: 6
                            radius: 3
                            color: errorColor
                            anchors.centerIn: parent
                            rotation: 45

                            scale: 0
                            SequentialAnimation on scale {
                                running: !success
                                PauseAnimation { duration: 300 }
                                NumberAnimation {
                                    from: 0
                                    to: 1
                                    duration: 400
                                    easing.type: Easing.OutBack
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width * 0.6
                            height: 6
                            radius: 3
                            color: errorColor
                            anchors.centerIn: parent
                            rotation: -45

                            scale: 0
                            SequentialAnimation on scale {
                                running: !success
                                PauseAnimation { duration: 300 }
                                NumberAnimation {
                                    from: 0
                                    to: 1
                                    duration: 400
                                    easing.type: Easing.OutBack
                                }
                            }
                        }
                    }

                    // Pulse animation
                    SequentialAnimation on scale {
                        running: true
                        loops: 1
                        NumberAnimation { from: 0.8; to: 1.0; duration: 500; easing.type: Easing.OutCubic }
                    }
                }

                // Status text
                Text {
                    text: success ? qsTr("Installation Complete!") : qsTr("Installation Failed")
                    font.pixelSize: 36
                    font.bold: true
                    color: textColor
                    anchors.horizontalCenter: parent.horizontalCenter

                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: Qt.rgba(0, 0, 0, 0.4)
                        shadowHorizontalOffset: 0
                        shadowVerticalOffset: 2
                        shadowBlur: 0.3
                    }
                }

                Text {
                    text: success ?
                          qsTr("The system has been successfully installed on your computer") :
                          qsTr("An error occurred during installation")
                    font.pixelSize: 16
                    color: textMutedColor
                    wrapMode: Text.WordWrap
                    anchors.horizontalCenter: parent.horizontalCenter
                    horizontalAlignment: Text.AlignHCenter
                    width: 500
                }
            }

            // Summary/Error details
            Rectangle {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: 700
                Layout.preferredHeight: detailsColumn.height + 48
                radius: 16
                color: surfaceColor

                Column {
                    id: detailsColumn
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16

                    // Success summary
                    Column {
                        width: parent.width
                        spacing: 16
                        visible: success

                        Row {
                            spacing: 12

                            Text {
                                text: "\u{1F389}"  // Party popper
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Installation Summary")
                                font.pixelSize: 20
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // Summary items
                        Column {
                            width: parent.width
                            spacing: 12

                            Row {
                                width: parent.width
                                spacing: 12

                                Text {
                                    text: qsTr("Distribution:")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    width: 160
                                }

                                Text {
                                    text: installationSummary.distroName || "Linux"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Row {
                                width: parent.width
                                spacing: 12

                                Text {
                                    text: qsTr("Installation Target:")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    width: 160
                                }

                                Text {
                                    text: installationSummary.targetDisk || qsTr("Unknown")
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Row {
                                width: parent.width
                                spacing: 12

                                Text {
                                    text: qsTr("Installation Time:")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    width: 160
                                }

                                Text {
                                    text: installationSummary.installationTime || qsTr("Unknown")
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Row {
                                width: parent.width
                                spacing: 12
                                visible: (installationSummary.installedPackages || 0) > 0

                                Text {
                                    text: qsTr("Packages Installed:")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    width: 160
                                }

                                Text {
                                    text: (installationSummary.installedPackages || 0).toString()
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: textColor
                                }
                            }
                        }
                    }

                    // Error details
                    Column {
                        width: parent.width
                        spacing: 16
                        visible: !success

                        Row {
                            spacing: 12

                            Text {
                                text: "\u{1F6A8}"  // Police car light
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Error Details")
                                font.pixelSize: 20
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: errorText.height + 32
                            radius: 8
                            color: Qt.rgba(errorColor.r, errorColor.g, errorColor.b, 0.15)
                            border.color: errorColor
                            border.width: 1

                            Text {
                                id: errorText
                                anchors.fill: parent
                                anchors.margins: 16
                                text: errorMessage || qsTr("An unknown error occurred during installation")
                                font.pixelSize: 14
                                font.family: "monospace"
                                color: textColor
                                wrapMode: Text.Wrap
                            }
                        }

                        Button {
                            text: qsTr("View Full Logs")
                            anchors.horizontalCenter: parent.horizontalCenter
                            height: 36

                            background: Rectangle {
                                radius: 8
                                color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
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

                            onClicked: root.viewLogsClicked()
                        }
                    }
                }
            }

            // Action buttons
            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: 700
                spacing: 16

                // Success actions
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16
                    visible: success

                    Button {
                        text: qsTr("Reboot Now")
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        font.pixelSize: 16
                        font.bold: true

                        background: Rectangle {
                            radius: 12
                            color: {
                                if (parent.pressed) return Qt.darker(primaryColor, 1.3)
                                if (parent.hovered) return Qt.lighter(primaryColor, 1.15)
                                return primaryColor
                            }
                            border.color: Qt.lighter(primaryColor, 1.3)
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }

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
                            spacing: 8
                            anchors.centerIn: parent

                            Text {
                                text: "\u{1F504}"  // Counterclockwise arrows
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: parent.parent.text
                                font: parent.parent.font
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        onClicked: root.rebootClicked()
                    }

                    Button {
                        text: qsTr("Shutdown")
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        font.pixelSize: 16

                        background: Rectangle {
                            radius: 12
                            color: parent.pressed ? Qt.darker(surfaceColor, 1.2) : surfaceColor
                            border.color: textMutedColor
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }
                        }

                        contentItem: Row {
                            spacing: 8
                            anchors.centerIn: parent

                            Text {
                                text: "\u{23FB}"  // Power symbol
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: parent.parent.text
                                font: parent.parent.font
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        onClicked: root.shutdownClicked()
                    }

                    Button {
                        text: qsTr("Continue")
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        font.pixelSize: 16

                        background: Rectangle {
                            radius: 12
                            color: parent.pressed ? Qt.darker(surfaceColor, 1.2) : surfaceColor
                            border.color: textMutedColor
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }
                        }

                        contentItem: Row {
                            spacing: 8
                            anchors.centerIn: parent

                            Text {
                                text: "\u{1F5D7}"  // Desktop computer
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: parent.parent.text
                                font: parent.parent.font
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        onClicked: root.continueClicked()
                    }
                }

                // Failure actions
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16
                    visible: !success

                    Button {
                        text: qsTr("Retry Installation")
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        font.pixelSize: 16
                        font.bold: true

                        background: Rectangle {
                            radius: 12
                            color: {
                                if (parent.pressed) return Qt.darker(warningColor, 1.3)
                                if (parent.hovered) return Qt.lighter(warningColor, 1.15)
                                return warningColor
                            }
                            border.color: Qt.lighter(warningColor, 1.3)
                            border.width: 2

                            Behavior on color {
                                ColorAnimation { duration: 150 }
                            }
                        }

                        contentItem: Row {
                            spacing: 8
                            anchors.centerIn: parent

                            Text {
                                text: "\u{1F504}"  // Counterclockwise arrows
                                font.pixelSize: 20
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: parent.parent.text
                                font: parent.parent.font
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        onClicked: root.retryClicked()
                    }

                    Button {
                        text: qsTr("Exit Installer")
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56
                        font.pixelSize: 16

                        background: Rectangle {
                            radius: 12
                            color: parent.pressed ? Qt.darker(surfaceColor, 1.2) : surfaceColor
                            border.color: textMutedColor
                            border.width: 2

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

                        onClicked: root.continueClicked()
                    }
                }

                // Info text
                Text {
                    text: success ?
                          qsTr("Please remove the installation media before rebooting") :
                          qsTr("Check the logs for more details about the error")
                    font.pixelSize: 13
                    color: textMutedColor
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // Footer bar - transparent (anchored at bottom, aligned with Main.qml footer)
    Item {
        id: footerBar
        anchors {
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            margins: 0  // No additional margins - parent already has 32px from ColumnLayout
        }
        height: 48

        RowLayout {
            anchors.fill: parent
            spacing: 16

            // "Powered by Omnis Installer" (left)
            Text {
                text: qsTr("Powered by Omnis Installer")
                font.pixelSize: 12
                color: textMutedColor
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            // Website URL (right)
            Text {
                id: websiteLink
                text: root.websiteLabel || root.websiteUrl
                font.pixelSize: 12
                color: primaryColor
                visible: root.websiteUrl !== ""
                Layout.alignment: Qt.AlignVCenter

                MouseArea {
                    id: footerWebsiteMouseArea
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: Qt.openUrlExternally(root.websiteUrl)
                }

                // Underline on hover
                Rectangle {
                    width: parent.width
                    height: 1
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: -2
                    color: primaryColor
                    visible: footerWebsiteMouseArea.containsMouse
                }

                opacity: footerWebsiteMouseArea.containsMouse ? 0.7 : 1.0
                Behavior on opacity {
                    NumberAnimation { duration: 150 }
                }
            }
        }
    }
}
