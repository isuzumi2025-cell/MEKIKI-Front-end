"""
GUI V2 Real Image Test (Using load_page API)
Confirm that ContentAnalyzer.load_page works correctly and MacroView renders the result.
"""
import sys
import io
import os
from pathlib import Path
from PIL import Image

# Windows UTF-8 support
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.analyzer import ContentAnalyzer, MatchedPair

def test_load_page_api():
    print("=" * 60)
    print("🧪 GUI V2 Test - ContentAnalyzer.load_page API")
    print("=" * 60)
    
    analyzer = ContentAnalyzer()
    
    # Load test image
    img_path = "test.jpg"
    if not os.path.exists(img_path):
        print(f"❌ Test image not found: {img_path}")
        # Create a dummy image
        img = Image.new('RGB', (800, 600), color = 'green')
        img_path = "dummy_test.jpg"
        img.save(img_path)
    
    # Use load_page to load as Web
    print(f"🔄 Loading as Web Page: {img_path}")
    web_page = analyzer.load_page(
        image_path=img_path,
        source_type="web",
        source_id="http://localhost/test",
        title="Local Test Image (Web)"
    )
    
    if not web_page:
        print("❌ Failed to load Web page")
        return None
    
    # Use load_page to load as PDF
    print(f"🔄 Loading as PDF Page: {img_path}")
    pdf_page = analyzer.load_page(
        image_path=img_path,
        source_type="pdf",
        source_id="test_doc.pdf",
        page_num=1,
        title="Local Test Image (PDF)"
    )
    
    if not pdf_page:
        print("❌ Failed to load PDF page")
        return None
        
    print(f"✅ Data loaded successfully")
    print(f"   Web Pages: {len(analyzer.web_pages)}")
    print(f"   PDF Pages: {len(analyzer.pdf_pages)}")
    
    # Manual Match
    pair = MatchedPair(
        web_page=web_page,
        pdf_page=pdf_page,
        similarity_score=0.99,
        match_type="manual"
    )
    analyzer.matched_pairs.append(pair)
    print(f"✅ Created MatchedPair")
    
    return analyzer

def launch_gui(analyzer):
    print("\n" + "=" * 60)
    print("🚀 Launching GUI V2")
    print("=" * 60)
    
    from app.gui.main_window_v2 import MainWindow
    
    app = MainWindow()
    app.analyzer = analyzer
    app.show_macro_view()
    
    app.mainloop()

if __name__ == "__main__":
    try:
        analyzer = test_load_page_api()
        if analyzer:
            launch_gui(analyzer)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
