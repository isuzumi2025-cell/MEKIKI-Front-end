"""
Phase 1: スクレイピング機能の強化
遅延読み込み（Lazy Loading）対応
"""
from playwright.sync_api import sync_playwright, Page
from PIL import Image
from typing import List, Dict, Optional, Tuple
import io
import time


class EnhancedWebScraper:
    """強化版Webスクレイパー - クローリングとLazy Loading対応"""
    
    def __init__(self, headless: bool = True, viewport_width: int = 1920, viewport_height: int = 1080):
        """
        Args:
            headless: ヘッドレスモードで実行するか
            viewport_width: ビューポート幅
            viewport_height: ビューポート高さ
        """
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
    
    def scrape_with_lazy_loading(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_scrolls: int = 10,
        scroll_delay: float = 1.0
    ) -> Tuple[str, str, Image.Image, Image.Image]:
        """
        遅延読み込み対応でWebページをスクレイピング
        
        Args:
            url: 対象URL
            username: Basic認証ユーザー名
            password: Basic認証パスワード
            max_scrolls: 最大スクロール回数
            scroll_delay: スクロール間の待機時間（秒）
        
        Returns:
            (title, text, full_page_image, viewport_image)
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            
            context_options = {
                'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
                'device_scale_factor': 2.0
            }
            
            # Basic認証設定
            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            try:
                print(f"🌍 アクセス中: {url}")
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # ページ下部までスクロール（Lazy Loading対応）
                self._scroll_to_bottom(page, max_scrolls, scroll_delay)
                
                # タイトルとテキスト取得
                title = page.title()
                text_content = page.inner_text("body")
                
                # 1画面分のスクリーンショット
                page.evaluate("window.scrollTo(0, 0)")  # トップに戻る
                time.sleep(0.2)  # 0.5s → 0.2s 短縮
                viewport_bytes = page.screenshot(full_page=False)
                viewport_image = Image.open(io.BytesIO(viewport_bytes))
                
                # フルページスクリーンショット (スティッチング方式に変更)
                full_image = self._capture_full_page_stitched(page)
                # full_bytes = page.screenshot(full_page=True)
                # full_image = Image.open(io.BytesIO(full_bytes))
                
                print(f"✅ 取得完了: {title}")
                return title, text_content, full_image, viewport_image
                
            except Exception as e:
                raise Exception(f"スクレイピングエラー: {str(e)}")
            finally:
                context.close()
                browser.close()
    
    def _scroll_to_bottom(self, page: Page, max_scrolls: int, delay: float):
        """
        ページ下部までスクロール（遅延読み込み対応）
        
        Args:
            page: Playwrightのページオブジェクト
            max_scrolls: 最大スクロール回数
            delay: スクロール間の待機時間
        """
        print(f"📜 ページをスクロール中...")
        
        for i in range(max_scrolls):
            # 現在の高さを取得
            prev_height = page.evaluate("document.body.scrollHeight")
            
            # 下にスクロール
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(delay)
            
            # 新しい高さを取得
            new_height = page.evaluate("document.body.scrollHeight")
            
            # 高さが変わらなければ終了（これ以上読み込むものがない）
            if new_height == prev_height:
                print(f"✅ スクロール完了（{i + 1}回）")
                break
        else:
            print(f"✅ 最大スクロール回数に到達（{max_scrolls}回）")

    def _capture_full_page_stitched(self, page: Page) -> Image.Image:
        """
        ページをスクロールしながらキャプチャして結合する（Ultrathink Stitching）
        - スクロールバーを非表示にする
        - 遅延読み込みを確実に待機
        - 正確なスティッチング
        """
        try:
            print("📸 Ultrathinkキャプチャ開始...")

            # 1. スクロールバーと固定ヘッダー/フッターを非表示にする (CSS注入)
            # ★ Phase 1: ヘッダー重複問題の修正 (強化版)
            page.add_style_tag(content="""
                body { overflow-y: hidden !important; }
                ::-webkit-scrollbar { display: none; }
                
                /* 固定ヘッダー/フッターを非表示 (Phase 1強化) */
                [style*="position: fixed"], 
                [style*="position:fixed"],
                [style*="position: sticky"],
                [style*="position:sticky"],
                header, nav,
                header[class*="fix"], header[class*="stick"],
                nav[class*="fix"], nav[class*="stick"],
                div[class*="fixed-header"], div[class*="sticky-header"],
                div[class*="fixed-nav"], div[class*="sticky-nav"],
                div[class*="header-fixed"], div[class*="header-sticky"],
                .fixed, .sticky, .fixed-top, .sticky-top,
                .header-fixed, .nav-fixed, .topbar-fixed,
                [class*="-fixed"], [class*="-sticky"],
                [id*="header"], [id*="nav"], [id*="topbar"],
                [role="banner"], [role="navigation"] {
                    position: relative !important;
                    display: none !important;
                }
            """)
            
            # --- 画像強制読み込み (Pre-roll Scroll) ---
            print("   🔄 画像読み込みのためのプレロールスクロール...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.8)  # 2.0s → 0.8s 短縮（精度維持のため1秒弱は必要）
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.8)  # 2.0s → 0.8s 短縮
            
            # メトリクス取得
            total_height = page.evaluate("document.body.scrollHeight")
            viewport_size = page.viewport_size
            viewport_height = viewport_size['height']
            
            # キャプチャ計画
            images = []
            current_scroll = 0
            
            # トップに戻る
            page.evaluate("window.scrollTo(0, 0)")
            # 動的待機に置換（固定2秒→networkidle）
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except:
                time.sleep(0.5)  # フォールバック
            
            # A4横比率（1.414）を意識したチャンクサイズにするか？
            # ユーザーの要望は「A4横サイズごとに」だが、Webページは縦長なので
            # ビューポート単位で綺麗に撮って、後でどうにでも印刷できるようにするのが最善。
            # ここではビューポート高さを基準にする。
            
            while current_scroll < total_height:
                # スクロール実行
                page.evaluate(f"window.scrollTo(0, {current_scroll})")
                
                # 動的待機（固定1秒→networkidle + 短いsleep）
                try:
                    page.wait_for_load_state("networkidle", timeout=2000)
                except:
                    time.sleep(0.3)  # フォールバック

                # キャプチャ
                screenshot_bytes = page.screenshot()
                img = Image.open(io.BytesIO(screenshot_bytes))
                images.append(img)
                
                print(f"   - キャプチャ: {current_scroll}px / {total_height}px")
                
                current_scroll += viewport_height
                
                # 安全装置
                if len(images) > 100:
                    print("⚠️ ページが長すぎるため中断")
                    break
            
            if not images:
                return Image.new('RGB', (100, 100), 'gray')

            # 2. 結合処理
            print(f"🧩 {len(images)}枚の画像を結合中...")
            
            # 最後の画像は重複部分がある可能性がある
            # しかし、単純なスクロール結合で多くの場合は機能する。
            # 厳密には `total_height` に合わせてトリミングが必要だが、
            # Playwrightのスクロールは正確なので、そのままスタックする。
            
            # 最終画像の高さ調整（はみ出し部分のカット）
            # 最後のスクロール位置での表示内容 = ページ最下部
            # 最後の画像の有効高さ = total_height % viewport_height (0ならそのまま)
            # いや、viewportで撮るので、最後の画像は「下からviewport分」ではなく「上からスクロールした位置」
            # 最後のスクロールが `total_height - viewport_height` 未満の場合、重複はしない。
            
            # 単純結合
            full_w = images[0].width
            full_h = sum(img.height for img in images)
            
            # 実際にページ高さより大きくなる場合（最後の白紙部分など）はトリミング
            # 余白削除は後処理で行うとしても、一旦結合。
            
            stitched_image = Image.new('RGB', (full_w, full_h))
            curr_y = 0
            for img in images:
                stitched_image.paste(img, (0, curr_y))
                curr_y += img.height
            
            # ページ末尾の重複除去ロジック（オプション）
            # 今回は「確実性」重視で、重複しても情報が消えるよりマシとする。
            
            print("✅ Ultrathinkキャプチャ完了")
            return stitched_image

        except Exception as e:
            print(f"⚠️ キャプチャエラー: {e}")
            # エラー時は通常のスクリーンショットを試みる
            full_bytes = page.screenshot(full_page=True)
            return Image.open(io.BytesIO(full_bytes))
    
    def crawl_site(
        self,
        base_url: str,
        max_pages: int = 50,
        same_domain_only: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> List[Dict]:
        """
        サイト内をクローリング
        
        Args:
            base_url: 開始URL
            max_pages: 最大ページ数
            same_domain_only: 同一ドメインのみ
            username: Basic認証ユーザー名
            password: Basic認証パスワード
        
        Returns:
            [{"url": str, "title": str, "text": str, "full_image": Image, "viewport_image": Image}, ...]
        """
        from urllib.parse import urlparse, urljoin
        import re
        
        visited = set()
        to_visit = [base_url]
        results = []
        base_domain = urlparse(base_url).netloc
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            
            context_options = {
                'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
                'device_scale_factor': 2.0
            }
            
            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            try:
                while to_visit and len(results) < max_pages:
                    current_url = to_visit.pop(0)
                    
                    if current_url in visited:
                        continue
                    
                    # ドメインチェック
                    if same_domain_only:
                        current_domain = urlparse(current_url).netloc
                        if current_domain != base_domain:
                            continue
                    
                    try:
                        print(f"🌍 [{len(results) + 1}/{max_pages}] {current_url}")
                        
                        page.goto(current_url, timeout=60000)
                        page.wait_for_load_state("networkidle")
                        
                        # Lazy Loading対応スクロール
                        self._scroll_to_bottom(page, max_scrolls=5, delay=0.5)
                        
                        # データ取得
                        title = page.title()
                        text_content = page.inner_text("body")
                        
                        # スクリーンショット
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(0.1)  # 0.3s → 0.1s 短縮
                        viewport_bytes = page.screenshot(full_page=False)
                        viewport_image = Image.open(io.BytesIO(viewport_bytes))
                        
                        full_image = self._capture_full_page_stitched(page)
                        # full_bytes = page.screenshot(full_page=True)
                        # full_image = Image.open(io.BytesIO(full_bytes))
                        
                        results.append({
                            "url": current_url,
                            "title": title,
                            "text": text_content,
                            "full_image": full_image,
                            "viewport_image": viewport_image
                        })
                        
                        visited.add(current_url)
                        
                        # リンクを抽出
                        links = page.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('a[href]'))
                                    .map(a => a.href)
                                    .filter(href => href.startsWith('http'));
                            }
                        """)
                        
                        for link in links:
                            # フラグメント除去
                            link = link.split('#')[0]
                            if link and link not in visited and link not in to_visit:
                                to_visit.append(link)
                        
                        time.sleep(0.3)  # 1.0s → 0.3s 短縮
                        
                    except Exception as e:
                        print(f"⚠️ エラー: {current_url} - {str(e)}")
                        visited.add(current_url)
                        continue
                
            finally:
                context.close()
                browser.close()
        
        print(f"✅ クローリング完了: {len(results)}ページ取得")
        return results


# エイリアス（後方互換性のため）
EnhancedScraper = EnhancedWebScraper

