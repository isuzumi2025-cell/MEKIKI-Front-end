"""
最小再現テスト
問題を素早く特定するための軽量テスト
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

def test_hybrid_ocr_init():
    """HybridOCR初期化テスト"""
    print("\n[TEST] HybridOCR Init")
    try:
        from app.core.hybrid_ocr import HybridOCREngine
        engine = HybridOCREngine()
        if engine._is_initialized:
            print("  ✅ PASS: HybridOCR initialized")
            return True
        else:
            print("  ❌ FAIL: HybridOCR not initialized")
            return False
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

def test_cloud_ocr_engine():
    """CloudOCREngine テスト"""
    print("\n[TEST] CloudOCREngine")
    try:
        from app.core.engine_cloud import CloudOCREngine
        engine = CloudOCREngine()
        print("  ✅ PASS: CloudOCREngine created")
        return True
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

def test_ocr_on_test_image():
    """テスト画像でOCR実行"""
    print("\n[TEST] OCR on test.jpg")
    try:
        from PIL import Image
        from app.core.engine_cloud import CloudOCREngine
        
        img_path = Path(__file__).parent / "test.jpg"
        if not img_path.exists():
            print(f"  ⚠️ SKIP: {img_path} not found")
            return None
        
        img = Image.open(img_path)
        engine = CloudOCREngine()
        clusters, words = engine.extract_text(img)
        
        print(f"  Clusters: {len(clusters)}")
        print(f"  Words: {len(words)}")
        
        if len(clusters) > 0:
            print("  ✅ PASS: OCR returned results")
            return True
        else:
            print("  ❌ FAIL: No clusters detected")
            return False
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_env_keys():
    """環境変数・APIキーテスト"""
    print("\n[TEST] API Keys")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    gemini = os.getenv("GEMINI_API_KEY", "")
    openai = os.getenv("OPENAI_API_KEY", "")
    
    results = []
    
    if gemini.startswith("AIza"):
        print("  ✅ GEMINI_API_KEY: OK")
        results.append(True)
    else:
        print("  ❌ GEMINI_API_KEY: Invalid or missing")
        results.append(False)
    
    if openai.startswith("sk-"):
        print("  ✅ OPENAI_API_KEY: OK")
        results.append(True)
    else:
        print("  ⚠️ OPENAI_API_KEY: Not set (optional)")
        results.append(None)
    
    return all(r for r in results if r is not None)

def run_all_tests():
    """すべてのテストを実行"""
    print("=" * 50)
    print("🧪 MEKIKI Minimal Tests")
    print("=" * 50)
    
    results = [
        ("API Keys", test_env_keys()),
        ("CloudOCREngine", test_cloud_ocr_engine()),
        ("HybridOCR Init", test_hybrid_ocr_init()),
        ("OCR on test.jpg", test_ocr_on_test_image()),
    ]
    
    print("\n" + "=" * 50)
    print("📊 Results")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    for name, result in results:
        status = "✅" if result is True else "❌" if result is False else "⚠️"
        print(f"  {status} {name}")
    
    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
