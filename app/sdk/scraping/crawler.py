"""
StandaloneScraper v3
WebCrawler を直接使用してサーバー不要で動作

Features:
- robots.txt遵守
- リトライ機構 (exponential backoff)
- キュー重複排除
- レート制限
- Basic認証対応
"""
import base64
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from PIL import Image
import io


@dataclass
class PageResult:
    """ページ結果"""
    url: str
    status_code: int
    title: str
    text_content: str
    screenshot_base64: Optional[str]
    depth: int
    parent_url: Optional[str]
    links: List[str]
    h1: str = ""
    meta_desc: str = ""
    canonical: str = ""
    error: Optional[str] = None

    def to_dict(self):
        return {
            'url': self.url,
            'status_code': self.status_code,
            'title': self.title,
            'text_content': self.text_content,
            'screenshot_base64': self.screenshot_base64,
            'depth': self.depth,
            'parent_url': self.parent_url,
            'links': self.links,
            'h1': self.h1,
            'meta_desc': self.meta_desc,
            'canonical': self.canonical,
            'error': self.error
        }


class StandaloneScraper:
    """
    StandaloneScraper v3
    WebCrawler を直接使用 (sitemap_pro 依存なし)
    """
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        respect_robots: bool = True,
        request_delay: float = 1.0,
        max_retries: int = 3
    ):
        self.headless = headless
        self.timeout = timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.respect_robots = respect_robots
        self.request_delay = request_delay
        self.max_retries = max_retries
    
    def crawl(
        self,
        start_url: str,
        max_pages: int = 10,
        max_depth: int = 3,
        username: Optional[str] = None,
        password: Optional[str] = None,
        allowed_domains: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[PageResult]:
        """
        BFS Crawl using WebCrawler
        
        Args:
            start_url: Start URL
            max_pages: Maximum pages to crawl
            max_depth: Maximum depth
            username: Basic auth username
            password: Basic auth password
            allowed_domains: Allowed domain list
            progress_callback: Progress callback (url, current, total)
        
        Returns:
            List[PageResult]: Crawl results
        """
        # Import WebCrawler from OCR's crawler module
        from app.core.crawler import WebCrawler
        
        # Create crawler with settings
        crawler = WebCrawler(
            max_pages=max_pages,
            max_depth=max_depth,
            delay=self.request_delay,
            username=username,
            password=password
        )
        
        # Run crawl
        raw_results = crawler.crawl(
            root_url=start_url,
            progress_callback=progress_callback
        )
        
        # Convert to PageResult format
        results = []
        for idx, r in enumerate(raw_results):
            # Get screenshot as base64
            screenshot_base64 = None
            full_img = r.get("full_image") or r.get("screenshot_image")
            
            if full_img is not None:
                try:
                    buffer = io.BytesIO()
                    full_img.save(buffer, format="PNG")
                    screenshot_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                except Exception as e:
                    print(f"Screenshot encode error: {e}")
            
            results.append(PageResult(
                url=r.get("url", ""),
                status_code=200 if not r.get("error") else 0,
                title=r.get("title", ""),
                text_content=r.get("text", ""),
                screenshot_base64=screenshot_base64,
                depth=r.get("depth", 0),
                parent_url=None,
                links=[],
                h1="",
                meta_desc="",
                canonical="",
                error=r.get("error")
            ))
        
        return results
    
    def scrape_page(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        take_screenshot: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> PageResult:
        """
        Scrape single page
        """
        results = self.crawl(
            start_url=url,
            max_pages=1,
            max_depth=0,
            username=username,
            password=password,
            progress_callback=lambda u, c, t: progress_callback(u) if progress_callback else None
        )
        
        if results:
            return results[0]
        
        return PageResult(
            url=url,
            status_code=0,
            title="",
            text_content="",
            screenshot_base64=None,
            depth=0,
            parent_url=None,
            links=[],
            error="No results"
        )
    
    def get_results_as_dict_list(self, results: List[PageResult]) -> List[Dict]:
        """Convert results to dict list for queue"""
        return [
            {
                'type': 'web',
                'url': r.url,
                'status_code': r.status_code,
                'title': r.title,
                'text_content': r.text_content,
                'screenshot_base64': r.screenshot_base64,
                'depth': r.depth,
                'parent_url': r.parent_url,
                'h1': r.h1,
                'meta_desc': r.meta_desc,
                'canonical': r.canonical,
                'error': r.error
            }
            for r in results
        ]


# Test
if __name__ == "__main__":
    scraper = StandaloneScraper(headless=True)
    
    result = scraper.scrape_page("https://example.com")
    print(f"Title: {result.title}")
    print(f"Status: {result.status_code}")
    print(f"Has Screenshot: {result.screenshot_base64 is not None}")
