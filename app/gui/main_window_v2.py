"""
Main Window V2
新しいアーキテクチャに対応したメインウィンドウ
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import io
from pathlib import Path
from typing import Optional, Dict, List
import threading

# Windows UTF-8対応（既に設定されていない場合のみ）
if sys.platform == 'win32' and not isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except AttributeError:
        pass  # 既にラップされている場合はスキップ

# PIL画像サイズ制限を解除
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

# プロジェクトモジュール
# プロジェクトモジュール
from app.core.gemini_ocr import GeminiOCREngine
from app.core.analyzer import ContentAnalyzer
from app.gui.macro_view import MacroView
from app.gui.micro_view import MicroView
from app.gui.navigation import NavigationPanel
from app.gui.sdk.keyboard_manager import KeyboardManager


# デザイン設定 (これらはMainWindowの__init__に移動)
# ctk.set_appearance_mode("Dark")
# ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    """
    メインウィンドウ (GUI V2)
    - 左右分割レイアウト
    - NavigationPanel (左側)
    - MacroView / MicroView (右側)
    """
    
    def __init__(self):
        super().__init__()
        
        self.title("MEKIKI Ver2 (Genius Edition)")
        self.geometry("1600x900")
        
        # テーマ設定
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # コアエンジン
        self.ocr_engine: Optional[GeminiOCREngine] = None
        self.analyzer: Optional[ContentAnalyzer] = None
        
        # ビュー
        self.current_view = None
        self.macro_view: Optional[MacroView] = None

        self._setup_ui()
        self._initialize_engines()
        self._setup_keyboard_shortcuts()
    
    def _setup_ui(self):
        """UI構築"""
        # メインコンテナ（Grid Layout）
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 左: ナビゲーションパネル (Fixed Width)
        self.nav_container = ctk.CTkFrame(
            self,
            width=260,
            corner_radius=0, # Sidebar style
            fg_color=("#F0F0F0", "#1E1E1E") # Light/Dark adaptation
        )
        self.nav_container.grid(row=0, column=0, sticky="nsew")
        self.nav_container.grid_propagate(False) # 固定幅
        
        nav_callbacks = {
            "new_project": self.new_project,
            "show_macro_view": self.show_macro_view,
            "crawl_web": self.crawl_web,
            "load_pdfs": self.load_pdfs,
            "match_all": self.match_all,
            "run_ocr": self.run_ocr,
            "export_excel": self.export_excel,
            "save_project": self.save_project,
            "load_project": self.load_project,
            "open_settings": self.open_settings
        }
        
        self.nav_panel = NavigationPanel(
            self.nav_container,
            callbacks=nav_callbacks,
            width=260
        )
        self.nav_panel.pack(fill="both", expand=True)
        
        # 右: コンテンツエリア
        self.content_area = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color="transparent" # 背景色をMainに合わせる
        )
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # 初期ビュー: ウェルカム画面
        self._show_welcome()
    
    def _initialize_engines(self):
        """エンジンを初期化"""
        try:
            # OCRエンジン（Gemini）
            self.ocr_engine = GeminiOCREngine()
            if not self.ocr_engine.initialize():
                print("⚠️ Geminiエンジンの初期化に失敗しました")
                # 失敗しても続行（APIキーがない場合など）
            
            # Analyzerを作成
            self.analyzer = ContentAnalyzer()
            self.analyzer.ocr_engine = self.ocr_engine # Analyzerにエンジンを渡す
            
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
            text="🚀 MEKIKI Ver2",
            font=("Meiryo", 32, "bold"),
            text_color="#4CAF50"
        ).pack(pady=20)
        
        ctk.CTkLabel(
            center,
            text="Genius Edition - Gemini Integration",
            font=("Meiryo", 14),
            text_color="gray"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            center,
            text="左のナビゲーションから操作を選択してください",
            font=("Meiryo", 12),
            text_color="gray"
        ).pack(pady=20)
        
        # クイックスタートボタン
        button_frame = ctk.CTkFrame(center, fg_color="transparent")
        button_frame.pack(pady=30)
        
        ctk.CTkButton(
            button_frame,
            text="🗺️ 全体マップを表示",
            command=self.show_macro_view,
            width=200,
            height=50,
            font=("Meiryo", 12, "bold"),
            fg_color="#4CAF50"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            button_frame,
            text="🌐 Webクロール開始",
            command=self.crawl_web,
            width=200,
            height=50,
            font=("Meiryo", 12, "bold"),
            fg_color="#E08E00"
        ).pack(side="left", padx=10)
        
        self.current_view = welcome

    # ... (skipping unchanged methods) ...

    def load_pdfs(self):
        """PDF一括読込を実行"""
        file_paths = filedialog.askopenfilenames(
            title="PDFまたは画像を選択",
            filetypes=[
                ("PDF & 画像", "*.pdf *.png *.jpg *.jpeg *.bmp"),
                ("PDFファイル", "*.pdf"),
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp")
            ]
        )
        
        if not file_paths:
            return
            
        # プログレス表示
        self.nav_panel.show_progress()
        
        def _run_load():
            try:
                from app.utils.pdf_loader import PDFLoader
                # from app.core.analyzer import DetectedArea # Geminiが生成するので不要
                
                loader = PDFLoader()
                total_files = len(file_paths)
                loaded_count = 0
                
                for i, file_path in enumerate(file_paths, 1):
                    self.after(0, lambda: self._update_loading_message(f"読み込み中 ({i}/{total_files}): {Path(file_path).name}"))
                    
                    if file_path.lower().endswith('.pdf'):
                        # PDF読み込み (PyMuPDFで画像化)
                        results = loader.load_pdf(file_path)
                        for page_res in results:
                            # Analyzerに追加 (GeminiにOCRを委譲)
                            self.analyzer.load_page(
                                image_path=None, 
                                source_type="pdf",
                                source_id=Path(file_path).name,
                                page_num=page_res['page_num'],
                                title=f"Page {page_res['page_num']}",
                                image=page_res['page_image'],
                                areas=None # ここでNoneを渡すと、Analyze->Geminiが走る
                            )
                        loaded_count += len(results)
                        
                    else:
                        # 画像読み込み (右側用の画像として読み込む)
                        self.analyzer.load_page(
                            image_path=file_path,
                            source_type="pdf", # PDF側（右側）として扱う
                            source_id=Path(file_path).name,
                            page_num=1
                        )
                        loaded_count += 1
                
                self.after(0, lambda: self._on_load_complete(loaded_count))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", f"読み込み中にエラーが発生しました:\n{str(e)}"))
                import traceback
                traceback.print_exc()
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        # バックグラウンドで実行
        threading.Thread(target=_run_load, daemon=True).start()
    
    def show_macro_view(self):
        """全体マップビューを表示"""
        # 既存のビューをクリア
        if self.current_view:
            self.current_view.pack_forget()
        
        # MacroViewを作成
        self.macro_view = MacroView(
            self.content_area,
            analyzer=self.analyzer,
            on_detail_click=self._open_micro_view
        )
        self.macro_view.pack(fill="both", expand=True)
        
        # データを読み込み
        self.macro_view.load_from_analyzer()
        
        self.current_view = self.macro_view
        print("🗺️ 全体マップビューを表示")
    
    def _open_micro_view(self, matched_pair):
        """詳細比較ビュー（Micro View）を開く"""
        try:
            micro = MicroView(
                self,
                matched_pair=matched_pair,
                analyzer=self.analyzer
            )
            print(f"🔍 詳細比較を開きました: 類似度 {matched_pair.similarity_score:.1%}")
            
        except Exception as e:
            messagebox.showerror("エラー", f"詳細比較の表示に失敗しました:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def new_project(self):
        """新規プロジェクト作成ダイアログを開く"""
        from app.gui.dialogs.project_dialog import ProjectDialog
        
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
        print("=" * 60)
        
        # ローディング画面を表示
        self._show_loading_screen()
        
        # プログレスバーを表示
        self.nav_panel.show_progress()
        
        # バックグラウンドで分析実行
        def _run_analysis():
            try:
                # Step 1: Webクロール
                self.after(0, lambda: self._update_loading_message("🌐 Webページをクロール中..."))
                web_results = self._crawl_web_pages(
                    config['url'],
                    config['depth'],
                    config['max_pages']
                )
                
                # Step 2: PDF読込
                self.after(0, lambda: self._update_loading_message("📁 PDFを読み込み中..."))
                pdf_results = self._load_pdf_pages(
                    config.get('pdf_file'),
                    config.get('pdf_folder')
                )
                
                # Step 3: OCR実行（オプション）
                if config['use_ocr'] and self.ocr_engine:
                    self.after(0, lambda: self._update_loading_message("🔍 OCR実行中..."))
                    # TODO: OCR処理
                
                # Step 4: マッチング
                self.after(0, lambda: self._update_loading_message("⚡ マッチング実行中..."))
                pairs = self.analyzer.compute_auto_matches(
                    threshold=config['threshold'],
                    method="hybrid"
                )
                
                # Step 5: 完了
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
    
    def _crawl_web_pages(self, url: str, depth: int, max_pages: int) -> List:
        """Webページをクロール"""
        from app.core.enhanced_scraper import EnhancedScraper
        
        try:
            scraper = EnhancedScraper()
            results = scraper.crawl_site(
                base_url=url,
                max_depth=depth,
                max_pages=max_pages
            )
            
            # Analyzerに追加（簡易版）
            for i, result in enumerate(results):
                # TODO: 実際の画像パスとテキストを処理
                print(f"  Web {i+1}: {result.get('url')}")
            
            return results
            
        except Exception as e:
            print(f"⚠️ Webクロールエラー: {str(e)}")
            return []
    
    def _load_pdf_pages(self, pdf_file: Optional[str], pdf_folder: Optional[str]) -> List:
        """PDFページを読み込み"""
        from app.utils.pdf_loader import PDFLoader
        
        try:
            loader = PDFLoader()
            results = []
            
            if pdf_file:
                # 単一ファイル
                pages = loader.load_pdf(pdf_file)
                results.extend(pages)
                print(f"  PDF: {pdf_file} ({len(pages)} ページ)")
                
            elif pdf_folder:
                # フォルダ内の全PDF
                # TODO: 実装
                print(f"  PDFフォルダ: {pdf_folder}")
            
            return results
            
        except Exception as e:
            print(f"⚠️ PDF読込エラー: {str(e)}")
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
    
    def crawl_web(self):
        """Webクロールを実行"""
        # モード選択ダイアログ
        mode = messagebox.askyesno(
            "Webデータ読み込み",
            "ローカルの画像ファイルをWebデータとして読み込みますか？\n\n(いいえ = URLからクロール機能[未実装])"
        )
        
        if not mode:
            messagebox.showinfo(
                "Web一括クロール",
                "URLクロール機能は実装予定です。\n\n現在は既存のDashboard機能をご利用ください。"
            )
            return

        # 画像読み込み処理
        file_paths = filedialog.askopenfilenames(
            title="Web用画像を選択",
            filetypes=[
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp"),
                ("全てのファイル", "*.*")
            ]
        )
        
        if not file_paths:
            return
            
        self.nav_panel.show_progress()
        
        def _run_load():
            try:
                loaded_count = 0
                total = len(file_paths)
                
                for i, file_path in enumerate(file_paths, 1):
                    self.after(0, lambda: self._update_loading_message(f"Web画像読込 ({i}/{total}): {Path(file_path).name}"))
                    
                    self.analyzer.load_page(
                        image_path=file_path,
                        source_type="web", # Web側（左側）として扱う
                        source_id=Path(file_path).name,
                        title=f"Web: {Path(file_path).stem}"
                    )
                    loaded_count += 1
                
                self.after(0, lambda: self._on_load_complete(loaded_count))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", f"読み込み中にエラーが発生しました:\n{str(e)}"))
                import traceback
                traceback.print_exc()
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        threading.Thread(target=_run_load, daemon=True).start()
    
    def load_pdfs(self):
        """PDF一括読込を実行"""
        file_paths = filedialog.askopenfilenames(
            title="PDFまたは画像を選択",
            filetypes=[
                ("PDF & 画像", "*.pdf *.png *.jpg *.jpeg *.bmp"),
                ("PDFファイル", "*.pdf"),
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp")
            ]
        )
        
        if not file_paths:
            return
            
        # プログレス表示
        self.nav_panel.show_progress()
        
        def _run_load():
            try:
                from app.utils.pdf_loader import PDFLoader
                from app.core.analyzer import DetectedArea
                
                loader = PDFLoader()
                total_files = len(file_paths)
                loaded_count = 0
                
                for i, file_path in enumerate(file_paths, 1):
                    self.after(0, lambda: self._update_loading_message(f"読み込み中 ({i}/{total_files}): {Path(file_path).name}"))
                    
                    if file_path.lower().endswith('.pdf'):
                        # PDF読み込み
                        results = loader.load_pdf(file_path)
                        for page_res in results:
                            # エリア情報を変換
                            areas = []
                            for area_dict in page_res['areas']:
                                areas.append(DetectedArea(
                                    text=area_dict['text'],
                                    bbox=area_dict['bbox'],
                                    confidence=1.0, # PDFネイティブは信頼度MAX
                                    source_type="pdf",
                                    source_id=Path(file_path).name,
                                    page_num=page_res['page_num']
                                ))
                            
                            # Analyzerに追加
                            self.analyzer.load_page(
                                image_path=None, # PDFなのでパスはなし（ファイルパスはsource_id）
                                source_type="pdf",
                                source_id=Path(file_path).name,
                                page_num=page_res['page_num'],
                                title=f"Page {page_res['page_num']}",
                                image=page_res['page_image'],
                                areas=areas
                            )
                        loaded_count += len(results)
                        
                    else:
                        # 画像読み込み (右側用の画像として読み込む)
                        self.analyzer.load_page(
                            image_path=file_path,
                            source_type="pdf", # PDF側（右側）として扱う
                            source_id=Path(file_path).name,
                            page_num=1
                        )
                        loaded_count += 1
                
                self.after(0, lambda: self._on_load_complete(loaded_count))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", f"読み込み中にエラーが発生しました:\n{str(e)}"))
                import traceback
                traceback.print_exc()
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        # バックグラウンドで実行
        threading.Thread(target=_run_load, daemon=True).start()
    
    def _on_load_complete(self, count: int):
        """読み込み完了時の処理"""
        messagebox.showinfo(
            "完了",
            f"✅ 読み込みが完了しました\n\n{count} ページを読み込みました"
        )
        # MacroViewを更新
        if self.macro_view:
            self.macro_view.load_from_analyzer()
        elif hasattr(self, 'show_macro_view'):
            self.show_macro_view()
    
    def match_all(self):
        """一括マッチングを実行"""
        if not self.analyzer:
            messagebox.showwarning("警告", "Analyzerが初期化されていません")
            return
        
        if not self.analyzer.web_areas or not self.analyzer.pdf_areas:
            messagebox.showwarning(
                "警告",
                "WebエリアまたはPDFエリアがありません。\n先にデータを読み込んでください。"
            )
            return
        
        # プログレス表示
        self.nav_panel.show_progress()
        
        def _run_matching():
            try:
                # マッチング実行
                pairs = self.analyzer.compute_auto_matches(
                    threshold=0.3,
                    method="hybrid"
                )
                
                # UI更新
                self.after(0, lambda: self._on_matching_complete(pairs))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        # バックグラウンドで実行
        threading.Thread(target=_run_matching, daemon=True).start()
    
    def _on_matching_complete(self, pairs):
        """マッチング完了時の処理"""
        messagebox.showinfo(
            "完了",
            f"✅ マッチングが完了しました\n\n{len(pairs)} ペアが見つかりました"
        )
        
        # MacroViewを更新
        if self.macro_view:
            self.macro_view.refresh_canvas()
    
    def run_ocr(self):
        """OCR実行"""
        if not self.ocr_engine:
            messagebox.showwarning(
                "警告",
                "OCRエンジンが初期化されていません。\n\ncredentials.jsonを配置してください。"
            )
            return
        
        # 画像ファイルを選択
        file_path = filedialog.askopenfilename(
            title="OCRする画像を選択",
            filetypes=[
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp"),
                ("全てのファイル", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        # プログレス表示
        self.nav_panel.show_progress()
        
        def _run_ocr():
            try:
                # OCR実行
                result = self.ocr_engine.detect_document_text(file_path)
                
                if result:
                    # 結果を表示
                    self.after(0, lambda: self._show_ocr_result(result))
                else:
                    self.after(0, lambda: messagebox.showerror(
                        "エラー",
                        "OCR処理に失敗しました"
                    ))
                    
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self.nav_panel.hide_progress)
        
        # バックグラウンドで実行
        threading.Thread(target=_run_ocr, daemon=True).start()
    
    def _show_ocr_result(self, result):
        """OCR結果を表示"""
        # 新しいウィンドウで表示
        window = ctk.CTkToplevel(self)
        window.title("OCR結果")
        window.geometry("800x600")
        
        # テキストウィジェット
        text_widget = tk.Text(
            window,
            bg="#1A1A1A",
            fg="white",
            font=("Consolas", 10),
            wrap="word",
            padx=15,
            pady=15
        )
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 結果を挿入
        text_widget.insert("end", f"=== 全体テキスト ===\n\n{result['full_text']}\n\n")
        text_widget.insert("end", f"=== 検出ブロック数: {len(result['blocks'])} ===\n\n")
        
        for i, block in enumerate(result['blocks'][:10], 1):
            text_widget.insert("end", f"ブロック {i}:\n")
            text_widget.insert("end", f"  テキスト: {block['text'][:100]}...\n")
            text_widget.insert("end", f"  座標: {block['bbox']}\n")
            text_widget.insert("end", f"  信頼度: {block['confidence']:.2%}\n\n")
    
    def export_excel(self):
        """Excel出力"""
        # TODO: ReportWriterを使用
        messagebox.showinfo("Excel出力", "この機能は実装予定です")
    
    def save_project(self):
        """プロジェクト保存"""
        # TODO: DataManagerを使用
        messagebox.showinfo("プロジェクト保存", "この機能は実装予定です")
    
    def load_project(self):
        """プロジェクト読込"""
        # TODO: DataManagerを使用
        messagebox.showinfo("プロジェクト読込", "この機能は実装予定です")

    def open_settings(self):
        """API設定画面を開く"""
        try:
            from app.gui.dialogs.settings_dialog import SettingsDialog

            # 設定ダイアログを開く（モーダル）
            dialog = SettingsDialog(self)
            self.wait_window(dialog)

            # 設定保存後、エンジンを再初期化
            print("🔄 API設定が更新されました。エンジンを再初期化します...")
            self._initialize_engines()

        except Exception as e:
            messagebox.showerror(
                "設定エラー",
                f"設定画面の表示に失敗しました:\n{str(e)}"
            )
            print(f"❌ Settings dialog error: {e}")

    def _setup_keyboard_shortcuts(self):
        """キーボードショートカット設定"""
        try:
            self.keyboard_manager = KeyboardManager(self)

            # ファイル操作
            self.keyboard_manager.bind("save", self.save_project)
            self.keyboard_manager.bind("open", self.load_project)
            self.keyboard_manager.bind("export_excel", self.export_excel)
            self.keyboard_manager.bind("settings", self.open_settings)
            self.keyboard_manager.bind("quit", self.quit)

            # 表示
            self.keyboard_manager.bind("refresh", self.show_macro_view)
            self.keyboard_manager.bind("toggle_fullscreen", self._toggle_fullscreen)

            # ツール
            self.keyboard_manager.bind("run_ocr", self.run_ocr)
            self.keyboard_manager.bind("match_all", self.match_all)

            # ヘルプ
            self.keyboard_manager.bind("help", self._show_help)
            self.keyboard_manager.bind("shortcuts", self.keyboard_manager.show_help_dialog)

            print("✅ Keyboard shortcuts configured")

        except Exception as e:
            print(f"⚠️ Failed to setup keyboard shortcuts: {e}")

    def _toggle_fullscreen(self):
        """フルスクリーン切り替え"""
        current = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not current)

    def _show_help(self):
        """ヘルプを表示"""
        messagebox.showinfo(
            "ヘルプ",
            "MEKIKI Ver2 - クリエイティブ評価ツール\n\n"
            "主な機能:\n"
            "- Web/PDF比較\n"
            "- AI OCR (Gemini)\n"
            "- 自動マッチング\n"
            "- Excel出力\n\n"
            "ショートカット一覧: Ctrl+/\n"
            "設定: Ctrl+,\n"
            "ヘルプ: F1"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 OCR 比較ツール V2 起動中...")
    print("=" * 60)
    
    app = MainWindow()
    app.mainloop()

