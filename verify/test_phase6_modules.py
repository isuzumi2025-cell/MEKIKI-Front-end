"""
Phase 6 モジュール検証スクリプト
VisualAnalyzer, ClusteringEngine, TextMatcher, LiveCellSync の動作確認
"""
import sys
import os
from pathlib import Path

# OCRルートをパスに追加
OCR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(OCR_ROOT))
os.chdir(OCR_ROOT)

from PIL import Image


# テスト結果
results = []

def test_pass(name: str, detail: str = ""):
    print(f"✅ {name}" + (f" - {detail}" if detail else ""))
    results.append(("PASS", name))

def test_fail(name: str, error: str):
    print(f"❌ {name} - {error}")
    results.append(("FAIL", name))

# ============================
# 1. VisualAnalyzer テスト
# ============================
print("\n" + "="*50)
print("1. VisualAnalyzer テスト")
print("="*50)

try:
    from app.core.visual_analyzer import VisualAnalyzer, enhance_blocks_with_visual_info
    test_pass("VisualAnalyzer import")
except Exception as e:
    test_fail("VisualAnalyzer import", str(e))
    sys.exit(1)

# 画像読み込みテスト
test_image_path = Path("test.jpg")
if not test_image_path.exists():
    test_image_path = Path("reference data/2502_寺社_パンフ_07 (1)_ページ_1.jpg")

if test_image_path.exists():
    try:
        img = Image.open(test_image_path)
        analyzer = VisualAnalyzer()
        result = analyzer.analyze_image(img)
        
        # 結果検証
        assert "borders" in result, "borders missing"
        assert "color_blocks" in result, "color_blocks missing"
        assert "dominant_colors" in result, "dominant_colors missing"
        
        test_pass("VisualAnalyzer.analyze_image", 
                  f"borders={len(result['borders'])}, color_blocks={len(result['color_blocks'])}, colors={len(result['dominant_colors'])}")
        
        # 主要色表示
        print(f"   主要色: {[c['color'] for c in result['dominant_colors'][:3]]}")
        
    except Exception as e:
        test_fail("VisualAnalyzer.analyze_image", str(e))
else:
    test_fail("VisualAnalyzer.analyze_image", "テスト画像が見つかりません")

# ============================
# 2. ClusteringEngine テスト
# ============================
print("\n" + "="*50)
print("2. ClusteringEngine テスト")
print("="*50)

try:
    from app.core.engine_clustering import ClusteringEngine, VisualAwareClusteringEngine, BlockExtractor
    test_pass("ClusteringEngine import")
except Exception as e:
    test_fail("ClusteringEngine import", str(e))
    sys.exit(1)

# サンプルブロックでテスト
sample_blocks = [
    {"text": "見出し1", "rect": [100, 100, 300, 140], "center_x": 200, "width": 200, "font_size": 24},
    {"text": "本文テキスト", "rect": [100, 150, 350, 180], "center_x": 225, "width": 250, "font_size": 12},
    {"text": "追加行", "rect": [100, 190, 300, 220], "center_x": 200, "width": 200, "font_size": 12},
    {"text": "別セクション", "rect": [500, 100, 700, 140], "center_x": 600, "width": 200, "font_size": 18},
]

try:
    engine = ClusteringEngine()
    clusters = engine.cluster_from_blocks(sample_blocks)
    
    assert len(clusters) > 0, "クラスタが生成されていません"
    assert all("id" in c and "rect" in c and "text" in c for c in clusters), "クラスタ形式が不正"
    
    test_pass("ClusteringEngine.cluster_from_blocks", f"入力={len(sample_blocks)}ブロック → 出力={len(clusters)}クラスタ")
    
    # クラスタ内容表示
    for c in clusters:
        print(f"   クラスタ{c['id']}: {c['text'][:30]}...")
        
except Exception as e:
    test_fail("ClusteringEngine.cluster_from_blocks", str(e))

# VisualAwareClusteringEngine テスト
try:
    enhanced_blocks = [
        {"text": "ヘッダー", "rect": [100, 100, 300, 140], "background_color": "#FF6F00", "has_border": False, "font_size": 24},
        {"text": "本文", "rect": [100, 150, 350, 180], "background_color": "#FF6F00", "has_border": False, "font_size": 12},
        {"text": "別枠", "rect": [100, 250, 300, 280], "background_color": "#FFFFFF", "has_border": True, "font_size": 12},
    ]
    
    va_engine = VisualAwareClusteringEngine()
    va_clusters = va_engine.cluster_with_visual_info(enhanced_blocks)
    
    test_pass("VisualAwareClusteringEngine.cluster_with_visual_info", f"{len(va_clusters)}クラスタ")
    
