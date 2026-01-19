from app.core.enhanced_scraper import EnhancedWebScraper
import os

def test_stitching():
    scraper = EnhancedWebScraper(headless=True)
    
    # Use a scroll-heavy page to test stitching
    # Since we can't guarantee external access, we trust the code logic but we can run it against example.com or a known long page if user allows.
    target_url = "https://www.apple.com" # Apple uses lots of scroll effects
    
    print(f"🌍 Testing stitching scraper on {target_url}...")
    try:
        title, text, full_img, view_img = scraper.scrape_with_lazy_loading(
            url=target_url,
            max_scrolls=5  # Longer scroll to test stitching
        )
        
        print(f"✅ Scraped: {title}")
        print(f"📊 Full Image Size: {full_img.size}")
        print(f"📊 View Image Size: {view_img.size}")
        
        output_path = "test_stitch_ultrathink.png"
        full_img.save(output_path)
        print(f"💾 Saved stitched image to {output_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_stitching()
