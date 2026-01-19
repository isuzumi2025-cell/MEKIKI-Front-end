import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import sys
import io
from pathlib import Path
from typing import Optional, Dict, List
import threading

# Windows UTF-8対応
if sys.platform == 'win32' and not isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except AttributeError:
        pass

# PIL画像サイズ制限を解除
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

# プロジェクトモジュール
try:
    from app.gui.navigation import NavigationPanel
    from app.gui.macro_view import MacroView
    from app.gui.micro_view import MicroView
    from app.gui.dialogs.project_dialog import ProjectDialog
    from app.core.ocr_engine import OCREngine
    from app.core.analyzer import ContentAnalyzer
except ImportError as e:
    print(f"⚠️ インポートエラー: {e}")
    # 相対インポート
    from .navigation import NavigationPanel
    from .macro_view import MacroView
    from .micro_view import MicroView
    from .dialogs.project_dialog import ProjectDialog

# テーマ設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    """
    メインウィンドウ
    NavigationPanel統合、新規プロジェクト機能搭載
    """
    
    def __init__(self):
        super().__init__()

        # ウィンドウ設定
        self.title("OCR 比較ツール - プロジェクトマネージャー")
        self.geometry("1600x900")
        
        # コアエンジン
        self.ocr_engine: Optional[OCREngine] = None
        self.analyzer: Optional[ContentAnalyzer] = None
        
        # ビュー管理
        self.current_view = None
        self.macro_view: Optional[MacroView] = None
        self.micro_view: Optional[MicroView] = None
        
        # UI構築
        self._setup_ui()
        
        # エンジン初期化
        self._initialize_engines()

    def _setup_ui(self):
        """UI構築"""
        # メインコンテナ（PanedWindow使用）
        self.main_container = tk.PanedWindow(
            self,
            orient="horizontal",
            bg="#2B2B2B",
            sashwidth=4
        )
        self.main_container.pack(fill="both", expand=True)
        
        # 左: ナビゲーションパネル
        nav_callbacks = {
            "new_project": self.open_new_project_dialog,
            "show_macro_view": self.show_macro_view,
            "crawl_web": self.crawl_web,
            "load_pdfs": self.load_pdfs,
            "match_all": self.match_all,
            "run_ocr": self.run_ocr,
            "export_excel": self.export_excel,
            "save_project": self.save_project,
            "load_project": self.load_project
        }
        
        self.nav_panel = NavigationPanel(
            self.main_container,
            callbacks=nav_callbacks,
            width=220
        )
        self.main_container.add(self.nav_panel, width=220)
        
        # 右: コンテンツエリア
        self.content_area = ctk.CTkFrame(self.main_container)
        self.main_container.add(self.content_area)
        
        # 初期ビュー: ウェルカム画面
        self._show_welcome()
    
    def _initialize_engines(self):
        """エンジンを初期化"""
        try:
            # OCRエンジン
            self.ocr_engine = OCREngine(credentials_path="credentials.json")
            
            # Analyzer
            self.analyzer = ContentAnalyzer(ocr_engine=self.ocr_engine)
            
            print("✅ エンジン初期化完了")
            
        except Exception as e:
            print(f"⚠️ エンジン初期化エラー: {str(e)}")
            # OCRなしでも動作可能
            self.analyzer = ContentAnalyzer()
    
    def _show_welcome(self):
        """ウェルカム画面を表示"""
        # 既存のビューをクリア
        if self.current_view:
            self.current_view.pack_forget()
        
        welcome = ctk.CTkFrame(self.content_area, fg_color="transparent")
        welcome.pack(fill="both", expand=True)
        
        # 中央にメッセージ
        center = ctk.CTkFrame(welcome, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(
            center,
            text="🚀 OCR 比較ツール",
            font=("Meiryo", 32, "bold"),
            text_color="#4CAF50"
        ).pack(pady=20)
        
        ctk.CTkLabel(
            center,
            text="Google Cloud Vision API統合版",
            font=("Meiryo", 14),
            text_color="gray"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            center,
            text="左のナビゲーションから「➕ 新規プロジェクト」を選択してください",
            font=("Meiryo", 12),
            text_color="gray"
        ).pack(pady=20)
        
        # クイックスタートボタン
        button_frame = ctk.CTkFrame(center, fg_color="transparent")
        button_frame.pack(pady=30)
        
        ctk.CTkButton(
            button_frame,
            text="➕ 新規プロジェクト",
            command=self.open_new_project_dialog,
            width=220,
            height=60,
            font=("Meiryo", 14, "bold"),
            fg_color="#FF6F00"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            button_frame,
            text="🗺️ 全体マップ",
            command=self.show_macro_view,
            width=220,
            height=60,
            font=("Meiryo", 14, "bold"),
            fg_color="#4CAF50"
        ).pack(side="left", padx=10)
        
        self.current_view = welcome

    def show_macro_view(self):
        """全体マップを表示"""
        # 既存のビューをクリア
        if self.current_view:
            self.current_view.pack_forget()
        
        # MacroViewを常に再作成（最新データを反映）
        if self.macro_view:
            self.macro_view.destroy()
        
        self.macro_view = MacroView(
            self.content_area,
            analyzer=self.analyzer,
            on_detail_click=self._open_micro_view
        )
        
        self.macro_view.pack(fill="both", expand=True)
        
        # データを読み込み
        if self.analyzer:
            print(f"[MacroView] Analyzerデータ読み込み開始")
            if hasattr(self.analyzer, 'web_pages') and hasattr(self.analyzer, 'pdf_pages'):
                print(f"  Web Pages: {len(self.analyzer.web_pages)}")
                print(f"  PDF Pages: {len(self.analyzer.pdf_pages)}")
            print(f"  Web Areas: {len(self.analyzer.web_areas)}")
            print(f"  PDF Areas: {len(self.analyzer.pdf_areas)}")
            print(f"  Matched Pairs: {len(self.analyzer.matched_pairs)}")
            self.macro_view.load_from_analyzer()
        
        self.current_view = self.macro_view
        print("🗺️ 全体マップビューを表示")
    
    def show_micro_view(self, matched_pair=None):
        """詳細比較画面を表示"""
        print(f"[MainWindow] MicroViewに遷移")
        
        # 既存のビューをクリア
        if self.current_view:
            self.current_view.pack_forget()
        
        # MicroViewを毎回再作成（最新データを反映）
        if self.micro_view:
            self.micro_view.destroy()
        
        from app.gui.micro_view import MicroView
        self.micro_view = MicroView(
            self.content_area,
            on_back=self.show_macro_view,
            matched_pair=matched_pair
        )
        
        self.micro_view.pack(fill="both", expand=True)
        self.current_view = self.micro_view
        
        if matched_pair:
            web_title = matched_pair.web_page.title[:30] if hasattr(matched_pair, 'web_page') else "Web"
            pdf_title = f"PDF P{matched_pair.pdf_page.page_num}" if hasattr(matched_pair, 'pdf_page') else "PDF"
            print(f"🔬 詳細比較ビューを表示: {web_title} ⇔ {pdf_title}")
    
    def _open_micro_view(self, matched_pair):
        """MicroViewを開く（MacroViewからのコールバック）"""
        self.show_micro_view(matched_pair)
    
    # ===== 新規プロジェクト機能 =====
    
    def open_new_project_dialog(self):
        """新規プロジェクトダイアログを開く"""
        dialog = ProjectDialog(
            self,
            on_start=self.start_analysis
        )
        
        # ダイアログを待機
        self.wait_window(dialog)
    
    def start_analysis(self, config: Dict):
        """分析を開始"""
        print("=" * 60)
        print("🚀 分析開始")
        print("=" * 60)
        print(f"URL: {config['url']}")
        print(f"深さ: {config['depth']}")
        print(f"最大ページ数: {config['max_pages']}")
        print(f"PDF: {config.get('pdf_file') or config.get('pdf_folder')}")
        print(f"OCR: {'有効' if config['use_ocr'] else '無効'}")
        print(f"閾値: {config['threshold']:.0%}")
        if config.get('use_auth'):
            print(f"Basic認証: 有効（ユーザー: {config.get('auth_user')}）")
            print(f"パスワード: {'*' * len(config.get('auth_pass', ''))}")
        else:
            print(f"Basic認証: 無効 (use_auth={config.get('use_auth')})")
        print("=" * 60)
        
        # ローディング画面を表示
        self._show_loading_screen()
        
        # プログレスバーを表示
        self.nav_panel.show_progress()
        
        # バックグラウンドで分析実行
        def _run_analysis():
            try:
                # Analyzerをクリア
                if self.analyzer:
                    self.analyzer.clear_all()
                
                # Step 1: Webクロール
                self.after(0, lambda: self._update_loading_message("🌐 Webページをクロール中..."))
                web_results = self._crawl_web_pages(
                    config['url'],
                    config['depth'],
                    config['max_pages'],
                    username=config.get('auth_user') if config.get('use_auth') else None,
                    password=config.get('auth_pass') if config.get('use_auth') else None
                )
                
                # Step 2: PDF読込
                self.after(0, lambda: self._update_loading_message("📁 PDFを読み込み中..."))
                pdf_results = self._load_pdf_pages(
                    config.get('pdf_file'),
                    config.get('pdf_folder')
                )
                
                # Step 3: Analyzerにデータを追加
                self.after(0, lambda: self._update_loading_message("📊 データを登録中..."))
                print(f"\n{'='*60}")
                print(f"[Analyzer] データ登録開始")
                print(f"{'='*60}")
                
                if self.analyzer:
                    # Webページデータを追加（PageData形式）
                    for i, web_data in enumerate(web_results):
                        from app.core.analyzer import PageData, DetectedArea
                        
                        # PageDataを作成
                        page = PageData(
                            source_type="web",
                            source_id=web_data.get('url', ''),
                            title=web_data.get('title', ''),
                            text=web_data.get('text', ''),
                            image=web_data.get('screenshot_image'),
                            image_path=web_data.get('screenshot_path'),
                            error=web_data.get('error')
                        )
                        
                        # エラーページはスキップ
                        if page.error:
                            print(f"[Analyzer] Web {i+1}: エラーのためスキップ - {page.error}")
                            continue
                        
                        self.analyzer.web_pages.append(page)
                        
                        # 後方互換性のため、エリアも追加
                        if page.image:
                            img_width, img_height = page.image.size
                        else:
                            img_width, img_height = 1280, 800
                        
                        area = DetectedArea(
                            text=page.text,
                            bbox=[0, 0, img_width, img_height],
                            confidence=1.0,
                            source_type="web",
                            source_id=page.source_id
                        )
                        self.analyzer.web_areas.append(area)
                    
                    print(f"[Analyzer] ✅ Webページ登録完了: {len(self.analyzer.web_pages)} ページ")
                    
                    # PDFページデータを追加（PageData形式）
                    for i, pdf_data in enumerate(pdf_results):
                        from app.core.analyzer import PageData, DetectedArea
                        
                        # PageDataを作成
                        page = PageData(
                            source_type="pdf",
                            source_id=pdf_data.get('filename', ''),
                            page_num=pdf_data.get('page_num', 0),
                            title=f"Page {pdf_data.get('page_num', 0)}",
                            text=pdf_data.get('text', ''),
                            image=pdf_data.get('page_image'),
                            image_path=pdf_data.get('image_path')
                        )
                        
                        self.analyzer.pdf_pages.append(page)
                        
                        # 後方互換性のため、エリアも追加
                        if page.image:
                            img_width, img_height = page.image.size
                        else:
                            img_width, img_height = 2480, 3508
                        
                        area = DetectedArea(
                            text=page.text,
                            bbox=[0, 0, img_width, img_height],
                            confidence=1.0,
                            source_type="pdf",
                            source_id=page.source_id,
                            page_num=page.page_num
                        )
                        self.analyzer.pdf_areas.append(area)
                    
                    print(f"[Analyzer] ✅ PDFページ登録完了: {len(self.analyzer.pdf_pages)} ページ")
                    print(f"{'='*60}\n")
                
                # Step 4: OCR実行（オプション）
                if config['use_ocr'] and self.ocr_engine:
                    self.after(0, lambda: self._update_loading_message("🔍 OCR実行中..."))
                    # TODO: OCR処理
                
                # Step 5: マッチング
                self.after(0, lambda: self._update_loading_message("⚡ マッチング実行中..."))
                pairs = []
                if self.analyzer:
                    pairs = self.analyzer.compute_auto_matches(
                        threshold=0.05,  # 業務用: 低閾値
                        method="hybrid",
                        force_match=True  # 強制マッチングモード
                    )
                
                # Step 6: 完了
                self.after(0, lambda: self._on_analysis_complete(
                    len(web_results),
                    len(pdf_results),
                    len(pairs)
                ))
                
            except Exception as e:
                self.after(0, lambda: self._on_analysis_error(e))
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        # バックグラウンドで実行
        threading.Thread(target=_run_analysis, daemon=True).start()
    
    def _show_loading_screen(self):
        """ローディング画面を表示"""
        # 既存のビューをクリア
        if self.current_view:
            self.current_view.pack_forget()
        
        loading = ctk.CTkFrame(self.content_area, fg_color="transparent")
        loading.pack(fill="both", expand=True)
        
        # 中央にメッセージ
        center = ctk.CTkFrame(loading, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(
            center,
            text="🔄 処理中...",
            font=("Meiryo", 24, "bold"),
            text_color="#4CAF50"
        ).pack(pady=20)
        
        self.loading_message = ctk.CTkLabel(
            center,
            text="初期化中...",
            font=("Meiryo", 12),
            text_color="gray"
        )
        self.loading_message.pack(pady=10)
        
        # プログレスバー
        progress = ctk.CTkProgressBar(
            center,
            mode='indeterminate',
            width=400,
            height=20
        )
        progress.pack(pady=20)
        progress.start()
        
        self.current_view = loading
    
    def _update_loading_message(self, message: str):
        """ローディングメッセージを更新"""
        if hasattr(self, 'loading_message'):
            self.loading_message.configure(text=message)
            print(f"  {message}")
    
    def _crawl_web_pages(
        self,
        url: str,
        depth: int,
        max_pages: int,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> List:
        """Webページをクロール"""
        try:
            print(f"=" * 60)
            print(f"📡 [Web] Crawl Start")
            print(f"  URL: {url}")
            print(f"  Depth: {depth}")
            print(f"  Max Pages: {max_pages}")
            if username:
                print(f"  Basic Auth: Enabled (User: {username})")
            print(f"=" * 60)
            
            # まずWebCrawlerを使用（標準）
            try:
                from app.core.crawler import WebCrawler
                
                crawler = WebCrawler(
                    max_pages=max_pages,
                    max_depth=depth,
                    delay=2.0,  # 少し長めの遅延を設定
                    username=username,
                    password=password
                )
                
                results = crawler.crawl(root_url=url)
                
                print(f"\n" + "=" * 60)
                print(f"✅ [Web] Crawl Complete: {len(results)} pages")
                for i, result in enumerate(results, start=1):
                    error_status = f" [ERROR: {result.get('error')}]" if result.get('error') else ""
                    print(f"  [{i}] {result.get('url')}{error_status}")
                print(f"=" * 60 + "\n")
                
                return results
                
            except ImportError:
                # WebCrawlerが使えない場合はEnhancedWebScraperを試す
                print("⚠️ WebCrawlerが使用できません。EnhancedWebScraperを試します...")
                from app.core.enhanced_scraper import EnhancedWebScraper
                
                scraper = EnhancedWebScraper()
                results = scraper.crawl_site(
                    base_url=url,
                    max_depth=depth,
                    max_pages=max_pages,
                    username=username,
                    password=password
                )
                
                print(f"\n✅ [Web] Crawl Complete: {len(results)} pages\n")
                
                return results
            
        except Exception as e:
            print(f"\n❌ [Web] Crawl Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _load_pdf_pages(self, pdf_file: Optional[str], pdf_folder: Optional[str]) -> List:
        """PDFページを読み込み"""
        try:
            from app.utils.pdf_loader import PDFLoader
            
            print(f"=" * 60)
            print(f"📄 [PDF] Load Start")
            if pdf_file:
                print(f"  File: {pdf_file}")
            elif pdf_folder:
                print(f"  Folder: {pdf_folder}")
            print(f"=" * 60)
            
            loader = PDFLoader()
            results = []
            
            if pdf_file:
                # 単一ファイル
                pages = loader.load_pdf(pdf_file)
                results.extend(pages)
                
                print(f"\n" + "=" * 60)
                print(f"✅ [PDF] Load Complete: {len(pages)} pages")
                for i, page in enumerate(pages, start=1):
                    text_len = len(page.get('text', ''))
                    areas_count = len(page.get('areas', []))
                    print(f"  [Page {i}] {text_len} chars, {areas_count} areas")
                print(f"=" * 60 + "\n")
                
            elif pdf_folder:
                # フォルダ内の全PDF
                pages = loader.load_pdfs_from_folder(pdf_folder)
                results.extend(pages)
                
                print(f"\n" + "=" * 60)
                print(f"✅ [PDF] Load Complete: {len(pages)} pages from folder")
                print(f"=" * 60 + "\n")
            
            return results
            
        except Exception as e:
            print(f"\n❌ [PDF] Load Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _on_analysis_complete(self, web_count: int, pdf_count: int, pair_count: int):
        """分析完了時の処理"""
        print("=" * 60)
        print("✅ 分析完了")
        print(f"  Web: {web_count} ページ")
        print(f"  PDF: {pdf_count} ページ")
        print(f"  ペア: {pair_count} 件")
        print("=" * 60)
        
        # 完了メッセージ
        messagebox.showinfo(
            "完了",
            f"✅ 分析が完了しました\n\n"
            f"Web: {web_count} ページ\n"
            f"PDF: {pdf_count} ページ\n"
            f"マッチング: {pair_count} ペア"
        )
        
        # 全体マップを表示
        self.show_macro_view()
    
    def _on_analysis_error(self, error: Exception):
        """分析エラー時の処理"""
        print(f"❌ 分析エラー: {str(error)}")
        import traceback
        traceback.print_exc()
        
        messagebox.showerror(
            "エラー",
            f"分析中にエラーが発生しました:\n\n{str(error)}"
        )
        
        # ウェルカム画面に戻る
        self._show_welcome()
    
    # ===== その他の機能 =====
    
    def crawl_web(self):
        """Webクロール"""
        messagebox.showinfo(
            "Web一括クロール",
            "「➕ 新規プロジェクト」から実行してください"
        )
    
    def load_pdfs(self):
        """PDF一括読込"""
        messagebox.showinfo(
            "PDF一括読込",
            "「➕ 新規プロジェクト」から実行してください"
        )
    
    def match_all(self):
        """一括マッチング"""
        if not self.analyzer or not self.analyzer.web_areas or not self.analyzer.pdf_areas:
            messagebox.showwarning(
                "警告",
                "データがありません。\n先に「➕ 新規プロジェクト」から分析を実行してください。"
            )
            return
        
        # プログレス表示
        self.nav_panel.show_progress()
        
        def _run_matching():
            try:
                pairs = self.analyzer.compute_auto_matches(
                    threshold=0.05,  # 業務用: 低閾値
                    method="hybrid",
                    force_match=True  # 強制マッチングモード
                )
                self.after(0, lambda: self._on_matching_complete(pairs))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        threading.Thread(target=_run_matching, daemon=True).start()
    
    def _on_matching_complete(self, pairs):
        """マッチング完了"""
        messagebox.showinfo(
            "完了",
            f"✅ マッチングが完了しました\n\n{len(pairs)} ペアが見つかりました"
        )
        
        if self.macro_view:
            self.macro_view.refresh_canvas()
    
    def run_ocr(self):
        """OCR実行"""
        messagebox.showinfo("OCR実行", "この機能は実装予定です")
    
    def export_excel(self):
        """Excel出力"""
        messagebox.showinfo("Excel出力", "この機能は実装予定です")
    
    def save_project(self):
        """プロジェクト保存"""
        messagebox.showinfo("プロジェクト保存", "この機能は実装予定です")
    
    def load_project(self):
        """プロジェクト読込"""
        messagebox.showinfo("プロジェクト読込", "この機能は実装予定です")


# アプリケーション起動
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 OCR 比較ツール 起動中...")
    print("=" * 60)
    
    app = MainWindow()
    app.mainloop()