/*
 * EnvironmentView - Desktop Environment (DE) & Edition/Flavor selection
 *
 * Mirrors the Calamares GLF OS flow (packagechooser@environment +
 * packagechooser@edition):
 *   - Desktop environment: Gnome / KDE Plasma (single choice)
 *   - Edition / flavor: Standard / Mini / Streamers / Studio / ... (single choice)
 *
 * Layout: two columns on a single page — desktop environments on the left,
 * editions/flavors on the right — so every option is visible at once.
 *
 * Persistence pattern (source of truth = engine):
 *   - `selectedDesktopEnvironment` / `selectedEdition` are readonly downward
 *     mirrors of engine.* — never reassigned imperatively.
 *   - Card clicks emit signals consumed by Main.qml, which calls
 *     engine.setDesktopEnvironment()/engine.setEdition(). The bindings stay
 *     live and always reflect the current state (no binding loops).
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // Signals (Main.qml wires these to engine.setX)
    signal desktopEnvironmentSelected(string environmentId)
    signal editionSelected(string editionId)

    // Data models (arrays of {id, name, description, iconUrl, default})
    property var desktopEnvironmentsModel: []
    property var editionsModel: []

    // Current selections: readonly downward mirrors of the engine source of truth.
    readonly property string selectedDesktopEnvironment: engine.desktopEnvironment
    readonly property string selectedEdition: engine.edition

    // Theme colors
    property color primaryColor: "#5597e6"
    property color secondaryColor: "#3a7bc8"
    property color accentColor: "#6b9ce8"
    property color backgroundColor: "#1a1a1a"
    property color surfaceColor: "#32373c"
    property color textColor: "#fffded"
    property color textMutedColor: "#9CA3AF"

    // Reusable card delegate for a DE or an edition (single-choice).
    // Inline component: root.* properties must be qualified (own scope).
    component ChoiceCard: Rectangle {
        id: card
        property var item: ({})
        property bool selected: false
        signal clicked()

        Layout.fillWidth: true
        Layout.preferredHeight: cardRow.implicitHeight + 28
        radius: 14
        color: selected
               ? Qt.rgba(root.primaryColor.r, root.primaryColor.g, root.primaryColor.b, 0.2)
               : root.surfaceColor
        border.color: selected ? root.primaryColor : "transparent"
        border.width: 2

        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: card.clicked()
        }

        RowLayout {
            id: cardRow
            anchors.fill: parent
            anchors.margins: 14
            spacing: 14

            // Icon (image if available, otherwise initial letter)
            Rectangle {
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                Layout.alignment: Qt.AlignVCenter
                radius: 8
                color: Qt.rgba(root.primaryColor.r, root.primaryColor.g, root.primaryColor.b, 0.2)

                Image {
                    id: cardIcon
                    anchors.fill: parent
                    anchors.margins: 6
                    source: card.item.iconUrl || ""
                    fillMode: Image.PreserveAspectFit
                    visible: status === Image.Ready
                }

                Text {
                    anchors.centerIn: parent
                    visible: cardIcon.status !== Image.Ready
                    text: (card.item.name || "?").charAt(0)
                    font.pixelSize: 20
                    font.bold: true
                    color: root.textColor
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 3

                Text {
                    text: card.item.name || card.item.id
                    font.pixelSize: 15
                    font.bold: true
                    color: root.textColor
                    Layout.fillWidth: true
                }

                Text {
                    text: card.item.description || ""
                    font.pixelSize: 12
                    color: root.textMutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    visible: text.length > 0
                }
            }

            // Selected indicator
            Text {
                text: "✓"
                font.pixelSize: 20
                font.bold: true
                color: root.primaryColor
                Layout.alignment: Qt.AlignVCenter
                visible: card.selected
            }
        }
    }

    // Content container with semi-transparent background
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(backgroundColor.r, backgroundColor.g, backgroundColor.b, 0.7)

        ScrollView {
            id: scrollView
            anchors.fill: parent
            anchors.margins: 20
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
                spacing: 16

                // Title section
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: qsTr("Desktop & Edition")
                        font.pixelSize: 24
                        font.bold: true
                        color: textColor
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Text {
                        text: qsTr("Choose your desktop environment and the software edition to install")
                        font.pixelSize: 14
                        color: textMutedColor
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item { Layout.preferredHeight: 8 }

                // ---------------------------------------------------------------
                // Two columns: Desktop Environment (left) + Edition (right)
                // ---------------------------------------------------------------
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 24

                    // ===== Left column: Desktop Environment =====
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        spacing: 12

                        Text {
                            text: qsTr("Desktop Environment")
                            font.pixelSize: 20
                            font.bold: true
                            color: textColor
                            Layout.fillWidth: true
                        }

                        Repeater {
                            model: desktopEnvironmentsModel

                            ChoiceCard {
                                item: modelData
                                selected: selectedDesktopEnvironment === modelData.id
                                onClicked: root.desktopEnvironmentSelected(modelData.id)
                            }
                        }

                        // Push cards to the top so both columns align.
                        Item { Layout.fillHeight: true }
                    }

                    // ===== Right column: Edition / flavor =====
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        spacing: 12

                        Text {
                            text: qsTr("Edition")
                            font.pixelSize: 20
                            font.bold: true
                            color: textColor
                            Layout.fillWidth: true
                        }

                        Repeater {
                            model: editionsModel

                            ChoiceCard {
                                item: modelData
                                selected: selectedEdition === modelData.id
                                onClicked: root.editionSelected(modelData.id)
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 24 }
            }
        }
    }
}
