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
    signal keyboardVariantSelected(string variant)

    // External properties (data models)
    property var localesModel: []
    property var localesModelNative: []  // Array of {code: string, name: string}
    property var timezonesModel: []
    property var keymapsModel: []
    property var keyboardVariantsModel: []

    // Helper function to get native name from locale code
    function getNativeNameForLocale(localeCode) {
        for (var i = 0; i < localesModelNative.length; i++) {
            if (localesModelNative[i].code === localeCode) {
                return localesModelNative[i].name
            }
        }
        return localeCode  // Fallback to code if not found
    }

    // Helper function to get locale code from native name
    function getLocaleCodeForNativeName(nativeName) {
        for (var i = 0; i < localesModelNative.length; i++) {
            if (localesModelNative[i].name === nativeName) {
                return localesModelNative[i].code
            }
        }
        return nativeName  // Fallback to name if not found
    }

    // Get display model for locale combo (native names)
    function getLocaleDisplayModel() {
        var names = []
        for (var i = 0; i < localesModelNative.length; i++) {
            names.push(localesModelNative[i].name)
        }
        return names.length > 0 ? names : localesModel
    }

    // Current selections
    property string selectedLocale: ""
    property string selectedTimezone: ""
    property string selectedKeymap: ""
    property string selectedKeyboardVariant: ""

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
            anchors.margins: 20
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 16

                // Title section
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: qsTr("Country & Language")
                        font.pixelSize: 24
                        font.bold: true
                        color: textColor
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Text {
                        text: qsTr("Configure your system language, timezone, and keyboard layout")
                        font.pixelSize: 13
                        color: textMutedColor
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Item { Layout.preferredHeight: 8 }

                // Configuration cards container - centered
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 600
                    Layout.minimumWidth: 400
                    spacing: 12

                    // ===== Locale selection card =====
                    Rectangle {
                        id: localeCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: localeContent.implicitHeight + 32
                        radius: 10
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
                            anchors.margins: 16
                            spacing: 8

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
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            SearchableComboBox {
                                id: localeCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40

                                model: getLocaleDisplayModel()
                                currentValue: getNativeNameForLocale(selectedLocale)
                                placeholder: qsTr("Select language...")
                                searchPlaceholder: qsTr("Search languages...")

                                primaryColor: root.primaryColor
                                backgroundColor: root.backgroundColor
                                surfaceColor: root.surfaceColor
                                textColor: root.textColor
                                textMutedColor: root.textMutedColor

                                onValueSelected: function(nativeName) {
                                    // Convert native name back to locale code
                                    var localeCode = getLocaleCodeForNativeName(nativeName)
                                    selectedLocale = localeCode
                                    localeSelected(localeCode)
                                }
                            }
                        }
                    }

                    // ===== Timezone selection card =====
                    Rectangle {
                        id: timezoneCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: timezoneContent.implicitHeight + 32
                        radius: 10
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
                            anchors.margins: 16
                            spacing: 8

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
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            SearchableComboBox {
                                id: timezoneCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40

                                model: timezonesModel
                                currentValue: selectedTimezone
                                placeholder: qsTr("Select timezone...")
                                searchPlaceholder: qsTr("Search timezones...")

                                primaryColor: root.primaryColor
                                backgroundColor: root.backgroundColor
                                surfaceColor: root.surfaceColor
                                textColor: root.textColor
                                textMutedColor: root.textMutedColor

                                onValueSelected: function(value) {
                                    selectedTimezone = value
                                    timezoneSelected(value)
                                }
                            }
                        }
                    }

                    // ===== Keyboard layout card =====
                    Rectangle {
                        id: keymapCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: keymapContent.implicitHeight + 32
                        radius: 10
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
                            anchors.margins: 16
                            spacing: 8

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
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            SearchableComboBox {
                                id: keymapCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40

                                model: keymapsModel
                                currentValue: selectedKeymap
                                placeholder: qsTr("Select layout...")
                                searchPlaceholder: qsTr("Search layouts...")

                                primaryColor: root.primaryColor
                                backgroundColor: root.backgroundColor
                                surfaceColor: root.surfaceColor
                                textColor: root.textColor
                                textMutedColor: root.textMutedColor

                                onValueSelected: function(value) {
                                    selectedKeymap = value
                                    keymapSelected(value)
                                }
                            }
                        }
                    }

                    // ===== Keyboard variant card =====
                    Rectangle {
                        id: variantCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: variantContent.implicitHeight + 32
                        radius: 10
                        color: surfaceColor
                        visible: keyboardVariantsModel.length > 1

                        layer.enabled: true
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: Qt.rgba(0, 0, 0, 0.2)
                            shadowHorizontalOffset: 0
                            shadowVerticalOffset: 2
                            shadowBlur: 0.3
                        }

                        ColumnLayout {
                            id: variantContent
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "\u{1F4DD}"
                                    font.pixelSize: 24
                                }

                                Text {
                                    text: qsTr("Keyboard Variant")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Select a specific variant for the keyboard layout")
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            ComboBox {
                                id: variantCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40

                                model: keyboardVariantsModel
                                currentIndex: {
                                    const idx = keyboardVariantsModel.indexOf(selectedKeyboardVariant)
                                    return idx >= 0 ? idx : 0
                                }

                                background: Rectangle {
                                    color: backgroundColor
                                    radius: 6
                                    border.color: variantCombo.activeFocus ? primaryColor : Qt.rgba(textColor.r, textColor.g, textColor.b, 0.2)
                                    border.width: variantCombo.activeFocus ? 2 : 1
                                }

                                contentItem: Text {
                                    leftPadding: 12
                                    text: variantCombo.displayText
                                    color: textColor
                                    verticalAlignment: Text.AlignVCenter
                                }

                                onActivated: function(index) {
                                    const variant = keyboardVariantsModel[index]
                                    selectedKeyboardVariant = variant
                                    keyboardVariantSelected(variant)
                                }
                            }
                        }
                    }

                    // ===== Keyboard test area card =====
                    Rectangle {
                        id: testCard
                        Layout.fillWidth: true
                        Layout.preferredHeight: testContent.implicitHeight + 32
                        radius: 10
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
                            id: testContent
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: "\u{1F4AC}"
                                    font.pixelSize: 24
                                }

                                Text {
                                    text: qsTr("Test Your Keyboard")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Type here to test your keyboard configuration")
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            TextField {
                                id: keyboardTestField
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40
                                placeholderText: qsTr("Type something to test...")

                                background: Rectangle {
                                    color: backgroundColor
                                    radius: 6
                                    border.color: keyboardTestField.activeFocus ? primaryColor : Qt.rgba(textColor.r, textColor.g, textColor.b, 0.2)
                                    border.width: keyboardTestField.activeFocus ? 2 : 1
                                }

                                color: textColor
                                placeholderTextColor: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.6)
                                leftPadding: 12
                                rightPadding: 12
                            }
                        }
                    }

                    // Spacer at bottom
                    Item { Layout.preferredHeight: 8 }
                }
            }
        }
    }
}
