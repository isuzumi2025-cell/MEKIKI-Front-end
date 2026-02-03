"""
開発専用ランチャー
- 自動キャッシュクリア
- デバッグモード対応
- ログ設定統合
- Fixture読み込み対応
"""
import os
import sys
import shutil
import glob
import subprocess
from pathlib import Path

# プロジェクトルート
ROOT = Path(__file__).parent

def clear_pycache():
    """すべての__pycache__を削除"""
    count = 0
    for cache_dir in ROOT.rglob("__pycache__"):
        if ".venv" not in str(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
            count += 1
    print(f"🗑️ Cleared {count} __pycache__ directories")

def clear_pyc():
    """すべての.pycファイルを削除"""
    count = 0
    for pyc_file in ROOT.rglob("*.pyc"):
        if ".venv" not in str(pyc_file):
            pyc_file.unlink(missing_ok=True)
            count += 1
    print(f"🗑️ Cleared {count} .pyc files")

def set_debug_env():
    """デバッグ用環境変数を設定"""
    os.environ["MEKIKI_DEBUG"] = "1"
    os.environ["MEKIKI_SKIP_GEMINI_CORRECTION"] = "1"  # Gemini補正をスキップ
    print("🐛 Debug mode enabled (Gemini correction skipped)")

def setup_logging():
    """ログ設定"""
    try:
        from config.logging_config import init_logging
        init_logging()
    except ImportError:
        print("⚠️ Logging config not found, using default")

def main():
    print("=" * 50)
    print("🚀 MEKIKI Dev Launcher v2.0")
    print("=" * 50)
    
    # 1. キャッシュクリア
    clear_pycache()
    clear_pyc()
    
    # 2. デバッグモード設定
    if "--debug" in sys.argv or "-d" in sys.argv:
        set_debug_env()
    
    # 3. Fixture使用
    if "--fixture" in sys.argv or "-f" in sys.argv:
        os.environ["MEKIKI_USE_FIXTURE"] = "1"
        print("📦 Fixture mode enabled")
    
    # 4. ログ設定
    setup_logging()
    
    # 5. 環境チェック（--checkオプション）
    if "--check" in sys.argv or "-c" in sys.argv:
        print("\n🔍 Running environment check...")
        from debug_tools import full_check
        full_check()
        return
    
    # 6. アプリ起動
    print("\n🎯 Starting unified app...")
    print("=" * 50)
    
    # run_unified.pyを実行
    exec(open(ROOT / "run_unified.py").read())

if __name__ == "__main__":
    main()
