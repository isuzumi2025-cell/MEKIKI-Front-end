"""
ContentAnalyzer と OCREngine の使用例

このスクリプトは、新しい分析エンジンの基本的な使い方を示します。
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.ocr_engine import OCREngine
from app.core.analyzer import ContentAnalyzer, DetectedArea


def example_basic_ocr():
    """基本的なOCR実行例"""
    print("=" * 60)
    print("📝 例1: 基本的なOCR実行")
    print("=" * 60)
    
    # OCRエンジンを初期化
    ocr = OCREngine(credentials_path="credentials.json")
    
    if not ocr.initialize():
        print("⚠️ OCRエンジンの初期化に失敗しました")
        return
    
    # 画像からテキストを検出
    image_path = "test_images/sample.png"  # 適切なパスに変更してください
    
    result = ocr.detect_document_text(image_path)
    
    if result:
        print(f"\n📄 全体テキスト:\n{result['full_text']}\n")
        print(f"🔍 検出されたブロック数: {len(result['blocks'])}")
        
        for i, block in enumerate(result['blocks'][:3], 1):  # 最初の3ブロックのみ表示
            print(f"\n  ブロック {i}:")
            print(f"    テキスト: {block['text'][:50]}...")
            print(f"    座標: {block['bbox']}")
            print(f"    信頼度: {block['confidence']:.2%}")


def example_analyzer_workflow():
    """ContentAnalyzerを使用したワークフロー例"""
    print("\n" + "=" * 60)
    print("📊 例2: ContentAnalyzer ワークフロー")
    print("=" * 60)
    
    # OCRエンジンを初期化
    ocr = OCREngine(credentials_path="credentials.json")
    
    if not ocr.initialize():
        print("⚠️ OCRエンジンの初期化に失敗しました")
        return
    
    # ContentAnalyzerを作成
    analyzer = ContentAnalyzer(ocr_engine=ocr)
    
    # ステップ1: Web画像を分析
    print("\n📌 ステップ1: Web画像を分析")
    web_image_path = "screenshots/web_page1.png"  # 適切なパスに変更
    web_areas = analyzer.analyze_image(
        image_path=web_image_path,
        source_type="web",
        source_id="https://example.com/page1"
    )
    print(f"   ✅ {len(web_areas)} エリア検出")
    
    # ステップ2: PDF画像を分析
    print("\n📌 ステップ2: PDF画像を分析")
    pdf_image_path = "pdf_previews/document_page1.png"  # 適切なパスに変更
    pdf_areas = analyzer.analyze_image(
        image_path=pdf_image_path,
        source_type="pdf",
        source_id="document.pdf",
        page_num=1
    )
    print(f"   ✅ {len(pdf_areas)} エリア検出")
    
    # ステップ3: 自動マッチング
    print("\n📌 ステップ3: 自動マッチング実行")
    pairs = analyzer.compute_auto_matches(
        threshold=0.3,
        method="hybrid"
    )
    
    print(f"\n🎯 マッチング結果:")
    for i, pair in enumerate(pairs[:5], 1):  # 最初の5ペアのみ表示
        print(f"\n  ペア {i}:")
        print(f"    Web: {pair.web_area.text[:30]}...")
        print(f"    PDF: {pair.pdf_area.text[:30]}...")
        print(f"    類似度: {pair.similarity_score:.2%}")
    
    # ステップ4: 統計情報を表示
    print("\n📊 統計情報:")
    stats = analyzer.get_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2%}")
        else:
            print(f"   {key}: {value}")


def example_manual_pairing():
    """手動ペアリングの例"""
    print("\n" + "=" * 60)
    print("🖐️ 例3: 手動ペアリング")
    print("=" * 60)
    
    # Analyzerを作成（OCRなし）
    analyzer = ContentAnalyzer()
    
    # 仮のエリアを作成
    web_area = DetectedArea(
        text="サンプルテキスト1",
        bbox=[100, 100, 500, 200],
        confidence=0.95,
        source_type="web",
        source_id="https://example.com"
    )
    
    pdf_area = DetectedArea(
        text="サンプルテキスト1",
        bbox=[120, 110, 520, 210],
        confidence=0.92,
        source_type="pdf",
        source_id="document.pdf",
        page_num=1
    )
    
    # 手動でペアリング
    pair = analyzer.add_manual_pair(web_area, pdf_area)
    
    print(f"\n✅ ペアリング完了")
    print(f"   類似度: {pair.similarity_score:.2%}")
    print(f"   タイプ: {pair.match_type}")


def example_text_difference():
    """テキスト差分検出の例"""
    print("\n" + "=" * 60)
    print("🔍 例4: テキスト差分検出")
    print("=" * 60)
    
    analyzer = ContentAnalyzer()
    
    text1 = """これは最初のテキストです。
2行目の内容。
3行目の内容。"""
    
    text2 = """これは変更後のテキストです。
2行目の内容。
4行目が追加されました。"""
    
    differences = analyzer.find_differences(text1, text2)
    
    print("\n📝 差分:")
    for diff in differences:
        symbol = "+" if diff["type"] == "add" else "-"
        print(f"   {symbol} {diff['text']}")


if __name__ == "__main__":
    print("\n🚀 ContentAnalyzer & OCREngine 使用例\n")
    
    # 注意: credentials.json が必要です
    print("⚠️ 注意: この例を実行するには、プロジェクトルートに")
    print("   credentials.json を配置する必要があります。\n")
    
    # 各例を実行（実際の画像パスに合わせて調整してください）
    try:
        # example_basic_ocr()
        # example_analyzer_workflow()
        example_manual_pairing()
        example_text_difference()
        
        print("\n✅ 全ての例が完了しました")
        
    except Exception as e:
        print(f"\n⚠️ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()

