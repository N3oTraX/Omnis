/*
 * ProgressView - Installation Progress Tracking
 *
 * Displays:
 * - Overall progress bar
 * - Current job name and progress
 * - Live installation log (auto-following, main content)
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
    // Non utilisée par la vue (la carte "Installation Steps" a été retirée,
    // redondante avec la carte du job courant) : conservée uniquement pour
    // compatibilité binaire avec Main.qml qui lie encore `jobsList:
    // engine.jobsList` — une property inutilisée assignée ne casse rien.
    property var jobsList: []  // Array of {name, status: "pending"|"running"|"completed"|"failed"}
    // Idem : conservée pour compatibilité avec Main.qml (onRetryClicked fait
    // `progressView.logMessages = []`). Le contenu du journal live vient
    // désormais directement de `engine.logTail` (voir carte "Installation
    // Log" plus bas), ce tableau n'est plus lu ni peuplé.
    property var logMessages: []  // Array of log message strings (legacy, unused)
    property bool showLog: true
    property string installationStatus: "idle"  // idle, running, success, failed
    property string errorMessage: ""
    property bool isStalled: false
    property bool indeterminate: false
    readonly property bool pulsing: root.isStalled || root.indeterminate

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
                            id: overallTrack
                            width: parent.width
                            height: 16
                            radius: 8
                            color: backgroundColor
                            clip: true

                            Rectangle {
                                id: overallFill
                                visible: !root.pulsing
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
                                        running: overallProgress < 100 && !root.pulsing
                                        loops: Animation.Infinite
                                        NumberAnimation {
                                            from: -shimmer.width
                                            to: overallFill.width
                                            duration: 2000
                                            easing.type: Easing.InOutQuad
                                        }
                                        PauseAnimation { duration: 500 }
                                    }
                                }
                            }

                            Rectangle {
                                id: indeterminateBar
                                visible: root.pulsing
                                width: overallTrack.width * 0.35
                                height: parent.height
                                radius: parent.radius
                                x: -width
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "transparent" }
                                    GradientStop { position: 0.5; color: primaryColor }
                                    GradientStop { position: 1.0; color: "transparent" }
                                }

                                SequentialAnimation on x {
                                    running: root.pulsing
                                    loops: Animation.Infinite
                                    NumberAnimation {
                                        from: -indeterminateBar.width
                                        to: overallTrack.width
                                        duration: 1400
                                        easing.type: Easing.InOutQuad
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

                                Text {
                                    visible: root.pulsing
                                    text: qsTr("Construction du système en cours… cela peut prendre plusieurs minutes ; l'interface peut sembler ralentie.")
                                    font.pixelSize: 13
                                    font.italic: true
                                    color: warningColor
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

                // Installation Log — contenu principal de la vue de progression.
                // La carte "Installation Steps" (liste des jobs) a été retirée :
                // elle était redondante avec la carte "job courant" ci-dessus et
                // n'affichait en pratique qu'une seule entrée ("welcome"). Le
                // journal live devient l'élément principal, en grand, et suit
                // automatiquement l'installation (voir TextArea plus bas).
                Rectangle {
                    Layout.fillWidth: true
                    // Hauteur FIXE en mode déplié (le ScrollView interne gère le
                    // défilement) : un calcul basé sur `logColumn.implicitHeight`
                    // ferait grandir la carte avec le contenu du journal, ce qui la
                    // ferait déborder de la fenêtre et rendrait le ScrollView interne
                    // inutile (rien ne défilerait, le texte serait simplement tronqué).
                    // Carte volontairement grande : c'est le contenu principal de la vue.
                    Layout.preferredHeight: showLog ? 480 : 60
                    radius: 16
                    color: surfaceColor
                    clip: true

                    Behavior on Layout.preferredHeight {
                        NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                    }

                        // ColumnLayout (et non Column) : le Column précédent
                        // était `anchors.fill: parent` avec une hauteur de
                        // ScrollView FIXE (380). Le total header+spacing+380
                        // ne correspondait pas exactement à la hauteur
                        // disponible (héritée de Layout.preferredHeight de la
                        // carte), laissant une marge basse incohérente avec
                        // la marge haute — la bordure arrondie du bas de la
                        // carte se retrouvait masquée par le rectangle sombre
                        // du journal. Avec ColumnLayout + Layout.fillHeight
                        // sur le ScrollView, celui-ci occupe exactement
                        // l'espace restant après le header, garantissant une
                        // marge bas identique à la marge haut (24px) quelle
                        // que soit la hauteur réelle du header.
                        ColumnLayout {
                            id: logColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            // Header
                            Row {
                                Layout.fillWidth: true
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
                                    text: showLog ? "▲" : "▼"
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

                            // Log content — occupe tout l'espace restant sous le
                            // header (Layout.fillHeight) au lieu d'une hauteur
                            // fixe : garantit une marge basse strictement égale à
                            // la marge haute (anchors.margins: 24 sur logColumn),
                            // donc la bordure arrondie basse de la carte reste
                            // toujours visible quelle que soit la hauteur réelle
                            // du header.
                            ScrollView {
                                id: logScroll
                                Layout.fillWidth: true
                                Layout.fillHeight: true
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
                                    font.family: branding.fontMonospace
                                    font.pixelSize: 12
                                    color: textColor
                                    // Source unique du journal live : property throttlée
                                    // (~5x/s) exposée par le moteur, contenant les ~300
                                    // dernières lignes. L'ancien signal per-ligne
                                    // logMessageAppended n'est plus émis (il saturait le
                                    // thread GUI sur les flux >10k lignes).
                                    text: engine.logTail

                                    background: Rectangle {
                                        color: backgroundColor
                                        radius: 8
                                    }

                                    // Auto-suivi systématique du bas : le tail affiche
                                    // toujours les dernières lignes du journal, donc on
                                    // se replace en bas à chaque mise à jour, sans
                                    // condition (pas de pin-to-bottom conditionnel).
                                    onTextChanged: cursorPosition = length
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
