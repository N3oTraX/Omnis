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

                    // ===== Keyboard layout & variant card (combined, side-by-side) =====
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
                                    text: qsTr("Keyboard Configuration")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: textColor
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Select your keyboard layout and variant")
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }

                            // Side-by-side layout (50/50)
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                // Left: Keyboard Layout (50%)
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 100
                                    spacing: 4

                                    Text {
                                        text: qsTr("Layout")
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: textMutedColor
                                    }

                                    SearchableComboBox {
                                        id: keymapCombo
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 36

                                        model: keymapsModel
                                        currentValue: selectedKeymap
                                        placeholder: qsTr("Select...")
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

                                // Right: Keyboard Variant (50%)
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 100
                                    spacing: 4

                                    Text {
                                        text: qsTr("Variant")
                                        font.pixelSize: 12
                                        font.bold: true
                                        color: textMutedColor
                                    }

                                    ComboBox {
                                        id: variantCombo
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 36

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
                                            text: variantCombo.displayText || qsTr("Default")
                                            color: textColor
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideRight
                                        }

                                        delegate: ItemDelegate {
                                            width: variantCombo.width
                                            contentItem: Text {
                                                text: modelData || qsTr("Default")
                                                color: textColor
                                                elide: Text.ElideRight
                                            }
                                            highlighted: variantCombo.highlightedIndex === index
                                            background: Rectangle {
                                                color: highlighted ? primaryColor : "transparent"
                                            }
                                        }

                                        popup: Popup {
                                            y: variantCombo.height
                                            width: variantCombo.width
                                            implicitHeight: contentItem.implicitHeight
                                            padding: 1

                                            contentItem: ListView {
                                                clip: true
                                                implicitHeight: Math.min(contentHeight, 200)
                                                model: variantCombo.popup.visible ? variantCombo.delegateModel : null
                                                currentIndex: variantCombo.highlightedIndex
                                                ScrollIndicator.vertical: ScrollIndicator {}
                                            }

                                            background: Rectangle {
                                                color: surfaceColor
                                                border.color: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.2)
                                                radius: 6
                                            }
                                        }

                                        onActivated: function(index) {
                                            const variant = keyboardVariantsModel[index]
                                            selectedKeyboardVariant = variant
                                            keyboardVariantSelected(variant)
                                        }
                                    }
                                }
                            }

                            // Compact keyboard test area (inline)
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                spacing: 8

                                Text {
                                    text: qsTr("Test:")
                                    font.pixelSize: 11
                                    color: textMutedColor
                                }

                                TextField {
                                    id: keyboardTestField
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 28
                                    placeholderText: qsTr("Type to test keyboard...")
                                    font.pixelSize: 12

                                    background: Rectangle {
                                        color: Qt.rgba(backgroundColor.r, backgroundColor.g, backgroundColor.b, 0.5)
                                        radius: 4
                                        border.color: keyboardTestField.activeFocus ? primaryColor : Qt.rgba(textColor.r, textColor.g, textColor.b, 0.15)
                                        border.width: 1
                                    }

                                    color: textColor
                                    placeholderTextColor: Qt.rgba(textMutedColor.r, textMutedColor.g, textMutedColor.b, 0.5)
                                    leftPadding: 8
                                    rightPadding: 8
                                }
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
