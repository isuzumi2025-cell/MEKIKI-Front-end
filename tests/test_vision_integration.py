"""
Vision API Integration Test (Simplified)
Direct test using OCREngine from screenshot
"""
import sys
import os
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent / "sitemap_pro"))

# Set credentials
CRED_PATH = PROJECT_ROOT.parent / "sitemap_pro" / "credentials" / "service_account.json"
if CRED_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(CRED_PATH)


def test_vision_api():
    """Direct Vision API test with screenshot from crawler"""
    print("=" * 60)
    print("🧪 Vision API Integration Test")
    print("=" * 60)
    
    # Step 1: Check credentials
    print("\n📋 Step 1: Checking credentials...")
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set")
        return False
    print(f"✅ Credentials: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
    
    # Step 2: Crawl page and get screenshot
    print("\n📋 Step 2: Crawling test page...")
    from app.core.crawler import Crawler
    from app.core.config import settings
    import asyncio
    
    settings.START_URL = "https://example.com"
    settings.MAX_PAGES = 1
    settings.HEADLESS = True
    settings.ALLOWED_DOMAINS = ["example.com"]
    
    crawler = Crawler()
    asyncio.run(crawler.run())
    
    if not crawler.nodes:
        print("❌ No pages crawled")
        return False
    
    node = crawler.nodes[0]
    screenshot_path = Path(crawler.output_dir) / node.get("screenshot", "")
    
    if not screenshot_path.exists():
        print(f"❌ Screenshot not found: {screenshot_path}")
        return False
    
    print(f"✅ Screenshot: {screenshot_path}")
    
    # Step 3: Send to Vision API
    print("\n📋 Step 3: Sending to Vision API...")
    
    try:
        from google.cloud import vision
        
        client = vision.ImageAnnotatorClient()
        
        with open(screenshot_path, "rb") as f:
            content = f.read()
        
        image = vision.Image(content=content)
        response = client.document_text_detection(image=image)
        
        if response.error.message:
            print(f"❌ Vision API Error: {response.error.message}")
            return False
        
        full_text = response.full_text_annotation.text if response.full_text_annotation else ""
        
        print(f"✅ OCR completed! {len(full_text)} characters")
        print(f"\n   Sample text:")
        print(f"   {full_text[:300]}...")
        
        # Verify
        if "Example" in full_text or "example" in full_text.lower():
            print("\n" + "=" * 60)
            print("🎉 Integration Test PASSED!")
            print("=" * 60)
            return True
        else:
            print("⚠️ Expected content not found")
            return False
            
    except ImportError:
        print("❌ google-cloud-vision not installed")
        print("   Run: pip install google-cloud-vision")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_vision_api()
    sys.exit(0 if success else 1)
