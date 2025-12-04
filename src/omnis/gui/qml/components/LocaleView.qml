/*
 * LocaleView - Locale, Timezone, and Keyboard Configuration
 *
 * Displays:
 * - System locale selection
 * - Timezone selection with search
 * - Keyboard layout selection
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Item {
    id: root

    // Signals
    signal localeSelected(string locale)
    signal timezoneSelected(string timezone)
    signal keymapSelected(string keymap)

    // External properties (data models)
    property var localesModel: []
    property var timezonesModel: []
    property var keymapsModel: []

    // Current selections
    property string selectedLocale: ""
    property string selectedTimezone: ""
    property string selectedKeymap: ""

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
            anchors.fill: parent
            anchors.margins: 32
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 24

                // Title section
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: qsTr("Locale Settings")
                        font.pixelSize: 28
                        font.bold: true
                        color: textColor
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Text {
                        text: qsTr("Configure your system language, timezone, and keyboard layout")
                        font.pixelSize: 14
                        color: textMutedColor
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item { Layout.preferredHeight: 16 }

                // Configuration cards container - centered
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 600
                    Layout.minimumWidth: 400
                    spacing: 20

                    // ===== Locale selection card =====
                    Rectangle {
                        id: localeCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: localeContent.implicitHeight + 48
                        radius: 12
                        color: surfaceColor

                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: Qt.rgba(0, 0, 0, 0.2)
                            shadowHorizontalOffset: 0
                            shadowVerticalOffset: 2
                            shadowBlur: 0.3
                        }

                        ColumnLayout {
                            id: localeContent
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "\u{1F310}"
                                    font.pixelSize: 24
                                }

                                Text {
                                    text: qsTr("System Language")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Select your preferred system language and locale")
                                font.pixelSize: 13
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            ComboBox {
                                id: localeCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 44

                                model: localesModel
                                currentIndex: findIndex(localesModel, selectedLocale)

                                function findIndex(model, value) {
                                    if (!model || !value) return 0
                                    for (var i = 0; i < model.length; i++) {
                                        if (model[i] === value) return i
                                    }
                                    return 0
                                }

                                onActivated: function(index) {
                                    if (model && model[index]) {
                                        selectedLocale = model[index]
                                        localeSelected(selectedLocale)
                                    }
                                }

                                background: Rectangle {
                                    radius: 8
                                    color: localeCombo.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                    border.color: localeCombo.activeFocus ? primaryColor : Qt.darker(surfaceColor, 1.2)
                                    border.width: 2
                                }

                                contentItem: Text {
                                    text: localeCombo.displayText || qsTr("Select language...")
                                    font.pixelSize: 14
                                    color: localeCombo.displayText ? textColor : textMutedColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 12
                                    elide: Text.ElideRight
                                }

                                popup: Popup {
                                    y: localeCombo.height + 4
                                    width: localeCombo.width
                                    height: Math.min(contentItem.implicitHeight + 16, 300)
                                    padding: 8

                                    background: Rectangle {
                                        radius: 8
                                        color: surfaceColor
                                        border.color: primaryColor
                                        border.width: 1
                                    }

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: localeCombo.popup.visible ? localeCombo.delegateModel : null
                                        currentIndex: localeCombo.highlightedIndex
                                        ScrollIndicator.vertical: ScrollIndicator { }
                                    }
                                }

                                delegate: ItemDelegate {
                                    width: localeCombo.width - 16
                                    height: 40
                                    contentItem: Text {
                                        text: modelData
                                        font.pixelSize: 14
                                        color: highlighted ? textColor : textMutedColor
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        radius: 4
                                        color: highlighted ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2) : "transparent"
                                    }
                                    highlighted: localeCombo.highlightedIndex === index
                                }
                            }
                        }
                    }

                    // ===== Timezone selection card =====
                    Rectangle {
                        id: timezoneCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: timezoneContent.implicitHeight + 48
                        radius: 12
                        color: surfaceColor

                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: Qt.rgba(0, 0, 0, 0.2)
                            shadowHorizontalOffset: 0
                            shadowVerticalOffset: 2
                            shadowBlur: 0.3
                        }

                        ColumnLayout {
                            id: timezoneContent
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "\u{1F30D}"
                                    font.pixelSize: 24
                                }

                                Text {
                                    text: qsTr("Timezone")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Select your timezone for accurate time display")
                                font.pixelSize: 13
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            ComboBox {
                                id: timezoneCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 44

                                model: timezonesModel
                                currentIndex: findIndex(timezonesModel, selectedTimezone)

                                function findIndex(model, value) {
                                    if (!model || !value) return 0
                                    for (var i = 0; i < model.length; i++) {
                                        if (model[i] === value) return i
                                    }
                                    return 0
                                }

                                onActivated: function(index) {
                                    if (model && model[index]) {
                                        selectedTimezone = model[index]
                                        timezoneSelected(selectedTimezone)
                                    }
                                }

                                background: Rectangle {
                                    radius: 8
                                    color: timezoneCombo.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                    border.color: timezoneCombo.activeFocus ? primaryColor : Qt.darker(surfaceColor, 1.2)
                                    border.width: 2
                                }

                                contentItem: Text {
                                    text: timezoneCombo.displayText || qsTr("Select timezone...")
                                    font.pixelSize: 14
                                    color: timezoneCombo.displayText ? textColor : textMutedColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 12
                                    elide: Text.ElideRight
                                }

                                popup: Popup {
                                    y: timezoneCombo.height + 4
                                    width: timezoneCombo.width
                                    height: Math.min(contentItem.implicitHeight + 16, 300)
                                    padding: 8

                                    background: Rectangle {
                                        radius: 8
                                        color: surfaceColor
                                        border.color: primaryColor
                                        border.width: 1
                                    }

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: timezoneCombo.popup.visible ? timezoneCombo.delegateModel : null
                                        currentIndex: timezoneCombo.highlightedIndex
                                        ScrollIndicator.vertical: ScrollIndicator { }
                                    }
                                }

                                delegate: ItemDelegate {
                                    width: timezoneCombo.width - 16
                                    height: 40
                                    contentItem: Text {
                                        text: modelData
                                        font.pixelSize: 14
                                        color: highlighted ? textColor : textMutedColor
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        radius: 4
                                        color: highlighted ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2) : "transparent"
                                    }
                                    highlighted: timezoneCombo.highlightedIndex === index
                                }
                            }
                        }
                    }

                    // ===== Keyboard layout card =====
                    Rectangle {
                        id: keymapCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: keymapContent.implicitHeight + 48
                        radius: 12
                        color: surfaceColor

                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: Qt.rgba(0, 0, 0, 0.2)
                            shadowHorizontalOffset: 0
                            shadowVerticalOffset: 2
                            shadowBlur: 0.3
                        }

                        ColumnLayout {
                            id: keymapContent
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "\u{2328}\u{FE0F}"
                                    font.pixelSize: 24
                                }

                                Text {
                                    text: qsTr("Keyboard Layout")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Select your keyboard layout for proper key mapping")
                                font.pixelSize: 13
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            ComboBox {
                                id: keymapCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 44

                                model: keymapsModel
                                currentIndex: findIndex(keymapsModel, selectedKeymap)

                                function findIndex(model, value) {
                                    if (!model || !value) return 0
                                    for (var i = 0; i < model.length; i++) {
                                        if (model[i] === value) return i
                                    }
                                    return 0
                                }

                                onActivated: function(index) {
                                    if (model && model[index]) {
                                        selectedKeymap = model[index]
                                        keymapSelected(selectedKeymap)
                                    }
                                }

                                background: Rectangle {
                                    radius: 8
                                    color: keymapCombo.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                    border.color: keymapCombo.activeFocus ? primaryColor : Qt.darker(surfaceColor, 1.2)
                                    border.width: 2
                                }

                                contentItem: Text {
                                    text: keymapCombo.displayText || qsTr("Select layout...")
                                    font.pixelSize: 14
                                    color: keymapCombo.displayText ? textColor : textMutedColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 12
                                    elide: Text.ElideRight
                                }

                                popup: Popup {
                                    y: keymapCombo.height + 4
                                    width: keymapCombo.width
                                    height: Math.min(contentItem.implicitHeight + 16, 300)
                                    padding: 8

                                    background: Rectangle {
                                        radius: 8
                                        color: surfaceColor
                                        border.color: primaryColor
                                        border.width: 1
                                    }

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: keymapCombo.popup.visible ? keymapCombo.delegateModel : null
                                        currentIndex: keymapCombo.highlightedIndex
                                        ScrollIndicator.vertical: ScrollIndicator { }
                                    }
                                }

                                delegate: ItemDelegate {
                                    width: keymapCombo.width - 16
                                    height: 40
                                    contentItem: Text {
                                        text: modelData
                                        font.pixelSize: 14
                                        color: highlighted ? textColor : textMutedColor
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        radius: 4
                                        color: highlighted ? Qt.rgba(primaryColor.r, primaryColor.g, primaryColor.b, 0.2) : "transparent"
                                    }
                                    highlighted: keymapCombo.highlightedIndex === index
                                }
                            }
                        }
                    }

                    // Spacer at bottom
                    Item { Layout.preferredHeight: 20 }
                }
            }
        }
    }
}
