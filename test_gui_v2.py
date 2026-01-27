"""
GUI V2 の動作確認スクリプト
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


def test_with_sample_data():
    """サンプルデータでGUIをテスト"""
    print("=" * 60)
    print("🧪 GUI V2 テスト - サンプルデータ生成")
    print("=" * 60)
    
    # Analyzerを作成
    analyzer = ContentAnalyzer()
    
    # サンプルWebエリアを追加
    web_data = [
        ("東京都渋谷区のレストラン情報", [100, 100, 500, 300]),
        ("大阪府大阪市の観光スポット", [100, 350, 500, 550]),
        ("京都府京都市の寺社仏閣", [100, 600, 500, 800]),
    ]
    
    for i, (text, bbox) in enumerate(web_data):
        area = DetectedArea(
            text=text,
            bbox=bbox,
            confidence=0.9,
            source_type="web",
            source_id=f"https://example.com/page{i+1}"
        )
        analyzer.web_areas.append(area)
    
    # サンプルPDFエリアを追加
    pdf_data = [
        ("東京都渋谷区の飲食店情報", [100, 100, 500, 300]),
        ("名古屋市の観光情報", [100, 350, 500, 550]),
        ("京都市内の神社とお寺", [100, 600, 500, 800]),
    ]
    
    for i, (text, bbox) in enumerate(pdf_data):
        area = DetectedArea(
            text=text,
            bbox=bbox,
            confidence=0.88,
            source_type="pdf",
            source_id="sample.pdf",
            page_num=i+1
        )
        analyzer.pdf_areas.append(area)
    
    print(f"✅ サンプルデータ生成完了")
    print(f"   Web: {len(analyzer.web_areas)} エリア")
    print(f"   PDF: {len(analyzer.pdf_areas)} エリア")
    
    # 自動マッチング
    print(f"\n🔄 自動マッチング実行中...")
    pairs = analyzer.compute_auto_matches(threshold=0.3, method="hybrid")
    
    print(f"\n✅ マッチング完了: {len(pairs)} ペア")
    for i, pair in enumerate(pairs, 1):
        print(f"\n   ペア {i}:")
        print(f"     Web: {pair.web_page.text}")
        print(f"     PDF: {pair.pdf_page.text}")
        print(f"     類似度: {pair.similarity_score:.2%}")
    
    return analyzer


def launch_gui_with_data(analyzer):
    """サンプルデータでGUIを起動"""
    print("\n" + "=" * 60)
    print("🚀 GUI V2 起動")
    print("=" * 60)
    
    from app.gui.main_window_v2 import MainWindow
    
    # GUIを起動
    app = MainWindow()
    
    # Analyzerを設定
    app.analyzer = analyzer
    
    # 全体マップを表示
    app.show_macro_view()
    
    print("✅ GUI起動完了 - 全体マップを表示")
    print("   左のナビゲーションから操作を選択できます")
    
    app.mainloop()


if __name__ == "__main__":
    print("\n🎨 GUI V2 動作確認\n")
    
    try:
        # サンプルデータを生成
        analyzer = test_with_sample_data()
        
        # GUIを起動
        launch_gui_with_data(analyzer)
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

