"""
OCR Accuracy Benchmark
3つのOCR方式を比較: Cloud Vision / Gemini / Hybrid
"""
import sys
import os
from pathlib import Path
from PIL import Image
import time

# パス設定
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from config import Config
Config.load_keys()

# ======================================
# 1. Cloud Vision OCR
# ======================================
def run_cloud_vision_ocr(image_path: str) -> dict:
    """Cloud Vision APIでOCR実行"""
    print("\n" + "="*60)
    print("📷 [1/3] Cloud Vision API OCR")
    print("="*60)
    
    try:
        from app.core.ocr_engine import OCREngine
        engine = OCREngine()
        
        start = time.time()
        result = engine.detect_document_text(image_path)
        elapsed = time.time() - start
        
        if result:
            full_text = result.get('full_text', '')
            blocks = result.get('blocks', [])
            print(f"✅ 完了: {len(blocks)} ブロック検出 ({elapsed:.2f}秒)")
            print(f"📝 文字数: {len(full_text)}")
            return {
                "method": "Cloud Vision",
                "text": full_text,
                "blocks": len(blocks),
                "chars": len(full_text),
                "time": elapsed,
                "success": True
            }
        else:
            print("❌ 結果なし")
            return {"method": "Cloud Vision", "success": False, "error": "No result"}
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        return {"method": "Cloud Vision", "success": False, "error": str(e)}

# ======================================
# 2. Gemini OCR (単体)
# ======================================
def run_gemini_ocr(image_path: str) -> dict:
    """Gemini単体でOCR実行"""
    print("\n" + "="*60)
    print("🤖 [2/3] Gemini Multimodal OCR")
    print("="*60)
    
    try:
        from app.core.gemini_ocr import GeminiOCREngine
        engine = GeminiOCREngine()
        
        start = time.time()
        result = engine.detect_document_text(image_path)
        elapsed = time.time() - start
        
        if result:
            full_text = result.get('full_text', '')
            blocks = result.get('blocks', [])
            print(f"✅ 完了: {len(blocks)} ブロック検出 ({elapsed:.2f}秒)")
            print(f"📝 文字数: {len(full_text)}")
            return {
                "method": "Gemini",
                "text": full_text,
                "blocks": len(blocks),
                "chars": len(full_text),
                "time": elapsed,
                "success": True
            }
        else:
            print("❌ 結果なし")
            return {"method": "Gemini", "success": False, "error": "No result"}
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return {"method": "Gemini", "success": False, "error": str(e)}

# ======================================
# 3. Hybrid OCR (Cloud Vision + Gemini補正)
# ======================================
def run_hybrid_ocr(image_path: str) -> dict:
    """Hybrid: Cloud Vision → Gemini補正"""
    print("\n" + "="*60)
    print("🔥 [3/3] Hybrid OCR (Vision + Gemini)")
    print("="*60)
    
    try:
        from app.core.ocr_engine import OCREngine
        from app.core.llm_client import LLMClient
        
        # Step 1: Cloud Vision で基本OCR
        print("  [Step 1] Cloud Vision OCR...")
        vision_engine = OCREngine()
        start = time.time()
        vision_result = vision_engine.detect_document_text(image_path)
        
        if not vision_result:
            return {"method": "Hybrid", "success": False, "error": "Vision OCR failed"}
        
        raw_text = vision_result.get('full_text', '')
        print(f"    → {len(raw_text)} 文字取得")
        
        # Step 2: Gemini で補正
        print("  [Step 2] Gemini 補正...")
        llm = LLMClient(model_name="gemini-2.0-flash")
        
        correction_prompt = f"""以下のOCR結果を校正してください。
誤認識を修正し、正しい日本語テキストを出力してください。
段落構造を維持し、明らかな誤字脱字を修正してください。
補正後のテキストのみを出力してください。

--- OCR結果 ---
{raw_text[:3000]}
"""
        
        corrected_text = llm.generate_content(correction_prompt)
        elapsed = time.time() - start
        
        if corrected_text:
            print(f"✅ 完了: 補正後 {len(corrected_text)} 文字 ({elapsed:.2f}秒)")
            return {
                "method": "Hybrid",
                "text": corrected_text,
                "original_chars": len(raw_text),
                "corrected_chars": len(corrected_text),
                "time": elapsed,
                "success": True
            }
        else:
            return {"method": "Hybrid", "success": False, "error": "Gemini correction failed"}
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return {"method": "Hybrid", "success": False, "error": str(e)}

# ======================================
# 比較レポート生成
# ======================================
def generate_report(results: list, output_path: str):
    """比較レポートを生成"""
    print("\n" + "="*60)
    print("📊 比較レポート")
    print("="*60)
    
    report = []
    report.append("# OCR Accuracy Benchmark Report\n")
    report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    report.append("## Summary\n\n")
    report.append("| Method | Status | Characters | Blocks | Time (s) |\n")
    report.append("|--------|--------|------------|--------|----------|\n")
    
    for r in results:
        status = "✅" if r.get("success") else "❌"
        chars = r.get("chars", r.get("corrected_chars", "-"))
        blocks = r.get("blocks", "-")
        time_s = f"{r.get('time', 0):.2f}" if r.get("time") else "-"
        report.append(f"| {r['method']} | {status} | {chars} | {blocks} | {time_s} |\n")
    
    report.append("\n## Extracted Text Samples\n\n")
    
    for r in results:
        report.append(f"### {r['method']}\n\n")
        if r.get("success"):
            text = r.get("text", "")[:500]
            report.append(f"```\n{text}\n```\n\n")
        else:
            report.append(f"Error: {r.get('error', 'Unknown')}\n\n")
    
    # ファイル出力
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(report)
    
    print(f"📄 レポート保存: {output_path}")
    
    # コンソールにもサマリー表示
    for r in results:
        status = "✅" if r.get("success") else "❌"
        chars = r.get("chars", r.get("corrected_chars", "-"))
        print(f"  {status} {r['method']}: {chars} 文字")

# ======================================
# メイン
# ======================================
def main():
    print("="*60)
    print("🔬 OCR Accuracy Benchmark")
    print("="*60)
    
    # テスト画像
    test_image = root_dir / "test.jpg"
    
    if not test_image.exists():
        print(f"❌ テスト画像が見つかりません: {test_image}")
        print("   test.jpg を配置してください")
        return
    
    print(f"📷 テスト画像: {test_image}")
    
    results = []
    
    # 1. Cloud Vision
    results.append(run_cloud_vision_ocr(str(test_image)))
    
    # 2. Gemini
    results.append(run_gemini_ocr(str(test_image)))
    
    # 3. Hybrid
    results.append(run_hybrid_ocr(str(test_image)))
    
    # レポート生成
    report_path = root_dir / "ocr_benchmark_report.md"
    generate_report(results, str(report_path))
    
    print("\n" + "="*60)
    print("✅ ベンチマーク完了!")
    print("="*60)

if __name__ == "__main__":
    main()
