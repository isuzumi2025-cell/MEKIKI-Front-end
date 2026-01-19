# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for MEKIKI OCR

業務配布用ビルド設定:
- Windows EXE生成
- 依存関係の自動バンドル
- アイコン、リソースの埋め込み
- 起動の高速化（--onefile モード）

Usage:
    pyinstaller mekiki.spec
"""

import sys
import os
from pathlib import Path

# プロジェクトルート
project_root = Path(os.getcwd())

# バージョン情報
version = "1.0.0"
app_name = "MEKIKI"

# アイコンファイル（存在する場合）
icon_path = project_root / "assets" / "icon.ico"
icon = str(icon_path) if icon_path.exists() else None

# ===== Hidden Imports（動的インポート対応） =====
hidden_imports = [
    # Core modules
    'app.core.exceptions',
    'app.core.logger',
    'app.core.error_handler',
    'app.config.api_manager',

    # OCR engines
    'app.sdk.ocr',
    'app.core.gemini_ocr',
    'app.core.llm_client',

    # GUI modules
    'app.gui.main_window_v2',
    'app.gui.windows.advanced_comparison_view',
    'app.gui.panels.spreadsheet_panel',
    'app.gui.dialogs.settings_dialog',
    'app.gui.dialogs.error_dialog',
    'app.gui.sdk.keyboard_manager',
    'app.gui.sdk.scroll_sync',

    # SDK modules
    'app.sdk.selection.manager',
    'app.sdk.canvas.transform',
    'app.utils.image_cache',
    'app.utils.pdf_loader',

    # Third-party hidden imports
    'PIL._tkinter_finder',
    'google.generativeai',
    'google.cloud.vision',
    'customtkinter',
    'openpyxl',
    'playwright',
    'PyMuPDF',
    'fitz',  # PyMuPDF internal name
    'cv2',
    'numpy',
]

# ===== Data Files（設定、アセット） =====
datas = [
    # 設定ファイル
    (str(project_root / 'config'), 'config'),

    # アセット（存在する場合）
    # (str(project_root / 'assets'), 'assets'),
]

# CustomTkinterのテーマファイル
import customtkinter
ctk_path = Path(customtkinter.__file__).parent
datas.append((str(ctk_path / 'assets'), 'customtkinter/assets'))

# ===== Binary Files（除外設定） =====
binaries = []

# ===== Analysis =====
a = Analysis(
    ['app/main.py'],  # エントリーポイント
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不要なモジュールを除外（サイズ削減）
        'tkinter.test',
        'unittest',
        'test',
        'distutils',
        'setuptools',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ===== PYZ（Python Archive） =====
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None
)

# ===== EXE（実行ファイル） =====
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,  # Trueにするとデバッグ情報付きでビルド
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # UPX圧縮（サイズ削減、Falseで高速起動）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI版なのでコンソールなし（デバッグ時はTrue）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version_file=None,  # バージョン情報ファイル（別途作成可能）
)

# ===== Optional: COLLECT（--onedir モード用） =====
# --onefile ではなく --onedir でビルドする場合は以下のコメントアウトを解除
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name=app_name,
# )
