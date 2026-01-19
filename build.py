"""
MEKIKI OCR Build Script

業務配布用ビルド自動化スクリプト:
- 環境チェック
- 依存関係確認
- PyInstallerビルド実行
- ビルド検証
- パッケージング

Usage:
    python build.py
    python build.py --clean  # クリーンビルド
    python build.py --debug  # デバッグビルド
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime


# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "mekiki.spec"


class Colors:
    """ANSI カラーコード"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_step(message: str):
    """ステップ表示"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}>>> {message}{Colors.END}")


def print_success(message: str):
    """成功メッセージ"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def print_warning(message: str):
    """警告メッセージ"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")


def print_error(message: str):
    """エラーメッセージ"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def check_environment():
    """環境チェック"""
    print_step("環境チェック")

    # Python バージョン確認
    python_version = sys.version_info
    print(f"  Python: {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print_error("Python 3.8 以上が必要です")
        return False

    # 必須パッケージ確認
    required_packages = [
        'PyInstaller',
        'customtkinter',
        'Pillow',
        'PyMuPDF',
        'numpy',
        'openpyxl',
    ]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_').lower())
            print_success(f"{package} インストール済み")
        except ImportError:
            missing_packages.append(package)
            print_error(f"{package} がインストールされていません")

    if missing_packages:
        print_error(f"以下のパッケージをインストールしてください:")
        print(f"  pip install {' '.join(missing_packages)}")
        return False

    # 仮想環境チェック
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_success("仮想環境で実行中")
    else:
        print_warning("仮想環境ではありません（推奨）")

    return True


def clean_build():
    """ビルドディレクトリクリーンアップ"""
    print_step("クリーンアップ")

    dirs_to_clean = [DIST_DIR, BUILD_DIR]

    for dir_path in dirs_to_clean:
        if dir_path.exists():
            print(f"  削除: {dir_path}")
            shutil.rmtree(dir_path)
            print_success(f"{dir_path.name} 削除完了")
        else:
            print(f"  スキップ: {dir_path} (存在しません)")


def run_pyinstaller(debug: bool = False):
    """PyInstaller 実行"""
    print_step("PyInstaller ビルド")

    if not SPEC_FILE.exists():
        print_error(f"Specファイルが見つかりません: {SPEC_FILE}")
        return False

    # PyInstallerコマンド構築
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        str(SPEC_FILE),
        "--noconfirm",  # 確認なしで上書き
    ]

    if debug:
        cmd.append("--debug")
        cmd.append("all")

    print(f"  コマンド: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=False  # ログをリアルタイム表示
        )

        print_success("PyInstaller ビルド成功")
        return True

    except subprocess.CalledProcessError as e:
        print_error(f"PyInstaller ビルド失敗: {e}")
        return False


def verify_build():
    """ビルド検証"""
    print_step("ビルド検証")

    exe_path = DIST_DIR / "MEKIKI.exe"

    if not exe_path.exists():
        print_error(f"実行ファイルが見つかりません: {exe_path}")
        return False

    # ファイルサイズ確認
    file_size = exe_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    print(f"  実行ファイル: {exe_path}")
    print(f"  サイズ: {file_size_mb:.2f} MB")

    if file_size_mb > 500:
        print_warning(f"ファイルサイズが大きいです（{file_size_mb:.2f} MB）")
    else:
        print_success(f"ファイルサイズ適正（{file_size_mb:.2f} MB）")

    return True


def create_distribution():
    """配布パッケージ作成"""
    print_step("配布パッケージ作成")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"MEKIKI_v1.0.0_{timestamp}"
    package_dir = DIST_DIR / package_name

    try:
        # パッケージディレクトリ作成
        package_dir.mkdir(exist_ok=True)

        # 実行ファイルコピー
        exe_path = DIST_DIR / "MEKIKI.exe"
        if exe_path.exists():
            shutil.copy2(exe_path, package_dir / "MEKIKI.exe")
            print_success("実行ファイルコピー完了")

        # README作成
        readme_content = """# MEKIKI OCR - 業務配布版

## インストール方法

1. MEKIKI.exe をダブルクリックして起動

## 初回起動時の設定

1. 設定 → API設定 を開く
2. 使用するAPIキーを入力
3. 保存

## 使用方法

1. WebページURLまたはPDFファイルを読み込み
2. OCRボタンで文字認識を実行
3. 結果を確認して必要に応じてExcelエクスポート

## サポート

エラーが発生した場合は、以下のログファイルを確認してください:
- logs/mekiki_error.log

ログファイルをサポートに送信する場合:
1. アプリ内で「レポート送信」ボタンをクリック
2. 生成されたZIPファイルを添付

## バージョン情報

- バージョン: 1.0.0
- ビルド日時: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """

© 2026 MEKIKI Project
"""

        readme_path = package_dir / "README.txt"
        readme_path.write_text(readme_content, encoding='utf-8')
        print_success("README作成完了")

        # ZIPで圧縮
        zip_path = DIST_DIR / f"{package_name}.zip"
        shutil.make_archive(
            str(DIST_DIR / package_name),
            'zip',
            package_dir
        )

        print_success(f"配布パッケージ作成完了: {zip_path}")

        # パッケージサイズ表示
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"  パッケージサイズ: {zip_size_mb:.2f} MB")

        return True

    except Exception as e:
        print_error(f"配布パッケージ作成失敗: {e}")
        return False


def main():
    """メインビルドプロセス"""
    parser = argparse.ArgumentParser(description='MEKIKI OCR Build Script')
    parser.add_argument('--clean', action='store_true', help='クリーンビルド')
    parser.add_argument('--debug', action='store_true', help='デバッグビルド')
    parser.add_argument('--skip-verify', action='store_true', help='検証スキップ')
    parser.add_argument('--skip-package', action='store_true', help='パッケージング スキップ')

    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}MEKIKI OCR Build Script{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")

    # 1. 環境チェック
    if not check_environment():
        print_error("環境チェック失敗")
        return 1

    # 2. クリーンアップ（オプション）
    if args.clean:
        clean_build()

    # 3. PyInstaller実行
    if not run_pyinstaller(debug=args.debug):
        print_error("ビルド失敗")
        return 1

    # 4. ビルド検証
    if not args.skip_verify:
        if not verify_build():
            print_error("検証失敗")
            return 1

    # 5. 配布パッケージ作成
    if not args.skip_package:
        if not create_distribution():
            print_error("パッケージング失敗")
            return 1

    # 完了
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}✅ ビルド成功!{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'=' * 60}{Colors.END}")
    print(f"\n配布ファイル: {DIST_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
