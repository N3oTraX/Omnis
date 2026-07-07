/*
 * ProgressView - Installation Progress Tracking
 *
 * Displays:
 * - Overall progress bar
 * - Current job name and progress
 * - Job list with status indicators
 * - Log output area (collapsible)
 * - Installation animation
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // External properties
    property int overallProgress: 0  // 0-100
    property string currentJobName: ""
    property int currentJobProgress: 0  // 0-100
    property string currentJobMessage: ""
    property var jobsList: []  // Array of {name, status: "pending"|"running"|"completed"|"failed"}
    property var logMessages: []  // Array of log message strings
    property bool showLog: false
    property string installationStatus: "idle"  // idle, running, success, failed
    property string errorMessage: ""

    // Distro info
    property string distroName: ""
    property string distroLogo: ""

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

            // Title
            Text {
                text: qsTr("Installing...")
                font.pixelSize: 32
                font.bold: true
                color: textColor
                Layout.alignment: Qt.AlignHCenter
            }

            Text {
                text: qsTr("Please wait while the system is being installed")
                font.pixelSize: 16
                color: textMutedColor
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                horizontalAlignment: Text.AlignHCenter
            }

            Item { Layout.preferredHeight: 16 }

            // Progress section - défile verticalement si le contenu dépasse
            // l'espace disponible (petites fenêtres / redimensionnement) afin
            // que la carte "Installation Log" reste toujours atteignable et
            // ne soit jamais repoussée hors écran / coupée.
            Flickable {
                id: cardsFlickable
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: cardsColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }

                ColumnLayout {
                    id: cardsColumn
                    width: Math.min(parent.width, 800)
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 24

                // Overall progress card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: overallProgressColumn.implicitHeight + 48
                    radius: 16
                    color: surfaceColor

                    Column {
                        id: overallProgressColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\u{1F4C8}"  // Chart increasing
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Overall Progress")
                                font.pixelSize: 20
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Item { Layout.fillWidth: true }

                            Text {
                                text: overallProgress + "%"
                                font.pixelSize: 24
                                font.bold: true
                                color: primaryColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // Overall progress bar
                        Rectangle {
                            width: parent.width
                            height: 16
                            radius: 8
                            color: backgroundColor

                            Rectangle {
                                width: parent.width * (overallProgress / 100)
                                height: parent.height
                                radius: parent.radius
                                color: primaryColor
                                clip: true  // keep the shimmer inside the filled bar

                                Behavior on width {
                                    NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                                }

                                // Animated gradient
                                Rectangle {
                                    anchors.fill: parent
                                    radius: parent.radius
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.2) }
                                        GradientStop { position: 0.5; color: "transparent" }
                                        GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.1) }
                                    }
                                }

                                // Shimmer effect
                                Rectangle {
                                    id: shimmer
                                    width: parent.width * 0.3
                                    height: parent.height
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: "transparent" }
                                        GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.3) }
                                        GradientStop { position: 1.0; color: "transparent" }
                                    }

                                    SequentialAnimation on x {
                                        running: overallProgress < 100
                                        loops: Animation.Infinite
                                        NumberAnimation {
                                            from: -shimmer.width
                                            to: parent.width
                                            duration: 2000
                                            easing.type: Easing.InOutQuad
                                        }
                                        PauseAnimation { duration: 500 }
                                    }
                                }
                            }
                        }
                    }
                }

                // Current job card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: currentJobColumn.implicitHeight + 48
                    radius: 16
                    color: surfaceColor
                    visible: currentJobName.length > 0

                    Column {
                        id: currentJobColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Row {
                            width: parent.width
                            spacing: 12

                            // Rotating spinner
                            Rectangle {
                                width: 32
                                height: 32
                                radius: 16
                                color: "transparent"
                                border.color: primaryColor
                                border.width: 3
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: primaryColor
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    y: 4

                                    SequentialAnimation on rotation {
                                        running: true
                                        loops: Animation.Infinite
                                        NumberAnimation {
                                            from: 0
                                            to: 360
                                            duration: 1000
                                            easing.type: Easing.Linear
                                        }
                                    }

                                    transform: Rotation {
                                        origin.x: 3
                                        origin.y: parent.parent.height / 2 - 4
                                        angle: 0
                                    }
                                }
                            }

                            Column {
                                width: parent.width - 44
                                spacing: 4

                                Text {
                                    text: currentJobName
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: textColor
                                }

                                Text {
                                    text: currentJobMessage || qsTr("Working...")
                                    font.pixelSize: 14
                                    color: textMutedColor
                                    wrapMode: Text.WordWrap
                                    width: parent.width
                                }
                            }
                        }

                        // Current job progress bar
                        Rectangle {
                            width: parent.width
                            height: 8
                            radius: 4
                            color: backgroundColor

                            Rectangle {
                                width: parent.width * (currentJobProgress / 100)
                                height: parent.height
                                radius: parent.radius
                                color: accentColor

                                Behavior on width {
                                    NumberAnimation { duration: 200 }
                                }
                            }
                        }

                        Text {
                            text: currentJobProgress + "%"
                            font.pixelSize: 13
                            color: textMutedColor
                        }
                    }
                }

                // Jobs list card
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(jobsColumn.implicitHeight + 48, 400)
                    radius: 16
                    color: surfaceColor

                    Column {
                        id: jobsColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\u{1F4CB}"  // Clipboard
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Installation Steps")
                                font.pixelSize: 20
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        ScrollView {
                            id: jobsScrollView
                            width: parent.width
                            height: Math.min(jobsListView.contentHeight, 280)
                            clip: true

                            // Improve wheel scroll speed (3x faster)
                            WheelHandler {
                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                onWheel: function(event) {
                                    var flickable = jobsScrollView.contentItem
                                    var multiplier = 3.0
                                    var deltaY = event.angleDelta.y * multiplier
                                    var newY = flickable.contentY - (deltaY / 120.0 * 40)
                                    flickable.contentY = Math.max(0, Math.min(flickable.contentHeight - flickable.height, newY))
                                    event.accepted = true
                                }
                            }

                            ListView {
                                id: jobsListView
                                width: parent.width
                                spacing: 8
                                model: jobsList

                                delegate: Row {
                                    width: parent.width
                                    spacing: 12
                                    height: 32

                                    // Status indicator
                                    Rectangle {
                                        width: 24
                                        height: 24
                                        radius: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: {
                                            switch(modelData.status) {
                                                case "completed": return successColor;
                                                case "running": return accentColor;
                                                case "failed": return errorColor;
                                                default: return Qt.darker(surfaceColor, 1.3);
                                            }
                                        }

                                        Behavior on color {
                                            ColorAnimation { duration: 200 }
                                        }

                                        Text {
                                            anchors.centerIn: parent
                                            text: {
                                                switch(modelData.status) {
                                                    case "completed": return "\u2713";
                                                    case "running": return "";
                                                    case "failed": return "\u2717";
                                                    default: return "";
                                                }
                                            }
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: textColor
                                        }

                                        // Animated ring for running status
                                        Rectangle {
                                            anchors.fill: parent
                                            radius: parent.radius
                                            color: "transparent"
                                            border.color: Qt.lighter(accentColor, 1.3)
                                            border.width: 2
                                            visible: modelData.status === "running"

                                            SequentialAnimation on scale {
                                                running: modelData.status === "running"
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 1.0; to: 1.3; duration: 800 }
                                                NumberAnimation { from: 1.3; to: 1.0; duration: 800 }
                                            }

                                            SequentialAnimation on opacity {
                                                running: modelData.status === "running"
                                                loops: Animation.Infinite
                                                NumberAnimation { from: 1.0; to: 0.0; duration: 800 }
                                                NumberAnimation { from: 0.0; to: 1.0; duration: 800 }
                                            }
                                        }
                                    }

                                    Text {
                                        text: modelData.name
                                        font.pixelSize: 14
                                        color: {
                                            switch(modelData.status) {
                                                case "completed": return textColor;
                                                case "running": return textColor;
                                                case "failed": return errorColor;
                                                default: return textMutedColor;
                                            }
                                        }
                                        font.bold: modelData.status === "running"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                        }
                    }
                }

                // Log viewer (collapsible)
                Rectangle {
                    Layout.fillWidth: true
                    // Hauteur FIXE en mode déplié (le ScrollView interne gère le
                    // défilement) : l'ancien calcul `logColumn.implicitHeight + 48`
                    // faisait grandir la carte avec le contenu du journal, ce qui la
                    // faisait déborder de la fenêtre et rendait le ScrollView interne
                    // inutile (rien ne défilait, le texte était simplement tronqué).
                    Layout.preferredHeight: showLog ? 400 : 60
                    radius: 16
                    color: surfaceColor
                    clip: true

                    Behavior on Layout.preferredHeight {
                        NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                    }

                    // Alimentation live du journal pendant l'installation. Le backend
                    // émet une ligne redigée à la fois via logMessageAppended(line);
                    // on l'ajoute au tableau existant et on force la notification
                    // (les mutations de tableau JS ne déclenchent pas les bindings
                    // QML automatiquement).
                    Connections {
                        target: engine
                        function onLogMessageAppended(line) {
                            root.logMessages.push(line)
                            // Borne la mémoire : conserve les 2000 dernières lignes
                            if (root.logMessages.length > 2000) {
                                root.logMessages = root.logMessages.slice(root.logMessages.length - 2000)
                            }
                            root.logMessagesChanged()
                        }
                    }

                    Column {
                        id: logColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        // Header
                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\u{1F4DD}"  // Memo
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Installation Log")
                                font.pixelSize: 20
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Item { Layout.fillWidth: true }

                            Button {
                                text: showLog ? "\u25B2" : "\u25BC"
                                width: 32
                                height: 32
                                anchors.verticalCenter: parent.verticalCenter

                                background: Rectangle {
                                    radius: 8
                                    color: parent.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                    border.color: textMutedColor
                                    border.width: 1
                                }

                                contentItem: Text {
                                    text: parent.text
                                    font.pixelSize: 16
                                    color: textColor
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }

                                onClicked: showLog = !showLog
                            }
                        }

                        // Log content
                        ScrollView {
                            id: logScroll
                            width: parent.width
                            height: 300
                            clip: true
                            visible: showLog

                            // Défilement vertical seul : la TextArea est bornée
                            // en largeur (availableWidth) pour que wrapMode enroule
                            // le texte au lieu de déborder horizontalement — cause
                            // de l'illisibilité et du "scroll cassé".
                            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded

                            opacity: showLog ? 1 : 0
                            Behavior on opacity {
                                NumberAnimation { duration: 200 }
                            }

                            TextArea {
                                id: logTextArea
                                width: logScroll.availableWidth
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextArea.Wrap
                                font.family: "monospace"
                                font.pixelSize: 12
                                color: textColor
                                text: logMessages.join("\n")

                                background: Rectangle {
                                    color: backgroundColor
                                    radius: 8
                                }

                                // Auto-suivi du bas UNIQUEMENT si l'utilisateur y
                                // est déjà : il peut remonter lire les lignes
                                // précédentes sans être ramené en bas à chaque
                                // nouvelle ligne (ce qui donnait "ne scroll pas").
                                property bool pinnedToBottom: true
                                onTextChanged: if (pinnedToBottom) cursorPosition = length
                            }

                            // Détecte si l'utilisateur a fait défiler vers le haut.
                            Connections {
                                target: logScroll.ScrollBar.vertical
                                function onPositionChanged() {
                                    var vbar = logScroll.ScrollBar.vertical
                                    logTextArea.pinnedToBottom = (vbar.position + vbar.size >= 0.98)
                                }
                            }
                        }
                    }
                }
                }
            }

            // Info text
            Text {
                text: qsTr("Do not turn off your computer during installation")
                font.pixelSize: 14
                color: textMutedColor
                Layout.alignment: Qt.AlignHCenter
            }
        }
    }
}
