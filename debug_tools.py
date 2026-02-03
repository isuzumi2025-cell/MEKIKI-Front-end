"""
デバッグコマンド集
問題切り分けのための便利関数
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))


def check_env():
    """環境変数確認"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 50)
    print("🔑 API Keys Check")
    print("=" * 50)
    
    keys = {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
    }
    
    for name, value in keys.items():
        if value:
            masked = value[:8] + "..." if len(value) > 8 else value
            print(f"  ✅ {name}: {masked}")
        else:
            print(f"  ❌ {name}: Not set")


def check_ocr_engine():
    """OCRエンジン確認"""
    print("\n" + "=" * 50)
    print("🔍 OCR Engine Check")
    print("=" * 50)
    
    try:
        from app.core.engine_cloud import CloudOCREngine
        engine = CloudOCREngine()
        print("  ✅ CloudOCREngine: OK")
    except Exception as e:
        print(f"  ❌ CloudOCREngine: {e}")
    
    try:
        from app.core.hybrid_ocr import HybridOCREngine
        engine = HybridOCREngine()
        status = "OK" if engine._is_initialized else "Not initialized"
        print(f"  {'✅' if engine._is_initialized else '⚠️'} HybridOCREngine: {status}")
    except Exception as e:
        print(f"  ❌ HybridOCREngine: {e}")


def check_clawdbot():
    """Clawdbot接続確認"""
    print("\n" + "=" * 50)
    print("🤖 Clawdbot Check")
    print("=" * 50)
    
    try:
        from app.sdk.notification.clawdbot_client import get_clawdbot_client
        client = get_clawdbot_client()
        if client.is_available():
            print("  ✅ Clawdbot: Available")
        else:
            print("  ⚠️ Clawdbot: Not available (no token)")
    except Exception as e:
        print(f"  ❌ Clawdbot: {e}")


def list_fixtures():
    """利用可能なFixture一覧"""
    print("\n" + "=" * 50)
    print("📦 Available Fixtures")
    print("=" * 50)
    
    try:
        from config.fixture_manager import list_fixtures as lf
        fixtures = lf()
        if fixtures:
            for f in fixtures:
                print(f"  - {f}")
        else:
            print("  (no fixtures)")
    except Exception as e:
        print(f"  Error: {e}")


def clear_cache():
    """キャッシュクリア"""
    print("\n" + "=" * 50)
    print("🗑️ Clear Cache")
    print("=" * 50)
    
    import shutil
    root = Path(__file__).parent
    count = 0
    for cache in root.rglob("__pycache__"):
        if ".venv" not in str(cache):
            shutil.rmtree(cache, ignore_errors=True)
            count += 1
    print(f"  Cleared {count} __pycache__ directories")


def full_check():
    """全チェック実行"""
    check_env()
    check_ocr_engine()
    check_clawdbot()
    list_fixtures()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MEKIKI Debug Commands")
    parser.add_argument("command", nargs="?", default="all",
                       choices=["all", "env", "ocr", "clawdbot", "fixtures", "cache"])
    args = parser.parse_args()
    
    if args.command == "all":
        full_check()
    elif args.command == "env":
        check_env()
    elif args.command == "ocr":
        check_ocr_engine()
    elif args.command == "clawdbot":
        check_clawdbot()
    elif args.command == "fixtures":
        list_fixtures()
    elif args.command == "cache":
        clear_cache()
