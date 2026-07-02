{
  lib,
  python3Packages,
  qt6,
}:

# Omnis - modular GLF-OS installer (PySide6/QML). Packaged as a Qt-wrapped
# Python application so QML imports and Qt platform plugins resolve at runtime.
python3Packages.buildPythonApplication {
  pname = "omnis-installer";
  version = "0.4.2";

  src = ./.;

  pyproject = true;

  build-system = [ python3Packages.hatchling ];

  # Qt wrapping: exposes QT_PLUGIN_PATH + QML2_IMPORT_PATH to the `omnis`
  # entry point. qtdeclarative provides QtQuick + QtQuick.Controls; qtsvg
  # renders the SVG icons used across the wizard.
  nativeBuildInputs = [ qt6.wrapQtAppsHook ];

  buildInputs = [
    qt6.qtbase
    qt6.qtdeclarative
    qt6.qtsvg
  ];

  # wrapQtAppsHook wraps the entry point but does NOT inject the QML import
  # path for a Python app, so QtQuick / QtQuick.Controls (bundled in
  # qtdeclarative) are not found and the QML interface fails to load. The
  # Python wrapper honors makeWrapperArgs, so set QML2_IMPORT_PATH there
  # (mirrors the working dev launcher run-omnis.sh).
  makeWrapperArgs = [
    "--prefix QML2_IMPORT_PATH : ${qt6.qtdeclarative}/lib/qt-6/qml"
  ];

  dependencies = with python3Packages; [
    pyside6
    pydantic
    pyyaml
    tzdata
  ];

  # PySide6 + QML cannot be import-checked headlessly in the sandbox.
  pythonImportsCheck = [ ];
  doCheck = false;

  # Ship the config + theme tree so the NixOS module can provision
  # /etc/omnis/omnis.yaml and the theme assets from the same versioned source.
  postInstall = ''
    mkdir -p $out/share/omnis
    cp -r config $out/share/omnis/config
  '';

  meta = {
    description = "Omnis - modular GLF-OS installer (Calamares alternative)";
    homepage = "https://github.com/N3oTraX/Omnis";
    license = lib.licenses.gpl3Plus;
    mainProgram = "omnis";
    platforms = lib.platforms.linux;
  };
}
