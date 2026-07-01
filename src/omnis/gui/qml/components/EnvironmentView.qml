/*
 * EnvironmentView - Desktop Environment (DE) & Edition/Flavor selection
 *
 * Mirrors the Calamares GLF OS flow (packagechooser@environment +
 * packagechooser@edition):
 *   - Desktop environment: Gnome / KDE Plasma (single choice)
 *   - Edition / flavor: Standard / Mini / Streamers / Studio / ... (single choice)
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
                // Desktop environment section
                // ---------------------------------------------------------------
                Text {
                    text: qsTr("Desktop Environment")
                    font.pixelSize: 20
                    font.bold: true
                    color: textColor
                    Layout.fillWidth: true
                }

                Repeater {
                    model: desktopEnvironmentsModel

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: deColumn.implicitHeight + 32
                        radius: 16
                        color: selectedDesktopEnvironment === modelData.id
                               ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2)
                               : surfaceColor
                        border.color: selectedDesktopEnvironment === modelData.id ? primaryColor : "transparent"
                        border.width: 2

                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.desktopEnvironmentSelected(modelData.id)
                        }

                        RowLayout {
                            id: deColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 16

                            // Icon (image if available, otherwise initial letter)
                            Rectangle {
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 48
                                Layout.alignment: Qt.AlignVCenter
                                radius: 8
                                color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2)

                                Image {
                                    id: deIcon
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    source: modelData.iconUrl || ""
                                    fillMode: Image.PreserveAspectFit
                                    visible: status === Image.Ready
                                }

                                Text {
                                    anchors.centerIn: parent
                                    visible: deIcon.status !== Image.Ready
                                    text: (modelData.name || "?").charAt(0)
                                    font.pixelSize: 22
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                spacing: 4

                                Text {
                                    text: modelData.name || modelData.id
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: modelData.description || ""
                                    font.pixelSize: 13
                                    color: textMutedColor
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    visible: text.length > 0
                                }
                            }

                            // Selected indicator
                            Text {
                                text: "✓"
                                font.pixelSize: 22
                                font.bold: true
                                color: primaryColor
                                Layout.alignment: Qt.AlignVCenter
                                visible: selectedDesktopEnvironment === modelData.id
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 16 }

                // ---------------------------------------------------------------
                // Edition / flavor section
                // ---------------------------------------------------------------
                Text {
                    text: qsTr("Edition")
                    font.pixelSize: 20
                    font.bold: true
                    color: textColor
                    Layout.fillWidth: true
                }

                Repeater {
                    model: editionsModel

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: editionColumn.implicitHeight + 32
                        radius: 16
                        color: selectedEdition === modelData.id
                               ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2)
                               : surfaceColor
                        border.color: selectedEdition === modelData.id ? primaryColor : "transparent"
                        border.width: 2

                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.editionSelected(modelData.id)
                        }

                        RowLayout {
                            id: editionColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 16

                            Rectangle {
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 48
                                Layout.alignment: Qt.AlignVCenter
                                radius: 8
                                color: Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2)

                                Image {
                                    id: editionIcon
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    source: modelData.iconUrl || ""
                                    fillMode: Image.PreserveAspectFit
                                    visible: status === Image.Ready
                                }

                                Text {
                                    anchors.centerIn: parent
                                    visible: editionIcon.status !== Image.Ready
                                    text: (modelData.name || "?").charAt(0)
                                    font.pixelSize: 22
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                spacing: 4

                                Text {
                                    text: modelData.name || modelData.id
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: modelData.description || ""
                                    font.pixelSize: 13
                                    color: textMutedColor
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    visible: text.length > 0
                                }
                            }

                            Text {
                                text: "✓"
                                font.pixelSize: 22
                                font.bold: true
                                color: primaryColor
                                Layout.alignment: Qt.AlignVCenter
                                visible: selectedEdition === modelData.id
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 24 }
            }
        }
    }
}
