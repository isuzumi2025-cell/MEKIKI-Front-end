"""
PDF Loader テストスクリプト
PyMuPDF単体での動作確認
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.pdf_loader import PDFLoader


def test_pdf_loader(pdf_path: str):
    """
    PDFローダーの動作テスト
    
    Args:
        pdf_path: テスト対象のPDFファイルパス
    """
    print("="*70)
    print("🧪 PDF Loader Test (PyMuPDF Only)")
    print("="*70)
    
    # PDFローダーを初期化
    loader = PDFLoader(dpi=300)
    
    try:
        # PDFを読み込み
        results = loader.load_pdf(pdf_path)
        
        # 結果サマリー
        print("\n" + "="*70)
        print("📊 Test Results Summary")
        print("="*70)
        print(f"✅ PDF File: {pdf_path}")
        print(f"✅ Total Pages: {len(results)}")
        print(f"✅ Total Characters: {sum(len(r['text']) for r in results)}")
        print(f"✅ Total Areas: {sum(len(r['areas']) for r in results)}")
        
        # 各ページの詳細
        print("\n" + "-"*70)
        print("📄 Page Details")
        print("-"*70)
        for i, page_data in enumerate(results, start=1):
            image = page_data['page_image']
            print(f"Page {i}:")
            print(f"  - Image Size: {image.size[0]}x{image.size[1]}px")
            print(f"  - Text Length: {len(page_data['text'])} chars")
            print(f"  - Areas Count: {len(page_data['areas'])}")
            print(f"  - First 100 chars: {page_data['text'][:100]}...")
            print()
        
        print("="*70)
        print("✅ Test Passed!")
        print("="*70)
        
        return True
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ Test Failed!")
        print("="*70)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # コマンドライン引数からPDFパスを取得
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_loader.py <pdf_file_path>")
        print("\nExample:")
        print("  python test_pdf_loader.py sample.pdf")
        print("  python test_pdf_loader.py C:/path/to/document.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # PDFファイルの存在確認
    if not Path(pdf_path).exists():
        print(f"❌ Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # テスト実行
    success = test_pdf_loader(pdf_path)
    
    sys.exit(0 if success else 1)

