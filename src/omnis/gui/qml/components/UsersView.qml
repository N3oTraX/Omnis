/*
 * UsersView - User Account Configuration
 *
 * Displays:
 * - Username input with validation
 * - Full name input
 * - Hostname input with validation
 * - Password fields with strength indicator and criteria checklist
 * - Autologin checkbox
 * - Admin privileges checkbox
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

    // Required property for branding access (icons)
    required property var branding

    // External properties (for data binding with engine)
    property string username: ""
    property string fullName: ""
    property string hostname: ""
    property string password: ""
    property string passwordConfirm: ""
    property bool autoLogin: false
    property bool isAdmin: true

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

    // Validation states
    readonly property bool usernameValid: usernameField.text.length > 0 && /^[a-z][a-z0-9_-]*$/.test(usernameField.text)
    readonly property bool hostnameValid: hostnameField.text.length > 0 && /^[a-z][a-z0-9-]*$/.test(hostnameField.text)

    // Password criteria (NIST SP 800-63B inspired)
    readonly property bool pwdHasMinLength: passwordField.text.length >= 8
    readonly property bool pwdHasUppercase: /[A-Z]/.test(passwordField.text)
    readonly property bool pwdHasLowercase: /[a-z]/.test(passwordField.text)
    readonly property bool pwdHasNumber: /[0-9]/.test(passwordField.text)
    readonly property bool pwdHasSpecial: /[^a-zA-Z0-9]/.test(passwordField.text)
    readonly property bool passwordValid: pwdHasMinLength
    readonly property bool passwordsMatch: passwordField.text === passwordConfirmField.text && passwordField.text.length > 0
    readonly property bool canProceed: usernameValid && hostnameValid && passwordValid && passwordsMatch
    readonly property alias isValid: root.canProceed  // Alias for Main.qml compatibility

    // Password strength calculation
    readonly property int passwordStrength: {
        var pwd = passwordField.text;
        if (pwd.length === 0) return 0;
        var strength = 0;
        if (pwdHasMinLength) strength += 25;
        if (pwd.length >= 12) strength += 25;
        if (pwdHasLowercase && pwdHasUppercase) strength += 25;
        if (pwdHasNumber) strength += 15;
        if (pwdHasSpecial) strength += 10;
        return Math.min(100, strength);
    }

    readonly property color passwordStrengthColor: {
        if (passwordStrength < 40) return errorColor;
        if (passwordStrength < 70) return warningColor;
        return successColor;
    }

    readonly property string passwordStrengthText: {
        if (passwordStrength === 0) return qsTr("Enter password");
        if (passwordStrength < 40) return qsTr("Weak");
        if (passwordStrength < 70) return qsTr("Medium");
        return qsTr("Strong");
    }

    // Reusable component for validation criteria row
    component CriteriaRow: Row {
        property bool met: false
        property string criteriaText: ""

        spacing: 8
        height: 20

        Image {
            source: met ? (root.branding ? root.branding.iconCheckUrl : "") : (root.branding ? root.branding.iconCrossUrl : "")
            width: 16
            height: 16
            anchors.verticalCenter: parent.verticalCenter
            sourceSize.width: 16
            sourceSize.height: 16
            visible: source != ""

            // SVG color overlay for theming
            layer.enabled: true
            layer.effect: MultiEffect {
                colorization: 1.0
                colorizationColor: met ? successColor : textMutedColor
            }
        }

        // Fallback text icon when image not available
        Text {
            text: met ? "\u2713" : "\u2717"
            font.pixelSize: 14
            color: met ? successColor : textMutedColor
            anchors.verticalCenter: parent.verticalCenter
            visible: !root.branding || (root.branding.iconCheckUrl === "" && root.branding.iconCrossUrl === "")
        }

        Text {
            text: criteriaText
            font.pixelSize: 12
            color: met ? successColor : textMutedColor
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // Reusable component for section icon
    component SectionIcon: Image {
        property string iconSource: ""

        source: iconSource
        width: 24
        height: 24
        sourceSize.width: 24
        sourceSize.height: 24
        anchors.verticalCenter: parent.verticalCenter
        visible: source != ""

        layer.enabled: true
        layer.effect: MultiEffect {
            colorization: 1.0
            colorizationColor: textColor
        }
    }

    // Content container
    Rectangle {
        anchors.fill: parent
        color: "transparent"

        ScrollView {
            id: scrollView
            anchors.fill: parent
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
                width: scrollView.availableWidth
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 48
                spacing: 32

                Item { height: 24 }

                // Title
                Text {
                    text: qsTr("Create User Account")
                    font.pixelSize: 32
                    font.bold: true
                    color: textColor
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: qsTr("Set up your user account and system hostname")
                    font.pixelSize: 16
                    color: textMutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                Item { Layout.preferredHeight: 16 }

                // Form container
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 700
                    spacing: 24

                    // Username section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: usernameColumn.height + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: usernameColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconUserUrl : ""
                                }

                                Text {
                                    text: qsTr("Username")
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: "*"
                                    font.pixelSize: 18
                                    color: errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: usernameField
                                width: parent.width
                                height: 48
                                placeholderText: qsTr("username (lowercase, no spaces)")
                                font.pixelSize: 16

                                text: root.username
                                onTextChanged: root.username = text

                                background: Rectangle {
                                    radius: 8
                                    color: usernameField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                    border.color: {
                                        if (!usernameField.activeFocus) return textMutedColor;
                                        if (usernameField.text.length === 0) return primaryColor;
                                        return usernameValid ? successColor : errorColor;
                                    }
                                    border.width: 2

                                    Behavior on border.color {
                                        ColorAnimation { duration: 150 }
                                    }
                                }

                                color: textColor
                                selectionColor: primaryColor
                                selectedTextColor: textColor
                                leftPadding: 16
                            }

                            Text {
                                width: parent.width
                                text: usernameField.text.length > 0 && !usernameValid ?
                                      qsTr("Username must start with a letter and contain only lowercase letters, numbers, hyphens, or underscores") :
                                      qsTr("This will be your login name")
                                font.pixelSize: 12
                                color: usernameField.text.length > 0 && !usernameValid ? errorColor : textMutedColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Full name section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: fullNameColumn.height + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: fullNameColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconFullnameUrl : ""
                                }

                                Text {
                                    text: qsTr("Full Name")
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: fullNameField
                                width: parent.width
                                height: 48
                                placeholderText: qsTr("Your full name")
                                font.pixelSize: 16

                                text: root.fullName
                                onTextChanged: root.fullName = text

                                background: Rectangle {
                                    radius: 8
                                    color: fullNameField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                    border.color: fullNameField.activeFocus ? primaryColor : textMutedColor
                                    border.width: 2

                                    Behavior on border.color {
                                        ColorAnimation { duration: 150 }
                                    }
                                }

                                color: textColor
                                selectionColor: primaryColor
                                selectedTextColor: textColor
                                leftPadding: 16
                            }

                            Text {
                                width: parent.width
                                text: qsTr("Optional: Display name for your account")
                                font.pixelSize: 12
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Hostname section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: hostnameColumn.height + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: hostnameColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconHostnameUrl : ""
                                }

                                Text {
                                    text: qsTr("Computer Name")
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: "*"
                                    font.pixelSize: 18
                                    color: errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: hostnameField
                                width: parent.width
                                height: 48
                                placeholderText: qsTr("hostname (lowercase, no spaces)")
                                font.pixelSize: 16

                                text: root.hostname
                                onTextChanged: root.hostname = text

                                background: Rectangle {
                                    radius: 8
                                    color: hostnameField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                    border.color: {
                                        if (!hostnameField.activeFocus) return textMutedColor;
                                        if (hostnameField.text.length === 0) return primaryColor;
                                        return hostnameValid ? successColor : errorColor;
                                    }
                                    border.width: 2

                                    Behavior on border.color {
                                        ColorAnimation { duration: 150 }
                                    }
                                }

                                color: textColor
                                selectionColor: primaryColor
                                selectedTextColor: textColor
                                leftPadding: 16
                            }

                            Text {
                                width: parent.width
                                text: hostnameField.text.length > 0 && !hostnameValid ?
                                      qsTr("Hostname must start with a letter and contain only lowercase letters, numbers, or hyphens") :
                                      qsTr("Your computer's network name")
                                font.pixelSize: 12
                                color: hostnameField.text.length > 0 && !hostnameValid ? errorColor : textMutedColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Password section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: passwordColumn.height + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: passwordColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconPasswordUrl : ""
                                }

                                Text {
                                    text: qsTr("Password")
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: "*"
                                    font.pixelSize: 18
                                    color: errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: passwordField
                                width: parent.width
                                height: 48
                                placeholderText: qsTr("Enter password (min 8 characters)")
                                font.pixelSize: 16
                                echoMode: showPasswordCheck.checked ? TextInput.Normal : TextInput.Password

                                text: root.password
                                onTextChanged: root.password = text

                                background: Rectangle {
                                    radius: 8
                                    color: passwordField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                    border.color: {
                                        if (!passwordField.activeFocus) return textMutedColor;
                                        if (passwordField.text.length === 0) return primaryColor;
                                        return passwordValid ? successColor : errorColor;
                                    }
                                    border.width: 2

                                    Behavior on border.color {
                                        ColorAnimation { duration: 150 }
                                    }
                                }

                                color: textColor
                                selectionColor: primaryColor
                                selectedTextColor: textColor
                                leftPadding: 16
                            }

                            // Password strength indicator
                            Column {
                                width: parent.width
                                spacing: 8

                                Row {
                                    width: parent.width
                                    spacing: 8

                                    Rectangle {
                                        width: (parent.width - 16) / 4
                                        height: 4
                                        radius: 2
                                        color: passwordStrength >= 25 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                    Rectangle {
                                        width: (parent.width - 16) / 4
                                        height: 4
                                        radius: 2
                                        color: passwordStrength >= 50 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                    Rectangle {
                                        width: (parent.width - 16) / 4
                                        height: 4
                                        radius: 2
                                        color: passwordStrength >= 75 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                    Rectangle {
                                        width: (parent.width - 16) / 4
                                        height: 4
                                        radius: 2
                                        color: passwordStrength >= 90 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                }

                                Text {
                                    text: qsTr("Strength: ") + passwordStrengthText
                                    font.pixelSize: 12
                                    color: passwordField.text.length > 0 ? passwordStrengthColor : textMutedColor
                                }
                            }

                            // Password criteria checklist
                            Column {
                                width: parent.width
                                spacing: 4
                                visible: passwordField.text.length > 0

                                CriteriaRow {
                                    met: pwdHasMinLength
                                    criteriaText: qsTr("At least 8 characters")
                                }

                                CriteriaRow {
                                    met: pwdHasUppercase
                                    criteriaText: qsTr("At least one uppercase letter")
                                }

                                CriteriaRow {
                                    met: pwdHasLowercase
                                    criteriaText: qsTr("At least one lowercase letter")
                                }

                                CriteriaRow {
                                    met: pwdHasNumber
                                    criteriaText: qsTr("At least one number")
                                }

                                CriteriaRow {
                                    met: pwdHasSpecial
                                    criteriaText: qsTr("At least one special character")
                                }
                            }

                            TextField {
                                id: passwordConfirmField
                                width: parent.width
                                height: 48
                                placeholderText: qsTr("Confirm password")
                                font.pixelSize: 16
                                echoMode: showPasswordCheck.checked ? TextInput.Normal : TextInput.Password

                                text: root.passwordConfirm
                                onTextChanged: root.passwordConfirm = text

                                background: Rectangle {
                                    radius: 8
                                    color: passwordConfirmField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                    border.color: {
                                        if (!passwordConfirmField.activeFocus) return textMutedColor;
                                        if (passwordConfirmField.text.length === 0) return primaryColor;
                                        return passwordsMatch ? successColor : errorColor;
                                    }
                                    border.width: 2

                                    Behavior on border.color {
                                        ColorAnimation { duration: 150 }
                                    }
                                }

                                color: textColor
                                selectionColor: primaryColor
                                selectedTextColor: textColor
                                leftPadding: 16
                            }

                            // Password match indicator
                            Row {
                                spacing: 8
                                visible: passwordConfirmField.text.length > 0

                                Image {
                                    source: passwordsMatch ? (root.branding ? root.branding.iconCheckUrl : "") : (root.branding ? root.branding.iconCrossUrl : "")
                                    width: 16
                                    height: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    sourceSize.width: 16
                                    sourceSize.height: 16
                                    visible: source != ""

                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        colorization: 1.0
                                        colorizationColor: passwordsMatch ? successColor : errorColor
                                    }
                                }

                                Text {
                                    text: passwordsMatch ? qsTr("Passwords match") : qsTr("Passwords do not match")
                                    font.pixelSize: 12
                                    color: passwordsMatch ? successColor : errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            CheckBox {
                                id: showPasswordCheck
                                text: qsTr("Show password")
                                font.pixelSize: 14

                                indicator: Rectangle {
                                    implicitWidth: 20
                                    implicitHeight: 20
                                    x: showPasswordCheck.leftPadding
                                    y: parent.height / 2 - height / 2
                                    radius: 4
                                    border.color: showPasswordCheck.checked ? primaryColor : textMutedColor
                                    border.width: 2
                                    color: showPasswordCheck.checked ? primaryColor : "transparent"

                                    Image {
                                        anchors.centerIn: parent
                                        source: root.branding ? root.branding.iconCheckUrl : ""
                                        width: 12
                                        height: 12
                                        sourceSize.width: 12
                                        sourceSize.height: 12
                                        visible: showPasswordCheck.checked && source != ""

                                        layer.enabled: true
                                        layer.effect: MultiEffect {
                                            colorization: 1.0
                                            colorizationColor: textColor
                                        }
                                    }

                                    // Fallback checkmark
                                    Text {
                                        anchors.centerIn: parent
                                        text: "\u2713"
                                        color: textColor
                                        font.pixelSize: 14
                                        visible: showPasswordCheck.checked && (!root.branding || root.branding.iconCheckUrl === "")
                                    }
                                }

                                contentItem: Text {
                                    text: showPasswordCheck.text
                                    font: showPasswordCheck.font
                                    color: textColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: showPasswordCheck.indicator.width + showPasswordCheck.spacing
                                }
                            }
                        }
                    }

                    // Options section
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: optionsColumn.height + 48
                        radius: 16
                        color: surfaceColor

                        Column {
                            id: optionsColumn
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconSettingsUrl : ""
                                }

                                Text {
                                    text: qsTr("Account Options")
                                    font.pixelSize: 18
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            CheckBox {
                                id: autoLoginCheck
                                checked: root.autoLogin
                                onCheckedChanged: root.autoLogin = checked

                                text: qsTr("Log in automatically without asking for password")
                                font.pixelSize: 14

                                indicator: Rectangle {
                                    implicitWidth: 20
                                    implicitHeight: 20
                                    x: autoLoginCheck.leftPadding
                                    y: parent.height / 2 - height / 2
                                    radius: 4
                                    border.color: autoLoginCheck.checked ? primaryColor : textMutedColor
                                    border.width: 2
                                    color: autoLoginCheck.checked ? primaryColor : "transparent"

                                    Image {
                                        anchors.centerIn: parent
                                        source: root.branding ? root.branding.iconCheckUrl : ""
                                        width: 12
                                        height: 12
                                        sourceSize.width: 12
                                        sourceSize.height: 12
                                        visible: autoLoginCheck.checked && source != ""

                                        layer.enabled: true
                                        layer.effect: MultiEffect {
                                            colorization: 1.0
                                            colorizationColor: textColor
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "\u2713"
                                        color: textColor
                                        font.pixelSize: 14
                                        visible: autoLoginCheck.checked && (!root.branding || root.branding.iconCheckUrl === "")
                                    }
                                }

                                contentItem: Text {
                                    text: autoLoginCheck.text
                                    font: autoLoginCheck.font
                                    color: textColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: autoLoginCheck.indicator.width + autoLoginCheck.spacing
                                    wrapMode: Text.WordWrap
                                }
                            }

                            CheckBox {
                                id: adminCheck
                                checked: root.isAdmin
                                onCheckedChanged: root.isAdmin = checked

                                text: qsTr("Use administrator privileges (sudo access)")
                                font.pixelSize: 14

                                indicator: Rectangle {
                                    implicitWidth: 20
                                    implicitHeight: 20
                                    x: adminCheck.leftPadding
                                    y: parent.height / 2 - height / 2
                                    radius: 4
                                    border.color: adminCheck.checked ? primaryColor : textMutedColor
                                    border.width: 2
                                    color: adminCheck.checked ? primaryColor : "transparent"

                                    Image {
                                        anchors.centerIn: parent
                                        source: root.branding ? root.branding.iconCheckUrl : ""
                                        width: 12
                                        height: 12
                                        sourceSize.width: 12
                                        sourceSize.height: 12
                                        visible: adminCheck.checked && source != ""

                                        layer.enabled: true
                                        layer.effect: MultiEffect {
                                            colorization: 1.0
                                            colorizationColor: textColor
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "\u2713"
                                        color: textColor
                                        font.pixelSize: 14
                                        visible: adminCheck.checked && (!root.branding || root.branding.iconCheckUrl === "")
                                    }
                                }

                                contentItem: Text {
                                    text: adminCheck.text
                                    font: adminCheck.font
                                    color: textColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: adminCheck.indicator.width + adminCheck.spacing
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 16 }

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
                        enabled: canProceed

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

                Item { height: 24 }
            }
        }
    }
}
