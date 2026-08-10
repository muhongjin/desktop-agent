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
    excludes=[],
    noarchive=False,
)
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
    exclude_binaries=True,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=bundle_name,
)
