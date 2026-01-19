"""
Webクローラー（魔改造版）
インテリジェントなサイトマップ構築 + メタデータ収集 + 静的アセット除外
"""
from urllib.parse import urljoin, urlparse, unquote
from typing import List, Set, Optional, Callable, Dict, Tuple
# EnhancedWebScraperは__init__内でインポート (line 50)
import time
import re
import base64


class WebCrawler:
    """インテリジェント・Webクローラークラス"""
    
    # 静的アセットの拡張子（除外対象）
    STATIC_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',  # 画像
        '.css', '.scss', '.sass', '.less',  # スタイルシート
        '.js', '.jsx', '.ts', '.tsx', '.mjs',  # JavaScript
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # ドキュメント
        '.zip', '.tar', '.gz', '.rar', '.7z',  # アーカイブ
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mp3', '.wav',  # メディア
        '.xml', '.json', '.csv', '.txt', '.log'  # データファイル
    }
    
    def __init__(
        self,
        max_pages: int = 50,
        max_depth: int = 5,
        delay: float = 0.5,  # 2.0s → 0.5s 短縮（サーバー負荷軽減のため0にはしない）
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Args:
            max_pages: 最大ページ数
            max_depth: 最大深さ（0=ルートのみ、1=ルート+1階層、2=ルート+2階層...）
            delay: リクエスト間の遅延（秒）
            username: Basic認証ユーザー名
            password: Basic認証パスワード
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.username = username
        self.password = password
        
        # EnhancedWebScraperを使用（Smart Stitching対応）
        from app.core.enhanced_scraper import EnhancedWebScraper
        self.scraper = EnhancedWebScraper(headless=True)
        
        self.visited_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.sitemap: Dict[str, Dict] = {}  # URL -> メタデータマップ
    
    def _is_static_asset(self, url: str) -> bool:
        """
        URLが静的アセットかどうかを判定
        
        Args:
            url: 判定するURL
        
        Returns:
            静的アセットの場合True
        """
        parsed = urlparse(url)
        path = unquote(parsed.path.lower())
        
        # 拡張子チェック
        for ext in self.STATIC_EXTENSIONS:
            if path.endswith(ext):
                return True
        
        # 特定のパスパターンを除外
        exclude_patterns = [
            r'/assets/',
            r'/static/',
            r'/images/',
            r'/img/',
            r'/css/',
            r'/js/',
            r'/fonts/',
            r'/media/',
            r'/download/'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        
        return False
    
    def _normalize_url(self, url: str) -> str:
        """
        URLを正規化（フラグメント除去、末尾スラッシュ統一）
        ⚠️ クエリパラメータは保持（重要なページ識別子の可能性があるため）
        
        Args:
            url: 正規化するURL
        
        Returns:
            正規化されたURL
        """
        # フラグメントを除去
        url = url.split('#')[0]
        
        parsed = urlparse(url)
        
        # スキーム、ホスト、パス、クエリを使用
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # クエリパラメータがあれば追加
        if parsed.query:
            normalized += f"?{parsed.query}"
        
        # 末尾スラッシュを統一（ある場合は削除、ルートは保持）
        # ただし、クエリパラメータがある場合は末尾スラッシュを気にしない
        if not parsed.query and normalized.endswith('/') and len(parsed.path) > 1:
            normalized = normalized.rstrip('/')
        
        return normalized
    
    def crawl(
        self,
        root_url: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[dict]:
        """
        ルートURLからクローリングを開始
        
        Args:
            root_url: 開始URL
            progress_callback: 進捗コールバック (url, current, total) -> None
        
        Returns:
            [{"url": str, "title": str, "text": str, "screenshot_path": str, "error": str or None}, ...]
        """
        print(f"\n{'='*60}")
        print(f"[Web] 🚀 Intelligent Crawling Start")
        print(f"  Root URL: {root_url}")
        print(f"  Max Depth: {self.max_depth}")
        print(f"  Max Pages: {self.max_pages}")
        print(f"{'='*60}\n")
        
        self.visited_urls.clear()
        self.failed_urls.clear()
        self.sitemap.clear()
        
        root_url = self._normalize_url(root_url)
        root_domain = urlparse(root_url).netloc
        results = []
        queue = [(root_url, 0, None)]  # (url, depth, parent_url)
        
        while queue and len(results) < self.max_pages:
            current_url, depth, parent_url = queue.pop(0)
            
            print(f"[Web] [Depth: {depth}] [Queue: {len(queue)}] {current_url}")
            
            # 深さチェック
            if depth > self.max_depth:
                print(f"[Web]   ❌ Skipped: Depth limit ({self.max_depth}) exceeded")
                continue
            
            # 既に訪問済み
            if current_url in self.visited_urls:
                print(f"[Web]   ⏭️  Skipped: Already visited")
                continue
            
            # ドメインチェック
            current_domain = urlparse(current_url).netloc
            if current_domain != root_domain:
                print(f"[Web]   ❌ Skipped: Different domain ({current_domain})")
                continue
            
            # 静的アセットチェック
            if self._is_static_asset(current_url):
                print(f"[Web]   🚫 Skipped: Static asset")
                continue
            
            try:
                # スクレイピング実行
                if progress_callback:
                    progress_callback(current_url, len(results), self.max_pages)
                
                print(f"[Web] Fetching: {current_url}")
                
                # 認証情報が設定されているか確認
                if self.username and self.password:
                    print(f"[Web]   🔐 Basic認証使用: {self.username}")
                
                # EnhancedWebScraperを使用
                title, text, img_full, img_view = self.scraper.scrape_with_lazy_loading(
                    url=current_url,
                    username=self.username,
                    password=self.password
                )
                
                # スクリーンショットを保存（オプション）
                screenshot_path = None  # 必要に応じて保存処理を追加
                
                # 暫定版: 画像全体を1つのエリアとして扱う
                # 将来的にはPlaywrightで要素ごとの位置を取得する可能性あり
                # img_viewのサイズを取得
                img_width, img_height = img_view.size if img_view else (1920, 1080)
                areas = [{
                    "text": text,
                    "bbox": [0, 0, img_width, img_height],
                    "area_id": 1
                }]
                
                # メタデータを構築
                metadata = {
                    "url": current_url,
                    "title": title,
                    "text": text,
                    "screenshot_path": screenshot_path,
                    "areas": areas,  # bbox付きテキスト領域
                    "screenshot_image": img_view,  # PIL Image (Viewport)
                    "full_image": img_full, # PIL Image (Stitched Full Page)
                    "error": None,  # 成功時はNone
                    "depth": depth,  # 階層レベル
                    "parent_url": parent_url,  # 親URL
                    "fetch_time": time.time()  # 取得時刻
                }
                
                results.append(metadata)
                self.visited_urls.add(current_url)
                self.sitemap[current_url] = metadata
                
                print(f"[Web]   ✅ Success: {len(text)} chars, {len(title)} title")
                
                # リンクを抽出してキューに追加（次の深さ）
                if depth < self.max_depth:
                    try:
                        links = self._extract_links_from_page(current_url)
                        print(f"[Web]   🔗 Found {len(links)} raw links")
                        
                        added_count = 0
                        filtered_count = 0
                        invalid_count = 0
                        
                        for link in links:
                            # 正規化
                            try:
                                normalized_link = self._normalize_url(link)
                            except Exception as e:
                                print(f"[Web]   ⚠️ URL normalization failed for {link}: {e}")
                                invalid_count += 1
                                continue
                            
                            # 静的アセット除外
                            if self._is_static_asset(normalized_link):
                                filtered_count += 1
                                continue
                            
                            # URLの妥当性チェック（簡易）
                            parsed_link = urlparse(normalized_link)
                            if not parsed_link.netloc or not parsed_link.scheme:
                                print(f"[Web]   ⚠️ Invalid URL format: {normalized_link}")
                                invalid_count += 1
                                continue
                            
                            # 未訪問かつキューに未登録
                            if normalized_link not in self.visited_urls and normalized_link not in [q[0] for q in queue]:
                                # デバッグ: リンクの追加を詳細表示
                                if added_count < 3:  # 最初の3件のみ表示
                                    print(f"[Web]     ➕ Adding: {normalized_link}")
                                
                                queue.append((normalized_link, depth + 1, current_url))  # 親URLも記録
                                added_count += 1
                        
                        print(f"[Web]   📥 Summary: {added_count} added, {filtered_count} filtered, {invalid_count} invalid")
                    except Exception as e:
                        print(f"[Web]   ⚠️ Link extraction failed: {e}")
                        import traceback
                        traceback.print_exc()
                
                # 遅延（少し長めに設定）
                if self.delay > 0:
                    time.sleep(self.delay)
                    
            except Exception as e:
                error_msg = str(e)
                print(f"❌ [Web] Error: {error_msg}")
                
                # エラーの詳細を判定
                if "404" in error_msg or "Not Found" in error_msg:
                    print(f"[Web]   💀 404 Not Found - URL may be invalid")
                elif "401" in error_msg or "Authorization" in error_msg:
                    print(f"[Web]   🔐 Authorization Required - Check credentials")
                elif "403" in error_msg or "Forbidden" in error_msg:
                    print(f"[Web]   🚫 Forbidden - Access denied")
                elif "timeout" in error_msg.lower():
                    print(f"[Web]   ⏱️ Timeout - Server too slow or unresponsive")
                else:
                    print(f"[Web]   ⚠️ Unknown error")
                    import traceback
                    traceback.print_exc()
                
                self.failed_urls.add(current_url)
                
                # エラー情報を含めて結果に追加（マッチングから除外できるように）
                error_metadata = {
                    "url": current_url,
                    "title": f"取得失敗",
                    "text": "",
                    "screenshot_path": None,
                    "areas": [],
                    "screenshot_image": None,
                    "error": error_msg,  # エラーメッセージを記録
                    "depth": depth,
                    "parent_url": parent_url,
                    "fetch_time": time.time()
                }
                results.append(error_metadata)
                self.sitemap[current_url] = error_metadata
                continue
        
        print(f"\n{'='*60}")
        print(f"[Web] ✅ Crawling Complete")
        print(f"  Total Pages: {len(results)}")
        print(f"  Successful: {len(self.visited_urls)}")
        print(f"  Failed: {len(self.failed_urls)}")
        print(f"  Max Depth Reached: {max(r['depth'] for r in results if r.get('depth') is not None)}")
        print(f"{'='*60}\n")
        
        return results
    
    def _extract_links_from_scraper_result(self, url: str) -> List[str]:
        """
        WebScraperを使用してリンクを抽出（認証情報を引き継ぐ）
        
        Args:
            url: 対象URL
        
        Returns:
            抽出されたリンクのリスト
        """
        try:
            from playwright.sync_api import sync_playwright
            
            links = set()
            root_domain = urlparse(url).netloc
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                # コンテキスト設定（認証情報を含む）
                context_options = {
                    "viewport": {"width": 1920, "height": 1080},  # ✅ デスクトップ表示に統一
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                if self.username and self.password:
                    context_options["http_credentials"] = {
                        "username": self.username,
                        "password": self.password
                    }
                
                context = browser.new_context(**context_options)
                page = context.new_page()
                
                # Basic認証ヘッダーを設定
                if self.username and self.password:
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    page.set_extra_http_headers({
                        "Authorization": f"Basic {credentials}"
                    })
                
                try:
                    # ページにアクセス
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(0.3)  # 1.0s → 0.3s 短縮
                    
                    # 実際のページURLを取得 (リダイレクト後の正しいURL)
                    actual_url = page.url
                    # 末尾にスラッシュがない場合は追加（相対リンク解決の精度向上）
                    if not actual_url.endswith('/') and '.' not in actual_url.split('/')[-1]:
                        actual_url = actual_url + '/'
                    
                    # JavaScriptでリンクを取得（getAttribute使用で相対URLも正確に取得）
                    raw_links = page.evaluate("""
                        () => {
                            return Array.from(document.querySelectorAll('a[href]'))
                                .map(a => ({
                                    href: a.getAttribute('href'),
                                    text: a.textContent.trim().substring(0, 30)
                                }))
                                .filter(link => link.href && link.href.trim() !== '');
                        }
                    """)
                    
                    print(f"[Web]   🔗 Extracting from: {actual_url}")
                    print(f"[Web]   📋 Raw links found: {len(raw_links)}")
                    
                    # デバッグ: 最初の5件を表示
                    for i, link_data in enumerate(raw_links[:5]):
                        href = link_data.get('href', link_data) if isinstance(link_data, dict) else link_data
                        text = link_data.get('text', '')[:20] if isinstance(link_data, dict) else ''
                        print(f"[Web]     [{i+1}] {href} (\"{text}\")")
                    
                    # リンクを処理
                    for link_data in raw_links:
                        href = link_data.get('href', link_data) if isinstance(link_data, dict) else link_data
                        
                        try:
                            # javascript:やmailto:を除外
                            if href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                                continue
                            
                            # 絶対URLに変換 (actual_urlを使用して正確に解決)
                            absolute_url = urljoin(actual_url, href)
                            
                            # デバッグ: 変換結果を表示（最初の3件）
                            if len(links) < 3:
                                print(f"[Web]     ✓ {href} → {absolute_url}")
                            
                            # フラグメントを除去
                            absolute_url = absolute_url.split('#')[0]
                            
                            # URL検証
                            parsed = urlparse(absolute_url)
                            
                            # httpまたはhttpsのみ
                            if parsed.scheme not in ['http', 'https']:
                                continue
                            
                            # 同一ドメインのみ
                            if parsed.netloc != root_domain:
                                continue
                            
                            # 静的アセットを除外
                            if not self._is_static_asset(absolute_url):
                                links.add(absolute_url)
                        
                        except Exception as e:
                            print(f"[Web]   ⚠️ URL処理エラー ({href}): {e}")
                            continue
                    
                except Exception as e:
                    print(f"[Web]   ⚠️ ページアクセスエラー: {e}")
                
                finally:
                    context.close()
                    browser.close()
            
            return list(links)
            
        except Exception as e:
            print(f"⚠️ [Web] Link extraction error: {url} - {str(e)}")
            return []
    
    def _extract_links_from_page(self, url: str) -> List[str]:
        """
        リンク抽出（改善版を使用）
        
        Args:
            url: 対象URL
        
        Returns:
            抽出されたリンクのリスト
        """
        return self._extract_links_from_scraper_result(url)
    
    def _is_obvious_static_asset(self, url: str) -> bool:
        """
        明らかな静的アセットを高速判定（軽量版）
        """
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in ['.jpg', '.png', '.gif', '.css', '.js', '.pdf', '.zip'])
    
    def _extract_links(self, base_url: str, html_text: str) -> List[str]:
        """
        HTMLテキストからリンクを抽出（簡易版・レガシー）
        実際の実装では、BeautifulSoupなどを使うとより正確
        
        注意: このメソッドは非推奨です。_extract_links_from_page を使用してください。
        """
        import re
        
        # 簡易的なリンク抽出（href属性を探す）
        pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html_text, re.IGNORECASE)
        
        links = []
        for match in matches:
            # 相対URLを絶対URLに変換
            absolute_url = urljoin(base_url, match)
            
            # フラグメント（#）を除去
            absolute_url = absolute_url.split('#')[0]
            
            # 有効なURLかチェック
            parsed = urlparse(absolute_url)
            if parsed.scheme in ['http', 'https']:
                links.append(absolute_url)
        
        return links
    
    def get_statistics(self) -> dict:
        """クローリング統計情報とサイトマップを取得"""
        depth_distribution = {}
        for url, metadata in self.sitemap.items():
            depth = metadata.get('depth', 0)
            depth_distribution[depth] = depth_distribution.get(depth, 0) + 1
        
        return {
            "visited_count": len(self.visited_urls),
            "failed_count": len(self.failed_urls),
            "total_pages": len(self.sitemap),
            "depth_distribution": depth_distribution,
            "visited_urls": list(self.visited_urls),
            "failed_urls": list(self.failed_urls),
            "sitemap": self.sitemap  # 完全なサイトマップ情報
        }
    
    def get_sitemap_tree(self) -> Dict:
        """
        サイトマップをツリー構造で取得（階層的表示用）
        
        Returns:
            階層構造のサイトマップ
        """
        tree = {}
        
        # depthでソート
        sorted_pages = sorted(
            self.sitemap.items(),
            key=lambda x: x[1].get('depth', 0)
        )
        
        for url, metadata in sorted_pages:
            depth = metadata.get('depth', 0)
            parent = metadata.get('parent_url')
            
            if depth not in tree:
                tree[depth] = []
            
            tree[depth].append({
                'url': url,
                'title': metadata.get('title', ''),
                'parent_url': parent,
                'has_error': metadata.get('error') is not None
            })
        
        return tree

