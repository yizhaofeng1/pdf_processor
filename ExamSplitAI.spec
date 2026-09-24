# -*- mode: python ; coding: utf-8 -*-
"""ExamSplit AI PyInstaller Specification File
Cross-platform packaging for Windows and Linux.
"""

import sys
import os
from pathlib import Path

block_cipher = None

BASE_DIR = Path(os.path.abspath(SPECPATH))

# Collect data assets
datas = [
    (str(BASE_DIR / 'prompts'), 'prompts'),
    (str(BASE_DIR / 'schemas'), 'schemas'),
    (str(BASE_DIR / 'resources'), 'resources'),
]

# Ensure PySide6 platform plugins and runtime DLLs are bundled
try:
    import PySide6
    pyside_path = Path(PySide6.__file__).resolve().parent
    plugins_path = pyside_path / 'plugins'
    if plugins_path.exists():
        for plugin_name in ['platforms', 'styles', 'imageformats', 'iconengines', 'tls']:
            p_sub = plugins_path / plugin_name
            if p_sub.exists():
                datas.append((str(p_sub), f'PySide6/plugins/{plugin_name}'))
                datas.append((str(p_sub), f'plugins/{plugin_name}'))
                if plugin_name == 'platforms':
                    datas.append((str(p_sub), 'platforms'))

    if sys.platform.startswith('win'):
        for dll_name in ['opengl32sw.dll', 'd3dcompiler_47.dll']:
            candidate = pyside_path / dll_name
            if candidate.exists():
                datas.append((str(candidate), 'PySide6'))
                datas.append((str(candidate), '.'))
except Exception as e:
    print(f"[Warning] Failed collecting PySide6 plugins: {e}")

# Hidden imports for PySide6, PyMuPDF, Pydantic v2, and Cryptography
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'pymupdf',
    'fitz',
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.hashes',
    'httpx',
    'pydantic',
    'pydantic_core',
    'dotenv',
    'sqlite3',
    'app.experimental',
    'app.experimental.local_ai',
    'app.experimental.local_ai.config',
    'app.experimental.local_ai.types',
    'app.experimental.local_ai.local_vlm',
    'app.experimental.local_ai.ocr_provider',
    'app.experimental.local_ai.layout_provider',
    'app.experimental.local_detection',
    'app.experimental.local_detection.reading_order',
    'app.experimental.local_detection.marker_detector',
    'app.experimental.local_detection.candidate_builder',
    'app.experimental.local_detection.boundary_resolver',
    'app.experimental.local_detection.confidence_router',
    'app.experimental.local_detection.cross_page_resolver',
    'app.experimental.local_recognition',
    'app.experimental.local_recognition.service',
    'app.experimental.local_recognition.ui',
]

# Platform-specific icon selection
if sys.platform.startswith('win'):
    app_icon = str(BASE_DIR / 'resources' / 'icon.ico')
else:
    app_icon = str(BASE_DIR / 'resources' / 'icon.png')

# Collect essential binary runtime DLLs on Windows (e.g. Conda Library/bin: libexpat, sqlite3, etc.)
binaries = []
if sys.platform.startswith('win'):
    conda_lib_bin = Path(sys.prefix) / 'Library' / 'bin'
    if conda_lib_bin.exists():
        for dll in conda_lib_bin.glob('*.dll'):
            binaries.append((str(dll), '.'))

a = Analysis(
    ['run_app.py'],
    pathex=[str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'IPython', 'PyQt5', 'PyQt6'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

# Build standalone folder distribution (fast startup, optimal compatibility)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ExamSplitAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ExamSplitAI',
)
