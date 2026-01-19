"""
OCR精度テストスクリプト
前処理有無による精度比較

Usage: py -3 verify/test_ocr_accuracy.py <image_path>
"""
import sys
import os
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from PIL import Image
import time

def test_ocr_with_preprocessing(image_path: str):
    """前処理有無でOCR精度を比較"""
    
    print("=" * 60)
    print("OCR精度テスト")
    print("=" * 60)
    
    # 画像読み込み
    if not Path(image_path).exists():
        print(f"❌ 画像が見つかりません: {image_path}")
        return
    
    original_image = Image.open(image_path)
    print(f"\n📷 入力画像: {image_path}")
    print(f"   サイズ: {original_image.size}")
    print(f"   モード: {original_image.mode}")
    
    # OCRエンジン確認
    try:
        from app.core.ocr_engine import OCREngine
        ocr = OCREngine()
        if ocr.initialize():
            print("\n✅ OCRエンジン: Google Cloud Vision API")
        else:
            print("\n⚠️ Vision API初期化失敗")
            ocr = None
    except Exception as e:
        print(f"\n⚠️ OCRエンジンロード失敗: {e}")
        print("   Tesseractでテスト...")
        ocr = None
    
    # 前処理
    from app.core.image_preprocessor import ImagePreprocessor
    preprocessor = ImagePreprocessor(
        scale_factor=4.0,
        gamma=0.5,
        enable_binarize=True
    )
    
    # ========== テスト1: 前処理なし ==========
    print("\n" + "-" * 40)
    print("[1] 前処理なし")
    print("-" * 40)
    
    start = time.time()
    if ocr:
        result1 = ocr.detect_document_text(image_path)
        text1 = result1.get("text", "") if result1 else ""
    else:
        # Tesseract fallback
        try:
            import pytesseract
            text1 = pytesseract.image_to_string(original_image, lang='jpn')
        except:
            text1 = "(Tesseract not available)"

    
    time1 = time.time() - start
    print(f"⏱️  処理時間: {time1:.2f}秒")
    print(f"📝 抽出テキスト ({len(text1)}文字):")
    print(text1[:500] if text1 else "(なし)")
    
    # ========== テスト2: 前処理あり ==========
    print("\n" + "-" * 40)
    print("[2] 前処理あり (4倍拡大 + ノイズ除去 + γ補正)")
    print("-" * 40)
    
    # 前処理適用
    preprocessed = preprocessor.process(original_image)
    print(f"   前処理後サイズ: {preprocessed.size}")
    
    # 一時ファイルに保存
    temp_path = Path("storage/temp_preprocessed.png")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    preprocessed.save(str(temp_path))
    
    start = time.time()
    if ocr:
        result2 = ocr.detect_document_text(str(temp_path))
        text2 = result2.get("text", "") if result2 else ""
    else:
        try:
            import pytesseract
            text2 = pytesseract.image_to_string(preprocessed, lang='jpn')
        except:
            text2 = "(Tesseract not available)"
    
    time2 = time.time() - start
    print(f"⏱️  処理時間: {time2:.2f}秒")
    print(f"📝 抽出テキスト ({len(text2)}文字):")
    print(text2[:500] if text2 else "(なし)")
    
    # ========== 比較 ==========
    print("\n" + "=" * 60)
    print("比較結果")
    print("=" * 60)
    
    diff_chars = abs(len(text2) - len(text1))
    print(f"📊 文字数差: {diff_chars} ({len(text1)} → {len(text2)})")
    
    if len(text2) > len(text1):
        print(f"   → 前処理により {len(text2) - len(text1)} 文字多く抽出")
    elif len(text2) < len(text1):
        print(f"   → 前処理により {len(text1) - len(text2)} 文字減少")
    else:
        print("   → 文字数同じ")
    
    # フィールド抽出比較
    from app.core.fields_extract import extract_fields
    
    fields1 = extract_fields(text1)
    fields2 = extract_fields(text2)
    
    print(f"\n🔢 フィールド抽出数:")
    print(f"   前処理なし: {len(fields1)}")
    print(f"   前処理あり: {len(fields2)}")
    
    if fields2:
        print("\n   抽出されたフィールド (前処理あり):")
        for f in fields2[:10]:
            print(f"     {f['type']:12} | {f['raw']}")
    
    print("\n" + "=" * 60)
    print("✅ テスト完了")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # デフォルトでテスト画像を探す
        test_images = list(Path("storage").rglob("*.png")) + list(Path("storage").rglob("*.jpg"))
        if test_images:
            print(f"引数なし。最初に見つかった画像でテスト: {test_images[0]}")
            test_ocr_with_preprocessing(str(test_images[0]))
        else:
            print("Usage: py -3 verify/test_ocr_accuracy.py <image_path>")
            print("\nテスト用画像をドラッグ&ドロップするか、パスを指定してください。")
    else:
        test_ocr_with_preprocessing(sys.argv[1])
