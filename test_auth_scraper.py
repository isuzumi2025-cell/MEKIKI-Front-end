"""Test OCR scraper with auth"""
import sys
sys.path.insert(0, '.')

from app.core.enhanced_scraper import EnhancedWebScraper

url = "https://www.portcafe.net/demo/jrkyushu/jisha-meguri/"
username = "jrq"
password = "testga"

print(f"Testing URL: {url}")
print(f"Username: {username}")
print(f"Password: {password}")

scraper = EnhancedWebScraper(headless=True)

try:
    title, text, img_full, img_view = scraper.scrape_with_lazy_loading(
        url=url,
        username=username,
        password=password
    )
    
    print(f"\n=== SUCCESS ===")
    print(f"Title: {title}")
    print(f"Text length: {len(text)} chars")
    print(f"Full image size: {img_full.size if img_full else 'None'}")
    print(f"Viewport image size: {img_view.size if img_view else 'None'}")
    
except Exception as e:
    print(f"\n=== ERROR ===")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
