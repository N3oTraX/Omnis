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

    // Required property for branding access (icons)
    required property var branding

    // Miroirs descendants (lecture seule) de la source de vérité `engine`.
    // Ils ne sont JAMAIS réassignés impérativement : les champs écrivent
    // directement via engine.setX(), donc ces bindings ne se cassent pas et
    // reflètent toujours l'état courant (résout la non-persistance des vues).
    readonly property string username: engine.username
    readonly property string fullName: engine.fullName
    readonly property string hostname: engine.hostname
    readonly property bool autoLogin: engine.autoLogin
    readonly property bool isAdmin: engine.isAdmin
    // Mot de passe root : par défaut identique au compte utilisateur. Les
    // champs root ne sont révélés que si rootSameAsUser est décoché.
    readonly property bool rootSameAsUser: engine.rootSameAsUser
    // Confirmations : purement locales (jamais envoyées à engine), servent aux
    // indicateurs de correspondance. Les mots de passe eux-mêmes sont write-only.
    property string passwordConfirm: ""
    property string rootPasswordConfirm: ""

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
    // Aligné sur UsersJob.USERNAME_PATTERN côté Python : un underscore est
    // autorisé en première position (^[a-z_][a-z0-9_-]*$).
    // Noms réservés par le système (alignés sur UsersJob.RESERVED_USERNAMES) :
    // les réutiliser (surtout « nobody ») fait échouer nixos-install.
    readonly property var reservedUsernames: [
        "root", "nobody", "nixos", "daemon", "bin", "sys", "messagebus", "sshd",
        "nscd", "polkituser", "rtkit", "avahi", "systemd-network", "systemd-resolve",
        "systemd-timesync", "systemd-coredump", "nm-openvpn", "dbus"
    ]
    readonly property bool usernameReserved: reservedUsernames.indexOf(usernameField.text) !== -1
    readonly property bool usernameValid: usernameField.text.length > 0
        && /^[a-z_][a-z0-9_-]*$/.test(usernameField.text)
        && !usernameReserved
    readonly property bool hostnameValid: hostnameField.text.length > 0 && /^[a-z][a-z0-9-]*$/.test(hostnameField.text)

    // Password criteria (NIST SP 800-63B inspired)
    readonly property bool pwdHasMinLength: passwordField.text.length >= 8
    readonly property bool pwdHasUppercase: /[A-Z]/.test(passwordField.text)
    readonly property bool pwdHasLowercase: /[a-z]/.test(passwordField.text)
    readonly property bool pwdHasNumber: /[0-9]/.test(passwordField.text)
    readonly property bool pwdHasSpecial: /[^a-zA-Z0-9]/.test(passwordField.text)
    readonly property bool passwordValid: pwdHasMinLength
    readonly property bool passwordsMatch: passwordField.text === passwordConfirmField.text && passwordField.text.length > 0

    // Root password validation (only relevant when not reusing the user account
    // password). When rootSameAsUser is true, root credentials inherit the user
    // password, so no separate validation is required.
    readonly property bool rootPasswordValid: rootPasswordField.text.length >= 8
    readonly property bool rootPasswordsMatch: rootPasswordField.text === rootPasswordConfirmField.text && rootPasswordField.text.length > 0
    readonly property bool rootValid: rootSameAsUser || (rootPasswordValid && rootPasswordsMatch)

    readonly property bool canProceed: usernameValid && hostnameValid && passwordValid && passwordsMatch && rootValid
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
        height: 16

        Image {
            source: met ? (root.branding ? root.branding.iconCheckUrl : "") : (root.branding ? root.branding.iconCrossUrl : "")
            width: 16
            height: 16
            anchors.verticalCenter: parent.verticalCenter
            sourceSize.width: 16
            sourceSize.height: 16
            visible: source != ""

            // SVG color overlay for theming
            layer.enabled: !engine.softwareRendering
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
            font.pixelSize: 11
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

        layer.enabled: !engine.softwareRendering
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
            anchors.margins: 48
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
                // Largeur pilotée par le ScrollView (un seul mode de
                // dimensionnement, calqué sur LocaleView). Le padding
                // horizontal est porté par anchors.margins du ScrollView.
                width: scrollView.availableWidth
                spacing: 12

                Item { height: 8 }

                // Title
                Text {
                    text: qsTr("Create User Account")
                    font.pixelSize: 24
                    font.bold: true
                    color: textColor
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: qsTr("Set up your user account and system hostname")
                    font.pixelSize: 13
                    color: textMutedColor
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                // Form container — grille 2 colonnes (Variante B)
                GridLayout {
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 10
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 980

                    // Username section (ligne 1, colonne 0)
                    Rectangle {
                        Layout.row: 0
                        Layout.column: 0
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredHeight: usernameColumn.implicitHeight + 32
                        radius: 12
                        color: surfaceColor

                        Column {
                            id: usernameColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconUserUrl : ""
                                }

                                Text {
                                    text: qsTr("Username")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: "*"
                                    font.pixelSize: 15
                                    color: errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: usernameField
                                width: parent.width
                                height: 40
                                placeholderText: qsTr("username (lowercase, no spaces)")
                                font.pixelSize: 16

                                // Source de vérité unique : lecture/écriture
                                // directes vers engine (pas de miroir local
                                // réassigné qui casserait le binding descendant).
                                text: engine.username
                                onTextChanged: engine.setUsername(text)

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
                                text: usernameField.text.length > 0 && usernameReserved ?
                                      qsTr("This username is reserved by the system — please choose another") :
                                      usernameField.text.length > 0 && !usernameValid ?
                                      qsTr("Username must start with a letter and contain only lowercase letters, numbers, hyphens, or underscores") :
                                      qsTr("This will be your login name")
                                font.pixelSize: 11
                                color: usernameField.text.length > 0 && !usernameValid ? errorColor : textMutedColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Full name section (ligne 1, colonne 1)
                    Rectangle {
                        Layout.row: 0
                        Layout.column: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredHeight: fullNameColumn.implicitHeight + 32
                        radius: 12
                        color: surfaceColor

                        Column {
                            id: fullNameColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconFullnameUrl : ""
                                }

                                Text {
                                    text: qsTr("Full Name")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: fullNameField
                                width: parent.width
                                height: 40
                                placeholderText: qsTr("Your full name")
                                font.pixelSize: 16

                                text: engine.fullName
                                onTextChanged: engine.setFullName(text)

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
                                font.pixelSize: 11
                                color: textMutedColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Hostname section (ligne 2, colonne 0)
                    Rectangle {
                        Layout.row: 1
                        Layout.column: 0
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredHeight: hostnameColumn.implicitHeight + 32
                        radius: 12
                        color: surfaceColor

                        Column {
                            id: hostnameColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconHostnameUrl : ""
                                }

                                Text {
                                    text: qsTr("Computer Name")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: "*"
                                    font.pixelSize: 15
                                    color: errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            TextField {
                                id: hostnameField
                                width: parent.width
                                height: 40
                                placeholderText: qsTr("hostname (lowercase, no spaces)")
                                font.pixelSize: 16

                                text: engine.hostname
                                onTextChanged: engine.setHostname(text)

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
                                font.pixelSize: 11
                                color: hostnameField.text.length > 0 && !hostnameValid ? errorColor : textMutedColor
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // Password section (ligne 3, pleine largeur)
                    Rectangle {
                        Layout.row: 2
                        Layout.column: 0
                        Layout.fillWidth: true
                        Layout.columnSpan: 2
                        Layout.preferredHeight: passwordColumn.implicitHeight + 32
                        radius: 12
                        color: surfaceColor

                        Column {
                            id: passwordColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconPasswordUrl : ""
                                }

                                Text {
                                    text: qsTr("Password")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: "*"
                                    font.pixelSize: 15
                                    color: errorColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            // Password + Confirm côte à côte (Variante B)
                            RowLayout {
                                width: parent.width
                                spacing: 10

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    spacing: 8

                            TextField {
                                id: passwordField
                                Layout.fillWidth: true
                                height: 40
                                placeholderText: qsTr("Enter password (min 8 characters)")
                                font.pixelSize: 16
                                echoMode: showPasswordCheck.checked ? TextInput.Normal : TextInput.Password

                                // SÉCURITÉ : mot de passe write-only. On écrit
                                // vers engine mais on ne binde JAMAIS la valeur en
                                // descendant (pas de text: engine.password). Le
                                // champ garde sa propre valeur locale de saisie.
                                onTextChanged: engine.setPassword(text)

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
                                }  // fin colonne gauche (password)

                                // Colonne droite : confirmation + indicateur match
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    spacing: 8

                                    TextField {
                                        id: passwordConfirmField
                                        Layout.fillWidth: true
                                        height: 40
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
                                        Layout.fillWidth: true
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

                                            layer.enabled: !engine.softwareRendering
                                            layer.effect: MultiEffect {
                                                colorization: 1.0
                                                colorizationColor: passwordsMatch ? successColor : errorColor
                                            }
                                        }

                                        Text {
                                            text: passwordsMatch ? qsTr("Passwords match") : qsTr("Passwords do not match")
                                            font.pixelSize: 11
                                            color: passwordsMatch ? successColor : errorColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }  // fin colonne droite (confirm)
                            }  // fin RowLayout password/confirm

                            // Password strength indicator (pleine largeur sous les champs)
                            Column {
                                width: parent.width
                                spacing: 4

                                Row {
                                    width: parent.width
                                    spacing: 8

                                    Rectangle {
                                        width: (parent.width - 24) / 4
                                        height: 3
                                        radius: 2
                                        color: passwordStrength >= 25 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                    Rectangle {
                                        width: (parent.width - 24) / 4
                                        height: 3
                                        radius: 2
                                        color: passwordStrength >= 50 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                    Rectangle {
                                        width: (parent.width - 24) / 4
                                        height: 3
                                        radius: 2
                                        color: passwordStrength >= 75 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                    Rectangle {
                                        width: (parent.width - 24) / 4
                                        height: 3
                                        radius: 2
                                        color: passwordStrength >= 90 ? passwordStrengthColor : Qt.darker(surfaceColor, 1.2)
                                    }
                                }

                                Text {
                                    text: qsTr("Strength: ") + passwordStrengthText
                                    font.pixelSize: 11
                                    color: passwordField.text.length > 0 ? passwordStrengthColor : textMutedColor
                                }
                            }

                            // Password criteria checklist (masquée tant que vide)
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

                                        layer.enabled: !engine.softwareRendering
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

                            // Séparateur léger avant la section root.
                            Rectangle {
                                width: parent.width
                                height: 1
                                color: Qt.darker(surfaceColor, 1.3)
                            }

                            // Mot de passe root : réutiliser celui de l'utilisateur
                            // par défaut (coché). Décocher révèle deux champs root.
                            CheckBox {
                                id: rootSameAsUserCheck
                                checked: engine.rootSameAsUser
                                onCheckedChanged: engine.setRootSameAsUser(checked)

                                text: qsTr("Use the same password for the root account")
                                font.pixelSize: 14

                                indicator: Rectangle {
                                    implicitWidth: 20
                                    implicitHeight: 20
                                    x: rootSameAsUserCheck.leftPadding
                                    y: parent.height / 2 - height / 2
                                    radius: 4
                                    border.color: rootSameAsUserCheck.checked ? primaryColor : textMutedColor
                                    border.width: 2
                                    color: rootSameAsUserCheck.checked ? primaryColor : "transparent"

                                    Image {
                                        anchors.centerIn: parent
                                        source: root.branding ? root.branding.iconCheckUrl : ""
                                        width: 12
                                        height: 12
                                        sourceSize.width: 12
                                        sourceSize.height: 12
                                        visible: rootSameAsUserCheck.checked && source != ""

                                        layer.enabled: !engine.softwareRendering
                                        layer.effect: MultiEffect {
                                            colorization: 1.0
                                            colorizationColor: textColor
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"
                                        color: textColor
                                        font.pixelSize: 14
                                        visible: rootSameAsUserCheck.checked && (!root.branding || root.branding.iconCheckUrl === "")
                                    }
                                }

                                contentItem: Text {
                                    text: rootSameAsUserCheck.text
                                    font: rootSameAsUserCheck.font
                                    color: textColor
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: rootSameAsUserCheck.indicator.width + rootSameAsUserCheck.spacing
                                    wrapMode: Text.WordWrap
                                }
                            }

                            // Champs root (password + confirm) — collapse complet
                            // quand rootSameAsUser est coché (coût ~0px).
                            RowLayout {
                                width: parent.width
                                spacing: 10
                                visible: !root.rootSameAsUser

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    spacing: 8

                                    TextField {
                                        id: rootPasswordField
                                        Layout.fillWidth: true
                                        height: 40
                                        placeholderText: qsTr("Root password (min 8 characters)")
                                        font.pixelSize: 16
                                        echoMode: showPasswordCheck.checked ? TextInput.Normal : TextInput.Password

                                        // SÉCURITÉ : write-only (cf. password).
                                        onTextChanged: engine.setRootPassword(text)

                                        background: Rectangle {
                                            radius: 8
                                            color: rootPasswordField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                            border.color: {
                                                if (!rootPasswordField.activeFocus) return textMutedColor;
                                                if (rootPasswordField.text.length === 0) return primaryColor;
                                                return rootPasswordValid ? successColor : errorColor;
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
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    spacing: 8

                                    TextField {
                                        id: rootPasswordConfirmField
                                        Layout.fillWidth: true
                                        height: 40
                                        placeholderText: qsTr("Confirm root password")
                                        font.pixelSize: 16
                                        echoMode: showPasswordCheck.checked ? TextInput.Normal : TextInput.Password

                                        text: root.rootPasswordConfirm
                                        onTextChanged: root.rootPasswordConfirm = text

                                        background: Rectangle {
                                            radius: 8
                                            color: rootPasswordConfirmField.activeFocus ? Qt.darker(backgroundColor, 1.1) : backgroundColor
                                            border.color: {
                                                if (!rootPasswordConfirmField.activeFocus) return textMutedColor;
                                                if (rootPasswordConfirmField.text.length === 0) return primaryColor;
                                                return rootPasswordsMatch ? successColor : errorColor;
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

                                    // Indicateur de correspondance des mots de passe root.
                                    Row {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        visible: rootPasswordConfirmField.text.length > 0

                                        Image {
                                            source: rootPasswordsMatch ? (root.branding ? root.branding.iconCheckUrl : "") : (root.branding ? root.branding.iconCrossUrl : "")
                                            width: 16
                                            height: 16
                                            anchors.verticalCenter: parent.verticalCenter
                                            sourceSize.width: 16
                                            sourceSize.height: 16
                                            visible: source != ""

                                            layer.enabled: !engine.softwareRendering
                                            layer.effect: MultiEffect {
                                                colorization: 1.0
                                                colorizationColor: rootPasswordsMatch ? successColor : errorColor
                                            }
                                        }

                                        Text {
                                            text: rootPasswordsMatch ? qsTr("Passwords match") : qsTr("Passwords do not match")
                                            font.pixelSize: 11
                                            color: rootPasswordsMatch ? successColor : errorColor
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Options section (ligne 2, colonne 1)
                    Rectangle {
                        Layout.row: 1
                        Layout.column: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredHeight: optionsColumn.implicitHeight + 32
                        radius: 12
                        color: surfaceColor

                        Column {
                            id: optionsColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10

                            Row {
                                width: parent.width
                                spacing: 12

                                SectionIcon {
                                    iconSource: root.branding ? root.branding.iconSettingsUrl : ""
                                }

                                Text {
                                    text: qsTr("Account Options")
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: textColor
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            CheckBox {
                                id: autoLoginCheck
                                checked: engine.autoLogin
                                onCheckedChanged: engine.setAutoLogin(checked)

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

                                        layer.enabled: !engine.softwareRendering
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
                                checked: engine.isAdmin
                                onCheckedChanged: engine.setIsAdmin(checked)

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

                                        layer.enabled: !engine.softwareRendering
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

                // Note : la navigation (Précédent/Suivant) est assurée par le
                // footer global de Main.qml, qui consomme usersView.isValid via
                // canProceedToNext(). Pas de barre de navigation interne ici.

                Item { height: 8 }
            }
        }
    }
}
