"""
Web Ingestion Module
Playwright経由でWebページをキャプチャしテキスト/画像を取得

Created: 2026-01-11
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import uuid

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class WebCaptureResult:
    """Webキャプチャ結果"""
    capture_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    title: str = ""
    dom_text: str = ""
    html: str = ""
    screenshot_path: Optional[str] = None
    captured_at: datetime = field(default_factory=datetime.now)
    viewport_width: int = 1920
    viewport_height: int = 1080
    full_page: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class WebIngestor:
    """
    Webページ取り込みクラス
    Playwright経由でレンダリング済み画面をキャプチャ
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        headless: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080
    ):
        """
        初期化
        
        Args:
            storage_path: 画像保存先ディレクトリ
            headless: ヘッドレスモードで実行
            viewport_width: ビューポート幅
            viewport_height: ビューポート高さ
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("playwright is not installed. Run: pip install playwright && playwright install")
        
        self.storage_path = Path(storage_path) if storage_path else Path("storage/runs")
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        
        self._browser: Optional[Browser] = None
        self._playwright = None
    
    async def __aenter__(self):
        await self._start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._stop_browser()
    
    async def _start_browser(self):
        """ブラウザ起動"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
    
    async def _stop_browser(self):
        """ブラウザ終了"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def capture(
        self,
        url: str,
        run_id: Optional[str] = None,
        storage_state: Optional[str] = None,
        wait_for_selector: Optional[str] = None,
        wait_ms: int = 2000,
        full_page: bool = True,
        extract_dom_text: bool = True
    ) -> WebCaptureResult:
        """
        Webページをキャプチャ
        
        Args:
            url: キャプチャ対象URL
            run_id: 実行ID（保存先ディレクトリ）
            storage_state: ログイン状態を保持したstorageStateファイルパス
            wait_for_selector: 待機するセレクタ
            wait_ms: 追加待機時間（ミリ秒）
            full_page: フルページスクリーンショット
            extract_dom_text: DOMテキストを抽出するか
            
        Returns:
            WebCaptureResult
        """
        result = WebCaptureResult(url=url, full_page=full_page)
        
        try:
            # コンテキスト作成
            context_options = {
                "viewport": {"width": self.viewport_width, "height": self.viewport_height}
            }
            
            # storageState対応（ログイン状態維持）
            if storage_state and Path(storage_state).exists():
                context_options["storage_state"] = storage_state
            
            context = await self._browser.new_context(**context_options)
            page = await context.new_page()
            
            # ページ読み込み
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # 追加待機
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            
            if wait_ms > 0:
                await asyncio.sleep(wait_ms / 1000)
            
            # タイトル取得
            result.title = await page.title()
            
            # DOMテキスト抽出
            if extract_dom_text:
                result.dom_text = await self._extract_dom_text(page)
            
            # HTML取得
            result.html = await page.content()
            
            # スクリーンショット保存
            run_id = run_id or str(uuid.uuid4())[:8]
            save_dir = self.storage_path / run_id / "images"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_name = f"web_{result.capture_id[:8]}.png"
            screenshot_path = save_dir / screenshot_name
            
            await page.screenshot(path=str(screenshot_path), full_page=full_page)
            result.screenshot_path = str(screenshot_path)
            
            # メタデータ
            result.metadata = {
                "run_id": run_id,
                "final_url": page.url,
                "viewport": {"width": self.viewport_width, "height": self.viewport_height}
            }
            
            await context.close()
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    async def _extract_dom_text(self, page: Page) -> str:
        """
        DOMからテキストを抽出（Text-first）
        
        非表示要素を除外し、可視テキストのみ抽出
        """
        # JavaScriptでテキスト抽出
        text = await page.evaluate("""
            () => {
                // 不要な要素を除去
                const excludeTags = ['script', 'style', 'noscript', 'svg', 'path'];
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: (node) => {
                            const parent = node.parentElement;
                            if (!parent) return NodeFilter.FILTER_REJECT;
                            
                            // タグ名チェック
                            if (excludeTags.includes(parent.tagName.toLowerCase())) {
                                return NodeFilter.FILTER_REJECT;
                            }
                            
                            // 非表示チェック
                            const style = window.getComputedStyle(parent);
                            if (style.display === 'none' || style.visibility === 'hidden') {
                                return NodeFilter.FILTER_REJECT;
                            }
                            
                            // 空白のみはスキップ
                            if (!node.textContent.trim()) {
                                return NodeFilter.FILTER_REJECT;
                            }
                            
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                
                const texts = [];
                let node;
                while (node = walker.nextNode()) {
                    texts.push(node.textContent.trim());
                }
                
                return texts.join('\\n');
            }
        """)
        
        return text
    
    async def capture_with_login(
        self,
        url: str,
        login_url: str,
        username: str,
        password: str,
        username_selector: str = 'input[name="username"], input[type="email"]',
        password_selector: str = 'input[name="password"], input[type="password"]',
        submit_selector: str = 'button[type="submit"]',
        **capture_kwargs
    ) -> WebCaptureResult:
        """
        ログインしてからキャプチャ
        """
        context = await self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )
        page = await context.new_page()
        
        try:
            # ログインページへ
            await page.goto(login_url, wait_until="networkidle")
            
            # 認証情報入力
            await page.fill(username_selector, username)
            await page.fill(password_selector, password)
            await page.click(submit_selector)
            
            # ログイン完了待機
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # storageState保存
            storage_state = await context.storage_state()
            state_path = self.storage_path / "auth_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(state_path, 'w') as f:
                json.dump(storage_state, f)
            
            await context.close()
            
            # 保存したstateでキャプチャ
            return await self.capture(url, storage_state=str(state_path), **capture_kwargs)
            
        except Exception as e:
            await context.close()
            result = WebCaptureResult(url=url)
            result.error = f"Login failed: {e}"
            return result


# ========== Sync Wrapper ==========

def capture_web_page(
    url: str,
    run_id: Optional[str] = None,
    storage_state: Optional[str] = None,
    headless: bool = True,
    **kwargs
) -> WebCaptureResult:
    """
    Webページキャプチャ（同期ラッパー）
    
    Args:
        url: キャプチャ対象URL
        run_id: 実行ID
        storage_state: 認証状態ファイル
        headless: ヘッドレスモード
        
    Returns:
        WebCaptureResult
    """
    async def _run():
        async with WebIngestor(headless=headless) as ingestor:
            return await ingestor.capture(url, run_id=run_id, storage_state=storage_state, **kwargs)
    
    return asyncio.run(_run())


if __name__ == "__main__":
    # テスト
    result = capture_web_page("https://example.com", run_id="test")
    print(f"Title: {result.title}")
    print(f"Screenshot: {result.screenshot_path}")
    print(f"DOM Text (first 200): {result.dom_text[:200]}...")
    print(f"Error: {result.error}")
