"""
OCR精度診断スクリプト
- 同一画像でOCR実行し、テキスト抽出量と座標精度を確認
- チャンク分割時の座標オフセットを検証
"""
import os
import sys
from pathlib import Path

# Windows コンソールのエンコーディング対策
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PIL import Image
from app.core.engine_cloud import CloudOCREngine

def diagnose_ocr(image_path: str):
    """OCR診断を実行"""
    print("=" * 60)
    print(f"🔍 OCR診断: {image_path}")
    print("=" * 60)
    
    # 画像読み込み
    if not os.path.exists(image_path):
        print(f"❌ ファイルが見つかりません: {image_path}")
        return
    
    image = Image.open(image_path)
    print(f"📐 画像サイズ: {image.width} x {image.height}")
    print(f"📐 アスペクト比: {image.height / image.width:.2f}")
    print(f"📐 モード: {image.mode}")
    
    # OCRエンジン初期化
    engine = CloudOCREngine()
    
    print("\n🚀 OCR実行中...")
    try:
        clusters, raw_words = engine.extract_text(image)
        
        print(f"\n✅ OCR完了")
        print(f"📊 クラスタ数: {len(clusters)}")
        print(f"📊 単語数: {len(raw_words)}")
        
        # テキスト総量
        total_text = "".join([c.get('text', '') for c in clusters])
        print(f"📊 総文字数: {len(total_text)}")
        
        # クラスタ座標範囲
        if clusters:
            all_rects = [c['rect'] for c in clusters if 'rect' in c]
            if all_rects:
                min_x = min(r[0] for r in all_rects)
                min_y = min(r[1] for r in all_rects)
                max_x = max(r[2] for r in all_rects)
                max_y = max(r[3] for r in all_rects)
                print(f"📍 座標範囲: ({min_x}, {min_y}) - ({max_x}, {max_y})")
                
                # 座標が画像サイズを超えていないかチェック
                if max_x > image.width or max_y > image.height:
                    print(f"⚠️ 座標オーバーフロー検出!")
                    print(f"   画像: {image.width}x{image.height}")
                    print(f"   座標最大: ({max_x}, {max_y})")
        
        # 最初の5クラスタを表示
        print("\n📋 クラスタサンプル (最初の5件):")
        for i, c in enumerate(clusters[:5]):
            text_preview = c.get('text', '')[:50].replace('\n', ' ')
            rect = c.get('rect', [0,0,0,0])
            print(f"  [{i+1}] rect={rect} text=\"{text_preview}...\"")
        
        return clusters, raw_words
        
    except Exception as e:
        print(f"❌ OCRエラー: {e}")
        import traceback
        traceback.print_exc()
        return None, None


if __name__ == "__main__":
    # テスト画像
    test_images = [
        "test.jpg",  # プロジェクトルートにあれば
    ]
    
    # 引数で画像パスを指定可能
    if len(sys.argv) > 1:
        test_images = sys.argv[1:]
    
    for img_path in test_images:
        full_path = project_root / img_path if not os.path.isabs(img_path) else Path(img_path)
        if full_path.exists():
            diagnose_ocr(str(full_path))
            print("\n")
        else:
            print(f"⚠️ スキップ: {img_path} (ファイルなし)")
