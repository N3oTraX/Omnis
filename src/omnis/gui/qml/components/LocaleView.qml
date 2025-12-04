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
    signal nextClicked()
    signal previousClicked()
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

    // Emit signals when selections change
    onSelectedLocaleChanged: if (selectedLocale) localeSelected(selectedLocale)
    onSelectedTimezoneChanged: if (selectedTimezone) timezoneSelected(selectedTimezone)
    onSelectedKeymapChanged: if (selectedKeymap) keymapSelected(selectedKeymap)

    // Theme colors
    property color primaryColor: "#5597e6"
    property color secondaryColor: "#3a7bc8"
    property color accentColor: "#6b9ce8"
    property color backgroundColor: "#1a1a1a"
    property color surfaceColor: "#32373c"
    property color textColor: "#fffded"
    property color textMutedColor: "#9CA3AF"

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
                text: qsTr("Locale Settings")
                font.pixelSize: 32
                font.bold: true
                color: textColor
                Layout.alignment: Qt.AlignHCenter
            }

            Text {
                text: qsTr("Configure your system language, timezone, and keyboard layout")
                font.pixelSize: 16
                color: textMutedColor
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                horizontalAlignment: Text.AlignHCenter
            }

            Item { Layout.fillHeight: true; Layout.preferredHeight: 24 }

            // Configuration cards container
            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: 700
                spacing: 24

                // Locale selection
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: localeColumn.height + 48
                    radius: 16
                    color: surfaceColor

                    Column {
                        id: localeColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\u{1F310}"  // Globe emoji
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("System Language")
                                font.pixelSize: 18
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            width: parent.width
                            text: qsTr("Select your preferred system language and locale")
                            font.pixelSize: 14
                            color: textMutedColor
                            wrapMode: Text.WordWrap
                        }

                        ComboBox {
                            id: localeCombo
                            width: parent.width
                            height: 48

                            model: localesModel
                            currentIndex: {
                                for (var i = 0; i < model.length; i++) {
                                    if (model[i] === selectedLocale) return i;
                                }
                                return 0;
                            }

                            onActivated: {
                                selectedLocale = model[currentIndex]
                            }

                            background: Rectangle {
                                radius: 8
                                color: localeCombo.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                border.color: localeCombo.activeFocus ? primaryColor : textMutedColor
                                border.width: 2

                                Behavior on border.color {
                                    ColorAnimation { duration: 150 }
                                }
                            }

                            contentItem: Text {
                                text: localeCombo.displayText
                                font.pixelSize: 16
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 16
                            }

                            popup: Popup {
                                y: localeCombo.height + 4
                                width: localeCombo.width
                                height: Math.min(contentItem.implicitHeight, 400)
                                padding: 8

                                background: Rectangle {
                                    radius: 8
                                    color: surfaceColor
                                    border.color: primaryColor
                                    border.width: 1

                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        shadowEnabled: true
                                        shadowColor: Qt.rgba(0, 0, 0, 0.3)
                                        shadowHorizontalOffset: 0
                                        shadowVerticalOffset: 4
                                        shadowBlur: 0.4
                                    }
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
                                height: 44

                                contentItem: Text {
                                    text: modelData
                                    font.pixelSize: 16
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

                // Timezone selection
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: timezoneColumn.height + 48
                    radius: 16
                    color: surfaceColor

                    Column {
                        id: timezoneColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\u{1F30D}"  // Globe with meridians
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Timezone")
                                font.pixelSize: 18
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            width: parent.width
                            text: qsTr("Select your timezone for accurate time display")
                            font.pixelSize: 14
                            color: textMutedColor
                            wrapMode: Text.WordWrap
                        }

                        ComboBox {
                            id: timezoneCombo
                            width: parent.width
                            height: 48

                            model: timezonesModel
                            currentIndex: {
                                for (var i = 0; i < model.length; i++) {
                                    if (model[i] === selectedTimezone) return i;
                                }
                                return 0;
                            }

                            onActivated: {
                                selectedTimezone = model[currentIndex]
                            }

                            background: Rectangle {
                                radius: 8
                                color: timezoneCombo.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                border.color: timezoneCombo.activeFocus ? primaryColor : textMutedColor
                                border.width: 2

                                Behavior on border.color {
                                    ColorAnimation { duration: 150 }
                                }
                            }

                            contentItem: Text {
                                text: timezoneCombo.displayText
                                font.pixelSize: 16
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 16
                            }

                            popup: Popup {
                                y: timezoneCombo.height + 4
                                width: timezoneCombo.width
                                height: Math.min(contentItem.implicitHeight, 400)
                                padding: 8

                                background: Rectangle {
                                    radius: 8
                                    color: surfaceColor
                                    border.color: primaryColor
                                    border.width: 1

                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        shadowEnabled: true
                                        shadowColor: Qt.rgba(0, 0, 0, 0.3)
                                        shadowHorizontalOffset: 0
                                        shadowVerticalOffset: 4
                                        shadowBlur: 0.4
                                    }
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
                                height: 44

                                contentItem: Text {
                                    text: modelData
                                    font.pixelSize: 16
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

                // Keyboard layout selection
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: keymapColumn.height + 48
                    radius: 16
                    color: surfaceColor

                    Column {
                        id: keymapColumn
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "\u{2328}\u{FE0F}"  // Keyboard emoji
                                font.pixelSize: 24
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: qsTr("Keyboard Layout")
                                font.pixelSize: 18
                                font.bold: true
                                color: textColor
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            width: parent.width
                            text: qsTr("Select your keyboard layout for proper key mapping")
                            font.pixelSize: 14
                            color: textMutedColor
                            wrapMode: Text.WordWrap
                        }

                        ComboBox {
                            id: keymapCombo
                            width: parent.width
                            height: 48

                            model: keymapsModel
                            currentIndex: {
                                for (var i = 0; i < model.length; i++) {
                                    if (model[i] === selectedKeymap) return i;
                                }
                                return 0;
                            }

                            onActivated: {
                                selectedKeymap = model[currentIndex]
                            }

                            background: Rectangle {
                                radius: 8
                                color: keymapCombo.pressed ? Qt.darker(backgroundColor, 1.2) : backgroundColor
                                border.color: keymapCombo.activeFocus ? primaryColor : textMutedColor
                                border.width: 2

                                Behavior on border.color {
                                    ColorAnimation { duration: 150 }
                                }
                            }

                            contentItem: Text {
                                text: keymapCombo.displayText
                                font.pixelSize: 16
                                color: textColor
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 16
                            }

                            popup: Popup {
                                y: keymapCombo.height + 4
                                width: keymapCombo.width
                                height: Math.min(contentItem.implicitHeight, 400)
                                padding: 8

                                background: Rectangle {
                                    radius: 8
                                    color: surfaceColor
                                    border.color: primaryColor
                                    border.width: 1

                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        shadowEnabled: true
                                        shadowColor: Qt.rgba(0, 0, 0, 0.3)
                                        shadowHorizontalOffset: 0
                                        shadowVerticalOffset: 4
                                        shadowBlur: 0.4
                                    }
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
                                height: 44

                                contentItem: Text {
                                    text: modelData
                                    font.pixelSize: 16
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
            }

            Item { Layout.fillHeight: true }

            // Navigation buttons
            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: 700
                spacing: 16

                Button {
                    text: qsTr("Previous")
                    Layout.preferredWidth: 150
                    Layout.preferredHeight: 48
                    font.pixelSize: 16

                    background: Rectangle {
                        radius: 8
                        color: parent.pressed ? Qt.darker(surfaceColor, 1.2) : surfaceColor
                        border.color: textMutedColor
                        border.width: 1

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

                    onClicked: root.previousClicked()
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: qsTr("Next")
                    Layout.preferredWidth: 150
                    Layout.preferredHeight: 48
                    font.pixelSize: 16
                    font.bold: true
                    enabled: selectedLocale !== "" && selectedTimezone !== "" && selectedKeymap !== ""

                    background: Rectangle {
                        radius: 8
                        color: {
                            if (!parent.enabled) return Qt.darker(surfaceColor, 1.2)
                            if (parent.pressed) return Qt.darker(primaryColor, 1.3)
                            if (parent.hovered) return Qt.lighter(primaryColor, 1.15)
                            return primaryColor
                        }
                        border.color: parent.enabled ? Qt.lighter(primaryColor, 1.3) : "transparent"
                        border.width: 1

                        Behavior on color {
                            ColorAnimation { duration: 150 }
                        }
                    }

                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: parent.enabled ? textColor : textMutedColor
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: root.nextClicked()
                }
            }
        }
    }
}
