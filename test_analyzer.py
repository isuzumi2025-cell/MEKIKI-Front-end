"""
Analyzer & OCREngine の動作確認スクリプト

Google Cloud Vision APIの認証情報なしでも動作する基本テスト
"""
import sys
import io
from pathlib import Path

# Windows UTF-8対応
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.analyzer import ContentAnalyzer, DetectedArea, MatchedPair


def test_basic_classes():
    """基本的なデータクラスのテスト"""
    print("=" * 60)
    print("📝 テスト1: データクラス")
    print("=" * 60)
    
    # DetectedArea の作成
    area = DetectedArea(
        text="テストテキスト",
        bbox=[100, 100, 500, 200],
        confidence=0.95,
        source_type="web",
        source_id="https://example.com"
    )
    
    print(f"\n✅ DetectedArea 作成成功")
    print(f"   ID: {area.id}")
    print(f"   テキスト: {area.text}")
    print(f"   座標: {area.bbox}")
    print(f"   信頼度: {area.confidence}")
    
    # 辞書変換
    area_dict = area.to_dict()
    print(f"\n✅ 辞書変換成功")
    print(f"   キー数: {len(area_dict)}")


def test_similarity_calculation():
    """類似度計算のテスト"""
    print("\n" + "=" * 60)
    print("🔍 テスト2: 類似度計算")
    print("=" * 60)
    
    analyzer = ContentAnalyzer()
    
    # テストケース1: 完全一致
    text1 = "これは同じテキストです"
    text2 = "これは同じテキストです"
    score = analyzer._calculate_similarity(text1, text2)
    print(f"\n✅ 完全一致:")
    print(f"   類似度: {score:.2%}")
    assert score == 1.0, "完全一致は100%であるべき"
    
    # テストケース2: 部分一致
    text1 = "これは最初のテキストです"
    text2 = "これは2番目のテキストです"
    score = analyzer._calculate_similarity(text1, text2)
    print(f"\n✅ 部分一致:")
    print(f"   類似度: {score:.2%}")
    assert 0 < score < 1, "部分一致は0%と100%の間であるべき"
    
    # テストケース3: Jaccard係数
    text1 = "東京 大阪 京都"
    text2 = "東京 名古屋 福岡"
    score = analyzer._calculate_jaccard(text1, text2)
    print(f"\n✅ Jaccard係数:")
    print(f"   類似度: {score:.2%}")


def test_difference_detection():
    """差分検出のテスト"""
    print("\n" + "=" * 60)
    print("🔬 テスト3: 差分検出")
    print("=" * 60)
    
    analyzer = ContentAnalyzer()
    
    text1 = """1行目のテキスト
2行目のテキスト
3行目のテキスト"""
    
    text2 = """1行目のテキスト
2行目が変更されました
4行目が追加されました"""
    
    differences = analyzer.find_differences(text1, text2)
    
    print(f"\n✅ 差分検出完了: {len(differences)}件")
    for i, diff in enumerate(differences, 1):
        symbol = "+" if diff["type"] == "add" else "-" if diff["type"] == "delete" else "~"
        print(f"   {i}. [{symbol}] {diff['text']}")


def test_manual_pairing():
    """手動ペアリングのテスト"""
    print("\n" + "=" * 60)
    print("🖐️ テスト4: 手動ペアリング")
    print("=" * 60)
    
    analyzer = ContentAnalyzer()
    
    # Webエリアを作成
    web_area = DetectedArea(
        text="サンプルWebテキスト",
        bbox=[100, 100, 500, 200],
        confidence=0.95,
        source_type="web",
        source_id="https://example.com"
    )
    
    # PDFエリアを作成
    pdf_area = DetectedArea(
        text="サンプルPDFテキスト",
        bbox=[110, 110, 510, 210],
        confidence=0.92,
        source_type="pdf",
        source_id="document.pdf",
        page_num=1
    )
    
    # ペアリング
    pair = analyzer.add_manual_pair(web_area, pdf_area)
    
    print(f"\n✅ ペアリング完了")
    print(f"   類似度: {pair.similarity_score:.2%}")
    print(f"   タイプ: {pair.match_type}")
    
    # 統計情報
    stats = analyzer.get_statistics()
    print(f"\n📊 統計情報:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2%}")
        else:
            print(f"   {key}: {value}")


def test_auto_matching():
    """自動マッチングのテスト"""
    print("\n" + "=" * 60)
    print("🤖 テスト5: 自動マッチング")
    print("=" * 60)
    
    analyzer = ContentAnalyzer()
    
    # 複数のWebエリアを追加
    web_texts = [
        "東京都渋谷区のレストラン情報",
        "大阪府大阪市の観光スポット",
        "京都府京都市の寺社仏閣"
    ]
    
    for i, text in enumerate(web_texts):
        area = DetectedArea(
            text=text,
            bbox=[100, 100 + i*100, 500, 200 + i*100],
            confidence=0.9,
            source_type="web",
            source_id=f"https://example.com/page{i+1}"
        )
        analyzer.web_areas.append(area)
    
    # 複数のPDFエリアを追加
    pdf_texts = [
        "東京都渋谷区の飲食店情報",
        "名古屋市の観光情報",
        "京都市内の神社とお寺"
    ]
    
    for i, text in enumerate(pdf_texts):
        area = DetectedArea(
            text=text,
            bbox=[100, 100 + i*100, 500, 200 + i*100],
            confidence=0.88,
            source_type="pdf",
            source_id="document.pdf",
            page_num=i+1
        )
        analyzer.pdf_areas.append(area)
    
    # 自動マッチング実行
    pairs = analyzer.compute_auto_matches(threshold=0.3, method="hybrid")
    
    print(f"\n✅ マッチング完了: {len(pairs)} ペア")
    
    for i, pair in enumerate(pairs, 1):
        print(f"\n   ペア {i}:")
        print(f"     Web: {pair.web_area.text}")
        print(f"     PDF: {pair.pdf_area.text}")
        print(f"     類似度: {pair.similarity_score:.2%}")


def run_all_tests():
    """全てのテストを実行"""
    print("\n🚀 ContentAnalyzer 動作確認スクリプト")
    print("=" * 60)
    
    try:
        test_basic_classes()
        test_similarity_calculation()
        test_difference_detection()
        test_manual_pairing()
        test_auto_matching()
        
        print("\n" + "=" * 60)
        print("✅ 全てのテストが成功しました！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ アサーションエラー: {e}")
        return False
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