except Exception as e:
    test_fail("VisualAwareClusteringEngine", str(e))

# ============================
# 3. TextMatcher テスト
# ============================
print("\n" + "="*50)
print("3. TextMatcher テスト")
print("="*50)

try:
    from app.core.text_matcher import TextMatcher
    test_pass("TextMatcher import")
except Exception as e:
    test_fail("TextMatcher import", str(e))
    sys.exit(1)

try:
    matcher = TextMatcher()
    
    # 類似度テスト
    text1 = "これはテストテキストです"
    text2 = "これはテストテキストです"
    score1 = matcher.calculate_similarity(text1, text2)
    assert score1 == 1.0, f"同一テキストが1.0にならない: {score1}"
    test_pass("TextMatcher 同一テキスト", f"score={score1:.2f}")
    
    text3 = "これは少し違うテキストです"
    score2 = matcher.calculate_similarity(text1, text3)
    assert 0 < score2 < 1, f"類似テキストのスコアが不正: {score2}"
    test_pass("TextMatcher 類似テキスト", f"score={score2:.2f}")
    
    text4 = "完全に異なる文章"
    score3 = matcher.calculate_similarity(text1, text4)
    test_pass("TextMatcher 異なるテキスト", f"score={score3:.2f}")
    
except Exception as e:
    test_fail("TextMatcher calculate_similarity", str(e))

# ============================
# 4. LiveCellSync テスト
# ============================
print("\n" + "="*50)
print("4. LiveCellSync テスト")
print("="*50)

try:
    from app.core.live_cell_sync import LiveCellSync, CellData
    test_pass("LiveCellSync import")
except Exception as e:
    test_fail("LiveCellSync import", str(e))
    sys.exit(1)

try:
    sync = LiveCellSync()
    
    # ID生成テスト
    web_id1 = sync.generate_web_id()
    web_id2 = sync.generate_web_id()
    assert web_id1 == "WEB-001", f"WebID形式が不正: {web_id1}"
    assert web_id2 == "WEB-002", f"WebID連番が不正: {web_id2}"
    test_pass("LiveCellSync.generate_web_id", f"{web_id1}, {web_id2}")
    
    sync.set_page(3)
    pdf_id = sync.generate_pdf_id()
    assert "PDF-P3" in pdf_id, f"PDFID形式が不正: {pdf_id}"
    test_pass("LiveCellSync.generate_pdf_id", pdf_id)
    
    # コールバックテスト
    callback_fired = []
    def on_update(cell, row):
        callback_fired.append((cell.unique_id, row))
    
    sync2 = LiveCellSync(on_cell_update=on_update)
    sync2.on_area_selected(1, "web", "テストテキスト")
    
    assert len(callback_fired) > 0, "コールバックが発火していません"
    test_pass("LiveCellSync コールバック発火", f"{callback_fired[0][0]}")
    
    # 統計テスト
    stats = sync2.get_statistics()
    summary = sync2.get_summary_text()
    test_pass("LiveCellSync.get_statistics", summary)
    
except Exception as e:
    test_fail("LiveCellSync", str(e))

# ============================
# 5. InteractiveCanvas テスト
# ============================
print("\n" + "="*50)
print("5. InteractiveCanvas テスト")
print("="*50)

try:
    # GUIなしでインポートテストのみ
    from app.gui.interactive_canvas import InteractiveCanvas
    test_pass("InteractiveCanvas import")
    
    # 機能確認（インスタンスは作成しない）
    import inspect
    methods = [m for m in dir(InteractiveCanvas) if not m.startswith('_')]
    key_methods = ['load_image', 'enable_text_overlay_mode', 'enable_onion_skin_mode', 'get_areas']
    for m in key_methods:
        if m in methods:
            test_pass(f"InteractiveCanvas.{m} メソッド存在")
        else:
            test_fail(f"InteractiveCanvas.{m}", "メソッドなし")
            
except Exception as e:
    test_fail("InteractiveCanvas import", str(e))

# ============================
# サマリー
# ============================
print("\n" + "="*50)
print("テスト結果サマリー")
print("="*50)

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")

print(f"合計: {len(results)} テスト")
print(f"✅ PASS: {passed}")
print(f"❌ FAIL: {failed}")

if failed == 0:
    print("\n🎉 全テスト合格！")
else:
    print(f"\n⚠️ {failed}件のテストが失敗しました")

sys.exit(0 if failed == 0 else 1)
