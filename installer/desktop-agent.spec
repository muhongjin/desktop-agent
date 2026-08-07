from pathlib import Path


project_root = Path(SPECPATH).parent
source_root = project_root / "src"
package_root = source_root / "desktop_agent"

analysis = Analysis(
    [str(package_root / "main.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=[
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
    exclude_binaries=True,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DesktopAgent",
)
