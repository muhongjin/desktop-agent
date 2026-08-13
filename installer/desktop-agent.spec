import os
import tomllib
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)
from PyInstaller.utils.hooks import copy_metadata


project_root = Path(SPECPATH).parent
source_root = project_root / "src"
package_root = source_root / "desktop_agent"
icon_path = package_root / "resources" / "app-icon.ico"
project = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
app_version = project["version"]
version_numbers = [int(value) for value in app_version.split(".")]
version_tuple = tuple((version_numbers + [0, 0, 0, 0])[:4])
bundle_name = os.environ.get(
    "DESKTOP_AGENT_BUNDLE_NAME", f"DesktopAgent-{app_version}-win64"
)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=version_tuple,
        prodvers=version_tuple,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Desktop Agent Contributors"),
                        StringStruct("FileDescription", "Desktop Agent"),
                        StringStruct("FileVersion", app_version),
                        StringStruct("InternalName", "DesktopAgent"),
                        StringStruct("OriginalFilename", "DesktopAgent.exe"),
                        StringStruct("ProductName", "Desktop Agent"),
                        StringStruct("ProductVersion", app_version),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

analysis = Analysis(
    [str(package_root / "main.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=copy_metadata("desktop-agent") + [
        (str(package_root / "ui"), "desktop_agent/ui"),
        (str(package_root / "resources"), "desktop_agent/resources"),
    ],
    hiddenimports=["qasync", "win32api", "win32con", "win32job"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.Qt3DCore",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DQuick",
        "PySide6.Qt3DQuickAnimation",
        "PySide6.Qt3DQuickExtras",
        "PySide6.Qt3DQuickInput",
        "PySide6.Qt3DQuickRender",
        "PySide6.Qt3DQuickScene2D",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtPdf",
        "PySide6.QtPositioning",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtVirtualKeyboard",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebSockets",
        "PySide6.QtWebView",
    ],
    noarchive=False,
)

excluded_qt_modules = {
    "3d",
    "quick3d",
    "quickdialogs",
    "quickeffects",
    "quickparticles",
    "quicktest",
    "quicktimeline",
    "quickvectorimage",
    "quickcontrols2fluentwinui3",
    "quickcontrols2fusion",
    "quickcontrols2imagine",
    "quickcontrols2material",
    "quickcontrols2universal",
    "quickcontrols2windows",
    "labs",
    "spatialaudio",
    "statemachine",
    "svg",
    "shadertools",
    "charts",
    "datavisualization",
    "graphs",
    "location",
    "multimedia",
    "pdf",
    "positioning",
    "remoteobjects",
    "scxml",
    "sensors",
    "test",
    "texttospeech",
    "virtualkeyboard",
    "webchannel",
    "webengine",
    "websockets",
    "webview",
}
allowed_qml_modules = {"QtCore", "QtQml", "QtQuick"}


def keep_qt_entry(entry):
    source_path = Path(entry[0])
    source_parts = [part.lower() for part in source_path.parts]
    source_name = source_path.name.lower()
    if "pyside6" in source_parts and "qml" in source_parts:
        qml_index = source_parts.index("qml")
        relative_parts = source_parts[qml_index + 1 :]
        if not relative_parts:
            return True
        module = relative_parts[0]
        if module not in {name.lower() for name in allowed_qml_modules}:
            return False
    if source_name.startswith("qt6"):
        stem = source_name.removeprefix("qt6").removesuffix(".dll")
        if any(stem.startswith(module) for module in excluded_qt_modules):
            return False
    return True


trimmed_binaries = [entry for entry in analysis.binaries if keep_qt_entry(entry)]
trimmed_datas = [entry for entry in analysis.datas if keep_qt_entry(entry)]
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    name="DesktopAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,
    icon=str(icon_path),
    exclude_binaries=True,
)

COLLECT(
    executable,
    trimmed_binaries,
    trimmed_datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=bundle_name,
)
