"""
Test Script for Gemini OCR Integration
Verifies that GeminiOCREngine correctly uses LLMClient to process images.
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

from app.core.gemini_ocr import GeminiOCREngine

def test_gemini_ocr():
    print("=" * 60)
    print("🧪 Testing Gemini OCR Integration")
    print("=" * 60)
    
    # Initialize Engine
    engine = GeminiOCREngine()
    if not engine.initialize():
        print("❌ Failed to initialize Gemini Engine (Check API Key)")
        return
        
    print("✅ Engine Initialized")
    
    # Prepare Test Image
    img_path = "test.jpg"
    if not os.path.exists(img_path):
        print("⚠️ test.jpg not found, creating dummy image")
        img = Image.new('RGB', (800, 600), color = 'white')
        
        # Draw some text
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "Hello Gemini OCR Test", fill="black")
        draw.text((50, 100), "This is a sample document.", fill="black")
        img.save(img_path)
    
    # Test 1: Path based
    print(f"\n🔄 Testing Path-based OCR: {img_path}")
    result = engine.detect_document_text(img_path)
    
    if result:
        print(f"✅ Path-based Result: {len(result['blocks'])} blocks")
        print(f"   Full Text Preview: {result['full_text'][:50]}...")
    else:
        print("❌ Path-based OCR Failed")

    # Test 2: Image Object based
    print(f"\n🔄 Testing Image-based OCR (PIL Object)")
    pil_image = Image.open(img_path)
    result_img = engine.detect_document_text(pil_image)
    
    if result_img:
        print(f"✅ Image-based Result: {len(result_img['blocks'])} blocks")
    else:
        print("❌ Image-based OCR Failed")

if __name__ == "__main__":
    try:
        test_gemini_ocr()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
