# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Parallax Studio — macOS Apple Silicon (.app + .dmg)
# Run via:  ./build_macos.sh   (or: pyinstaller parallax_studio.spec)

from PyInstaller.utils.hooks import collect_data_files

# imageio_ffmpeg bundles its own ARM64 ffmpeg binary; collect it explicitly
# so it lands at {_MEIPASS}/imageio_ffmpeg/binaries/ where the library expects it.
imageio_ffmpeg_datas = collect_data_files("imageio_ffmpeg")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=imageio_ffmpeg_datas,
    hiddenimports=[
        # OpenCV — compiled extension, not always auto-detected
        "cv2",
        # imageio backends
        "imageio.plugins.ffmpeg",
        "imageio_ffmpeg",
        # Pillow image plugins used by export
        "PIL.Image",
        "PIL.PngImagePlugin",
        "PIL.JpegImagePlugin",
        "PIL.WebPImagePlugin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["build_hooks/rthook_fix_ffmpeg.py"],
    excludes=[
        # Unused Qt modules — keep the bundle lean
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtHttpServer",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtNfc",
        "PySide6.QtPdf",
        "PySide6.QtPositioning",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialBus",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtStateMachine",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtXml",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Parallax Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX can break signed binaries on macOS — leave off
    console=False,       # GUI app — no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Parallax Studio",
)

app = BUNDLE(
    coll,
    name="Parallax Studio.app",
    icon=None,           # Phase 9: add assets/icons/app.icns
    bundle_identifier="com.longweekendlabs.parallaxstudio",
    version="0.1.1",
    info_plist={
        "CFBundleDisplayName": "Parallax Studio",
        "CFBundleVersion": "0.1.1",
        "CFBundleShortVersionString": "0.1.1",
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,   # supports dark mode
        "LSMinimumSystemVersion": "12.0",          # macOS Monterey+
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Parallax Studio Project",
                "CFBundleTypeExtensions": ["parlx"],
                "CFBundleTypeRole": "Editor",
            }
        ],
    },
)
