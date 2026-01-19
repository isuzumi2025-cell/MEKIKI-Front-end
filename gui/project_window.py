"""
プロジェクト管理ビュー
WebページとPDFページの一括管理・マッチング機能
ウィザード形式の直感的なUI
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import threading
import os
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.core.project_manager import ProjectManager, TextArea
from app.core.crawler import WebCrawler
from app.core.matcher import TextMatcher
from app.core.report_generator import ReportGenerator
from app.utils.pdf_loader import PDFLoader
from app.gui.interactive_canvas import InteractiveCanvas


class ProjectWindow(ctk.CTkToplevel):
    """プロジェクト管理ウィンドウ（ウィザード形式）"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("プロジェクト管理 - 一括照合")
        self.geometry("1600x900")
        self.transient(parent)
        
        self.project_manager = ProjectManager()
        self.pdf_loader = PDFLoader()
        self.matcher = TextMatcher()
        self.report_generator = ReportGenerator()
        
        # マスク編集用の変数
        self.mask_editing = False
        self.mask_start_x = None
        self.mask_start_y = None
        self.mask_rect_id = None
        
        self._setup_ui()
        self._update_step_status()
    
    def _setup_ui(self):
        """UI構築"""
        # --- 上部ステータスバー ---
        self._build_status_bar()
        
        # --- ツールバー（ボタングループ化） ---
        self._build_toolbar()
        
        # --- メインエリア（左右分割） ---
        self._build_main_area()
    
    def _build_status_bar(self):
        """上部ステータスバー（現在の手順表示）"""
        status_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#1A1A1A")
        status_frame.pack(side="top", fill="x", padx=0, pady=0)
        status_frame.pack_propagate(False)
        
        # ステップ表示ラベル
        self.step_label = ctk.CTkLabel(
            status_frame,
            text="STEP 1: WebとPDFを読み込んでください",
            font=("Meiryo", 14, "bold"),
            text_color="#4CAF50"
        )
        self.step_label.pack(side="left", padx=20, pady=15)
        
        # 進捗情報
        self.progress_info = ctk.CTkLabel(
            status_frame,
            text="",
            font=("Meiryo", 11),
            text_color="gray"
        )
        self.progress_info.pack(side="right", padx=20, pady=15)
    
    def _build_toolbar(self):
        """ツールバー（機能ごとにグループ化・色分け）"""
        toolbar = ctk.CTkFrame(self, height=70, corner_radius=0)
        toolbar.pack(side="top", fill="x", padx=0, pady=0)
        toolbar.pack_propagate(False)
        
        # === 入力セクション（Web/PDF）===
        input_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        input_frame.pack(side="left", padx=10, pady=10)
        
        input_label = ctk.CTkLabel(input_frame, text="📥 入力", font=("Meiryo", 11, "bold"), text_color="#2196F3")
        input_label.pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            input_frame, 
            text="🌐 Web一括クロール", 
            command=self.start_crawl,
            width=150,
            fg_color="#E08E00",
            hover_color="#D07E00",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            input_frame, 
            text="📁 PDF一括読込", 
            command=self.load_pdfs,
            width=150,
            fg_color="#4CAF50",
            hover_color="#45A049",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        # 区切り線
        separator1 = ctk.CTkFrame(toolbar, width=2, fg_color="gray")
        separator1.pack(side="left", fill="y", padx=10, pady=10)
        
        # === 処理セクション（マッチング/保存）===
        process_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        process_frame.pack(side="left", padx=10, pady=10)
        
        process_label = ctk.CTkLabel(process_frame, text="⚙️ 処理", font=("Meiryo", 11, "bold"), text_color="#FF9800")
        process_label.pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            process_frame, 
            text="⚖️ 一括マッチング", 
            command=self.start_matching,
            width=150,
            fg_color="#8B4513",
            hover_color="#7A3F12",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            process_frame, 
            text="💾 プロジェクト保存", 
            command=self.save_project,
            width=150,
            fg_color="#2196F3",
            hover_color="#1976D2",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            process_frame, 
            text="📂 プロジェクト読込", 
            command=self.load_project,
            width=150,
            fg_color="#9C27B0",
            hover_color="#7B1FA2",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            process_frame, 
            text="📤 Excelレポート出力", 
            command=self.export_excel_report,
            width=180,
            fg_color="#FF6F00",
            hover_color="#E65100",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        # 区切り線
        separator2 = ctk.CTkFrame(toolbar, width=2, fg_color="gray")
        separator2.pack(side="left", fill="y", padx=10, pady=10)
        
        # === 設定セクション ===
        settings_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        settings_frame.pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(
            settings_frame, 
            text="🎨 共通除外エリア設定", 
            command=self.toggle_mask_editing,
            width=180,
            fg_color="#555",
            hover_color="#444",
            font=("Meiryo", 11)
        ).pack(side="left", padx=5)
        
        # プログレスバー（右側）
        self.progress = ctk.CTkProgressBar(toolbar, mode='indeterminate', width=200)
        self.progress.pack(side="right", padx=10, pady=10)
    
    def _build_main_area(self):
        """メインエリア（左右分割）"""
        main_paned = tk.PanedWindow(self, orient="horizontal", bg="#2B2B2B", sashwidth=4)
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- 左パネル: Webページ一覧 ---
        self._build_web_panel(main_paned)
        
        # --- 中央パネル: マッチング結果・プレビュー ---
        self._build_center_panel(main_paned)
        
        # --- 右パネル: PDFページ一覧 ---
        self._build_pdf_panel(main_paned)
    
    def _build_web_panel(self, parent):
        """Webページ一覧パネル"""
        web_frame = ctk.CTkFrame(parent, corner_radius=0)
        parent.add(web_frame, width=400)
        
        ctk.CTkLabel(
            web_frame, 
            text="🌐 Webページ一覧", 
            font=("Meiryo", 14, "bold"),
            text_color="#E08E00"
        ).pack(pady=15)
        
        # ツリービュー
        web_tree_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        web_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.web_tree = ttk.Treeview(
            web_tree_frame,
            columns=("status",),
            show="tree headings",
            height=20
        )
        self.web_tree.heading("#0", text="タイトル / URL")
        self.web_tree.heading("status", text="ステータス")
        self.web_tree.column("#0", width=300)
        self.web_tree.column("status", width=80)
        
        # クリックイベントを追加
        self.web_tree.bind("<ButtonRelease-1>", self.on_web_item_clicked)
        
        web_scroll = tk.Scrollbar(web_tree_frame, orient="vertical", command=self.web_tree.yview)
        self.web_tree.configure(yscrollcommand=web_scroll.set)
        self.web_tree.pack(side="left", fill="both", expand=True)
        web_scroll.pack(side="right", fill="y")
        
        # プレースホルダー（空のとき）
        self.web_placeholder = ctk.CTkLabel(
            web_tree_frame,
            text="👈 左上の「Web一括クロール」ボタンを押して\nデータを取得してください",
            font=("Meiryo", 12),
            text_color="gray",
            anchor="center",
            justify="center"
        )
        self.web_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        
        # 抽出テキストプレビューエリア（Webパネル下部）
        text_preview_web_frame = ctk.CTkFrame(web_frame, height=150)
        text_preview_web_frame.pack(fill="x", padx=5, pady=5)
        text_preview_web_frame.pack_propagate(False)
        
        ctk.CTkLabel(
            text_preview_web_frame,
            text="📝 抽出テキストプレビュー（Web）",
            font=("Meiryo", 10, "bold"),
            text_color="#E08E00"
        ).pack(pady=5)
        
        self.web_text_preview = ctk.CTkTextbox(
            text_preview_web_frame,
            height=120,
            font=("Meiryo", 9),
            wrap="word"
        )
        self.web_text_preview.pack(fill="both", expand=True, padx=5, pady=(0, 5))
    
    def _build_center_panel(self, parent):
        """中央パネル（マッチング結果・プレビュー）"""
        center_frame = ctk.CTkFrame(parent, corner_radius=0)
        parent.add(center_frame)
        
        # ヘッダーフレーム（背景色付き）
        header_frame = ctk.CTkFrame(center_frame, fg_color="#1A1A1A", height=70)
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # メインタイトル
        ctk.CTkLabel(
            header_frame, 
            text="📊 全体マッピングビュー", 
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(pady=(10, 0))
        
        # サブタイトル（説明）
        ctk.CTkLabel(
            header_frame, 
            text="マッチング結果の一覧です。各カードから詳細比較を選択できます。", 
            font=("Meiryo", 10),
            text_color="gray"
        ).pack(pady=(0, 10))
        
        # カード表示エリア（スクロール可能）
        card_container = ctk.CTkScrollableFrame(center_frame, fg_color="transparent")
        card_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # カードリストを保持する変数
        self.matching_cards_frame = card_container
        self.matching_cards = []  # カードウィジェットを保持
        
        # インタラクティブキャンバスエリア（領域編集用）
        preview_frame = ctk.CTkFrame(center_frame, height=400)
        preview_frame.pack(fill="x", padx=5, pady=5)
        preview_frame.pack_propagate(False)
        
        # ヘッダー（画像情報表示）
        self.canvas_header = ctk.CTkLabel(
            preview_frame, 
            text="画像を選択してください", 
            font=("Meiryo", 11, "bold"),
            anchor="w"
        )
        self.canvas_header.pack(fill="x", padx=10, pady=5)
        
        # キャンバスフレーム
        canvas_container = ctk.CTkFrame(preview_frame, fg_color="transparent")
        canvas_container.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # InteractiveCanvasを作成
        self.interactive_canvas = InteractiveCanvas(canvas_container, width=750, height=320)
        self.interactive_canvas.pack(fill="both", expand=True)
        
        # 現在表示中のページ情報
        self.current_preview_type = None  # "web" or "pdf"
        self.current_preview_page = None
    
    def _build_pdf_panel(self, parent):
        """PDFページ一覧パネル"""
        pdf_frame = ctk.CTkFrame(parent, corner_radius=0)
        parent.add(pdf_frame, width=400)
        
        ctk.CTkLabel(
            pdf_frame, 
            text="📁 PDFページ一覧", 
            font=("Meiryo", 14, "bold"),
            text_color="#4CAF50"
        ).pack(pady=15)
        
        # ツリービュー
        pdf_tree_frame = ctk.CTkFrame(pdf_frame, fg_color="transparent")
        pdf_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.pdf_tree = ttk.Treeview(
            pdf_tree_frame,
            columns=("status",),
            show="tree headings",
            height=20
        )
        self.pdf_tree.heading("#0", text="ファイル名 / ページ")
        self.pdf_tree.heading("status", text="ステータス")
        self.pdf_tree.column("#0", width=300)
        self.pdf_tree.column("status", width=80)
        
        # クリックイベントを追加
        self.pdf_tree.bind("<ButtonRelease-1>", self.on_pdf_item_clicked)
        
        pdf_scroll = tk.Scrollbar(pdf_tree_frame, orient="vertical", command=self.pdf_tree.yview)
        self.pdf_tree.configure(yscrollcommand=pdf_scroll.set)
        self.pdf_tree.pack(side="left", fill="both", expand=True)
        pdf_scroll.pack(side="right", fill="y")
        
        # プレースホルダー（空のとき）
        self.pdf_placeholder = ctk.CTkLabel(
            pdf_tree_frame,
            text="👈 左上の「PDF一括読込」ボタンを押して\nデータを読み込んでください",
            font=("Meiryo", 12),
            text_color="gray",
            anchor="center",
            justify="center"
        )
        self.pdf_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        
        # 抽出テキストプレビューエリア（PDFパネル下部）
        text_preview_pdf_frame = ctk.CTkFrame(pdf_frame, height=150)
        text_preview_pdf_frame.pack(fill="x", padx=5, pady=5)
        text_preview_pdf_frame.pack_propagate(False)
        
        ctk.CTkLabel(
            text_preview_pdf_frame,
            text="📝 抽出テキストプレビュー（PDF）",
            font=("Meiryo", 10, "bold"),
            text_color="#4CAF50"
        ).pack(pady=5)
        
        self.pdf_text_preview = ctk.CTkTextbox(
            text_preview_pdf_frame,
            height=120,
            font=("Meiryo", 9),
            wrap="word"
        )
        self.pdf_text_preview.pack(fill="both", expand=True, padx=5, pady=(0, 5))
    
    def _update_step_status(self):
        """ステップ表示を更新"""
        web_count = len(self.project_manager.web_pages)
        pdf_count = len(self.project_manager.pdf_pages)
        match_count = len(self.project_manager.pairs)
        
        if web_count == 0 or pdf_count == 0:
            self.step_label.configure(
                text="STEP 1: WebとPDFを読み込んでください",
                text_color="#4CAF50"
            )
            self.progress_info.configure(text=f"Web: {web_count}件 / PDF: {pdf_count}ページ")
        elif match_count == 0:
            self.step_label.configure(
                text="STEP 2: 「一括マッチング」を実行してください",
                text_color="#FF9800"
            )
            self.progress_info.configure(text=f"Web: {web_count}件 / PDF: {pdf_count}ページ")
        else:
            self.step_label.configure(
                text=f"STEP 3: マッチング完了（{match_count}件）",
                text_color="#2196F3"
            )
            self.progress_info.configure(text=f"Web: {web_count}件 / PDF: {pdf_count}ページ / マッチ: {match_count}件")
        
        # プレースホルダーの表示/非表示
        self.web_placeholder.place_forget() if web_count > 0 else self.web_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        self.pdf_placeholder.place_forget() if pdf_count > 0 else self.pdf_placeholder.place(relx=0.5, rely=0.5, anchor="center")
    
    def start_crawl(self):
        """Web一括クロールを開始"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Web一括クロール設定")
        dialog.geometry("700x800")  # サイズを大きく
        dialog.transient(self)
        dialog.grab_set()
        
        # タイトル（固定）
        title_label = ctk.CTkLabel(dialog, text="🌐 Web一括クロール設定", font=("Meiryo", 18, "bold"))
        title_label.pack(pady=20)
        
        # スクロール可能なフレーム（高さを指定してスクロール可能に）
        scrollable_frame = ctk.CTkScrollableFrame(dialog, width=660, height=550)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        # ルートURL
        ctk.CTkLabel(scrollable_frame, text="ルートURL:", anchor="w", font=("Meiryo", 12, "bold")).pack(fill="x", pady=(10, 5))
        entry_url = ctk.CTkEntry(scrollable_frame, placeholder_text="https://example.com", height=35, font=("Meiryo", 11))
        entry_url.pack(fill="x", pady=(0, 15))
        
        # 最大ページ数
        ctk.CTkLabel(scrollable_frame, text="最大ページ数:", anchor="w", font=("Meiryo", 12, "bold")).pack(fill="x", pady=(0, 5))
        entry_max = ctk.CTkEntry(scrollable_frame, height=35, font=("Meiryo", 11))
        entry_max.insert(0, "50")
        entry_max.pack(fill="x", pady=(0, 15))
        
        # 認証情報セクション（明確に区切り）
        auth_separator = ctk.CTkFrame(scrollable_frame, height=2, fg_color="gray")
        auth_separator.pack(fill="x", pady=(15, 15))
        
        auth_label = ctk.CTkLabel(
            scrollable_frame, 
            text="認証情報（オプション）", 
            font=("Meiryo", 13, "bold"),
            anchor="w"
        )
        auth_label.pack(fill="x", pady=(0, 10))
        
        # 認証情報フレーム
        auth_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        auth_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(auth_frame, text="ユーザー名:", anchor="w", font=("Meiryo", 11)).pack(fill="x", padx=10, pady=(0, 5))
        entry_user = ctk.CTkEntry(auth_frame, height=35, font=("Meiryo", 11))
        entry_user.pack(fill="x", padx=10, pady=(0, 15))
        
        ctk.CTkLabel(auth_frame, text="パスワード:", anchor="w", font=("Meiryo", 11)).pack(fill="x", padx=10, pady=(0, 5))
        entry_pass = ctk.CTkEntry(auth_frame, show="*", height=35, font=("Meiryo", 11))
        entry_pass.pack(fill="x", padx=10, pady=(0, 15))
        
        # 説明テキスト
        info_label = ctk.CTkLabel(
            scrollable_frame,
            text="※認証が必要なサイトの場合のみ入力してください。\nBasic認証とCookie認証に対応しています。",
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w",
            justify="left"
        )
        info_label.pack(fill="x", pady=(10, 20))
        
        def on_submit():
            url = entry_url.get().strip()
            max_pages = int(entry_max.get().strip() or "50")
            username = entry_user.get().strip() or None
            password = entry_pass.get().strip() or None
            
            if not url:
                messagebox.showwarning("必須", "ルートURLを入力してください", parent=dialog)
                return
            
            dialog.destroy()
            self.progress.pack(side="right", padx=10)
            self.progress.start()
            threading.Thread(
                target=self._run_crawl,
                args=(url, max_pages, username, password),
                daemon=True
            ).start()
        
        # ボタンフレーム（スクロールフレームの外、ウィンドウ最下部に固定）
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # キャンセルボタン
        ctk.CTkButton(
            button_frame,
            text="キャンセル",
            command=dialog.destroy,
            fg_color="gray",
            hover_color="#555",
            height=45,
            font=("Meiryo", 13, "bold"),
            width=150
        ).pack(side="left", padx=(0, 10))
        
        # 実行ボタン
        ctk.CTkButton(
            button_frame, 
            text="🚀 クロール開始", 
            command=on_submit, 
            fg_color="#E08E00",
            hover_color="#D07E00",
            height=45,
            font=("Meiryo", 13, "bold")
        ).pack(side="right", fill="x", expand=True)
    
    def _run_crawl(self, root_url: str, max_pages: int, username: str, password: str):
        """クロール実行（バックグラウンド）"""
        try:
            crawler = WebCrawler(
                max_pages=max_pages,
                max_depth=5,
                delay=1.0,
                username=username,
                password=password
            )
            
            def progress_callback(url, current, total):
                self.after(0, lambda: self._update_crawl_status(f"処理中: {url} ({current}/{total})"))
            
            results = crawler.crawl(root_url, progress_callback=progress_callback)
            
            # プロジェクトマネージャーに追加
            for result in results:
                # areasをTextAreaオブジェクトに変換
                areas = None
                if result.get("areas"):
                    areas = [TextArea(text=a["text"], bbox=a["bbox"]) for a in result["areas"]]
                
                self.project_manager.add_web_page(
                    url=result["url"],
                    title=result["title"],
                    text=result["text"],
                    screenshot_path=result.get("screenshot_path"),
                    areas=areas,
                    screenshot_image=result.get("screenshot_image"),
                    error=result.get("error")  # エラー情報を追加
                )
            
            self.after(0, lambda: self._on_crawl_complete(len(results)))
            
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda err=e: messagebox.showerror("エラー", f"クロールに失敗しました:\n{str(err)}"))
        finally:
            self.after(0, self._reset_progress)
    
    def _update_crawl_status(self, message: str):
        """クロール進捗を更新"""
        self.progress_info.configure(text=message)
    
    def _on_crawl_complete(self, count: int):
        """クロール完了時の処理"""
        messagebox.showinfo("完了", f"{count}件のWebページを取得しました")
        self._refresh_web_tree()
        self._update_step_status()
    
    def load_pdfs(self):
        """PDF一括読込"""
        folder = filedialog.askdirectory(title="PDFフォルダを選択")
        if not folder:
            return
        
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        threading.Thread(target=self._run_load_pdfs, args=(folder,), daemon=True).start()
    
    def _run_load_pdfs(self, folder_path: str):
        """PDF読込実行（バックグラウンド）"""
        try:
            # グローバルマスクを適用
            if self.project_manager.global_mask:
                self.pdf_loader.set_global_mask(**self.project_manager.global_mask)
            
            results = self.pdf_loader.load_pdfs_from_folder(folder_path, recursive=True)
            
            # プロジェクトマネージャーに追加
            for result in results:
                # areasをTextAreaオブジェクトに変換
                areas = None
                if result.get("areas"):
                    areas = [TextArea(text=a["text"], bbox=a["bbox"]) for a in result["areas"]]
                
                self.project_manager.add_pdf_page(
                    filename=result["filename"],
                    page_num=result["page_num"],
                    text=result["text"],
                    image_path=result.get("image_path"),
                    areas=areas,
                    page_image=result.get("page_image")
                )
            
            self.after(0, lambda: self._on_pdf_load_complete(len(results)))
            
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda err=e: messagebox.showerror("エラー", f"PDF読込に失敗しました:\n{str(err)}"))
        finally:
            self.after(0, self._reset_progress)
    
    def _on_pdf_load_complete(self, count: int):
        """PDF読込完了時の処理"""
        messagebox.showinfo("完了", f"{count}ページのPDFを読み込みました")
        self._refresh_pdf_tree()
        self._update_step_status()
    
    def start_matching(self):
        """一括マッチングを開始"""
        if not self.project_manager.web_pages or not self.project_manager.pdf_pages:
            messagebox.showwarning("警告", "WebページとPDFページの両方を読み込んでください")
            return
        
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        threading.Thread(target=self._run_matching, daemon=True).start()
    
    def _run_matching(self):
        """マッチング実行（バックグラウンド）"""
        try:
            # Webページ（エラーがないもののみ）とPDFページを辞書形式に変換
            web_data = [
                {"page_id": page.page_id, "text": page.text}
                for page in self.project_manager.web_pages
                if not page.error  # エラーページは除外
            ]
            pdf_data = [
                {"page_id": page.page_id, "text": page.text}
                for page in self.project_manager.pdf_pages
            ]
            
            # マッチング実行（強制マッチングモード）
            pairs = self.matcher.match_all(web_data, pdf_data, force_matching=True)
            
            # プロジェクトマネージャーに追加
            self.project_manager.pairs.clear()
            for pair in pairs:
                # similarity_scoreが存在する場合はそれを使用、なければscoreを使用
                score = pair.get("similarity_score", pair.get("score", 0.0))
                self.project_manager.add_match_pair(
                    web_id=pair["web_id"],
                    pdf_id=pair["pdf_id"],
                    score=score
                )
            
            self.after(0, lambda: self._on_matching_complete(len(pairs)))
            
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda err=e: messagebox.showerror("エラー", f"マッチングに失敗しました:\n{str(err)}"))
        finally:
            self.after(0, self._reset_progress)
    
    def _on_matching_complete(self, count: int):
        """マッチング完了時の処理"""
        self._refresh_matrix()
        self._refresh_web_tree()
        self._refresh_pdf_tree()
        self._update_step_status()
        
        # マッチング完了メッセージ（次のステップを明示）
        messagebox.showinfo(
            "一括マッチング完了",
            f"✅ {count}件のペアを検出しました\n\n"
            "【全体マップ表示中】\n"
            "中央のエリアにマッチング結果カードが表示されています。\n\n"
            "【次のステップ】\n"
            "・各カードに表示されているシンクロ率を確認\n"
            "・詳細比較したいペアの「🔍 詳細比較」ボタンをクリック\n\n"
            "💡 現在の画面が全体マッピングビューです。\n"
            "   個別の詳細比較は行っていません。"
        )
    
    def _refresh_web_tree(self):
        """Webページツリーを更新"""
        # 既存のアイテムを削除
        for item in self.web_tree.get_children():
            self.web_tree.delete(item)
        
        # Treeviewのタグスタイルを設定（エラー行を赤字にする）
        self.web_tree.tag_configure("error", foreground="red")
        
        # プロジェクトマネージャーからデータを取得して表示
        for page in self.project_manager.web_pages:
            # エラーチェック
            if page.error:
                status = "❌ 取得失敗"
                display_text = f"【エラー】{page.url}\n{page.error}"
                tags = (page.page_id, "error")
            else:
                # マッチング状態を確認
                matched = any(p.web_id == page.page_id for p in self.project_manager.pairs)
                status = "✅一致" if matched else "⚠️不一致"
                display_text = f"{page.title}\n{page.url}"
                tags = (page.page_id,)
            
            self.web_tree.insert(
                "",
                "end",
                text=display_text,
                values=(status,),
                tags=tags
            )
        
        self._update_step_status()
    
    def _refresh_pdf_tree(self):
        """PDFページツリーを更新"""
        # 既存のアイテムを削除
        for item in self.pdf_tree.get_children():
            self.pdf_tree.delete(item)
        
        # プロジェクトマネージャーからデータを取得して表示
        for page in self.project_manager.pdf_pages:
            # マッチング状態を確認
            matched = any(p.pdf_id == page.page_id for p in self.project_manager.pairs)
            status = "✅一致" if matched else "⚠️不一致"
            
            filename = Path(page.filename).name
            self.pdf_tree.insert(
                "",
                "end",
                text=f"{filename} (p.{page.page_num})",
                values=(status,),
                tags=(page.page_id,)
            )
        
        self._update_step_status()
    
    def _refresh_matrix(self):
        """マッチング結果をカード形式で更新"""
        # 既存のカードを削除
        for card in self.matching_cards:
            card.destroy()
        self.matching_cards.clear()
        
        if not self.project_manager.pairs:
            no_result_label = ctk.CTkLabel(
                self.matching_cards_frame,
                text="📋 マッチング結果がまだありません\n\n"
                     "【手順】\n"
                     "1. 左側: Webページを取得\n"
                     "2. 右側: PDFページを読み込み\n"
                     "3. 上部: 「⚡ 一括マッチング」を実行\n\n"
                     "💡 マッチング完了後、ここに全体マップが表示されます",
                font=("Meiryo", 12),
                text_color="gray",
                justify="center"
            )
            no_result_label.pack(pady=50)
            self.matching_cards.append(no_result_label)
            return
        
        # スコアでソート
        sorted_pairs = sorted(self.project_manager.pairs, key=lambda p: p.score, reverse=True)
        
        for idx, pair in enumerate(sorted_pairs, start=1):
            web_page = self.project_manager.get_web_page_by_id(pair.web_id)
            pdf_page = self.project_manager.get_pdf_page_by_id(pair.pdf_id)
            
            if not web_page or not pdf_page:
                continue
            
            # カードフレームを作成（番号バッジ付き）
            card_container = ctk.CTkFrame(self.matching_cards_frame, fg_color="transparent")
            card_container.pack(fill="x", padx=10, pady=8)
            
            # 番号バッジ（左側）
            badge_frame = ctk.CTkFrame(card_container, fg_color="#2196F3", width=50, corner_radius=25)
            badge_frame.pack(side="left", padx=(0, 10), fill="y")
            badge_frame.pack_propagate(False)
            
            ctk.CTkLabel(
                badge_frame,
                text=f"#{idx}",
                font=("Meiryo", 14, "bold"),
                text_color="white"
            ).pack(expand=True)
            
            # カードフレーム（右側）
            card = ctk.CTkFrame(card_container, corner_radius=8)
            card.pack(side="left", fill="both", expand=True)
            self.matching_cards.append(card_container)
            
            # カード内容
            card_content = ctk.CTkFrame(card, fg_color="transparent")
            card_content.pack(fill="both", expand=True, padx=15, pady=15)
            
            # 上段: タイトルとシンクロ率
            top_row = ctk.CTkFrame(card_content, fg_color="transparent")
            top_row.pack(fill="x", pady=(0, 10))
            
            # Webページタイトル
            title_label = ctk.CTkLabel(
                top_row,
                text=f"🌐 {web_page.title[:50]}..." if len(web_page.title) > 50 else f"🌐 {web_page.title}",
                font=("Meiryo", 12, "bold"),
                anchor="w"
            )
            title_label.pack(side="left", fill="x", expand=True)
            
            # シンクロ率（スコア）
            score = pair.score
            score_percent = int(score * 100)
            score_label = ctk.CTkLabel(
                top_row,
                text=f"{score_percent}%",
                font=("Meiryo", 14, "bold"),
                text_color="#4CAF50" if score >= 0.5 else "#FF5722"
            )
            score_label.pack(side="right", padx=(10, 0))
            
            # プログレスバー
            progress_frame = ctk.CTkFrame(card_content, fg_color="transparent")
            progress_frame.pack(fill="x", pady=(0, 10))
            
            progress_color = "#4CAF50" if score >= 0.3 else "#FF5722"
            progress_bar = ctk.CTkProgressBar(
                progress_frame,
                width=400,
                height=20,
                progress_color=progress_color
            )
            progress_bar.set(score)
            progress_bar.pack(side="left", fill="x", expand=True)
            
            # PDF情報
            pdf_info_label = ctk.CTkLabel(
                card_content,
                text=f"📁 {Path(pdf_page.filename).name} (ページ {pdf_page.page_num})",
                font=("Meiryo", 11),
                text_color="gray",
                anchor="w"
            )
            pdf_info_label.pack(fill="x", pady=(0, 10))
            
            # 詳細比較ボタン
            detail_button = ctk.CTkButton(
                card_content,
                text="🔍 詳細比較",
                command=lambda w=web_page, p=pdf_page, s=score: self._show_detail_comparison(w, p, s),
                width=120,
                height=32,
                fg_color="#2196F3",
                hover_color="#1976D2",
                font=("Meiryo", 10)
            )
            detail_button.pack(side="right")
    
    def _show_detail_comparison(self, web_page, pdf_page, score):
        """詳細比較ウィンドウを表示（ビジュアル比較版）"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"📊 ビジュアル比較: {web_page.title}")
        dialog.geometry("1600x900")
        dialog.transient(self)
        
        # ヘッダー
        header = ctk.CTkFrame(dialog, height=80, corner_radius=0, fg_color="#1A1A1A")
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        # シンクロ率表示
        ctk.CTkLabel(
            header,
            text=f"🔄 シンクロ率: {int(score * 100)}%",
            font=("Meiryo", 18, "bold"),
            text_color="#4CAF50" if score >= 0.5 else "#FF5722"
        ).pack(side="left", padx=20, pady=20)
        
        # 説明テキスト
        ctk.CTkLabel(
            header,
            text="💡 左右の画像を比較して、赤枠の位置を確認できます。右クリックで不要な枠を削除できます。",
            font=("Meiryo", 11),
            text_color="gray"
        ).pack(side="left", padx=20, pady=20)
        
        # メインエリア（左右分割）
        main_paned = tk.PanedWindow(dialog, orient="horizontal", bg="#2B2B2B", sashwidth=4)
        main_paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 左側: Web画像用InteractiveCanvas
        web_frame = ctk.CTkFrame(main_paned, corner_radius=0)
        main_paned.add(web_frame, width=780)
        
        web_canvas = InteractiveCanvas(web_frame, width=760, height=700)
        web_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Web画像とエリアデータをロード
        if web_page.screenshot_image:
            # エリアデータを準備
            web_areas = []
            if web_page.areas:
                for idx, area in enumerate(web_page.areas):
                    web_areas.append({
                        "bbox": area.bbox if hasattr(area, 'bbox') else [0, 0, 100, 100],
                        "area_id": idx + 1
                    })
            
            web_canvas.load_data(
                image_path=web_page.screenshot_path if web_page.screenshot_path else None,
                title=f"🌐 Web: {web_page.url}",
                area_data_list=web_areas
            )
            
            # PIL Imageから直接読み込む場合
            if not web_page.screenshot_path or not os.path.exists(web_page.screenshot_path):
                web_canvas.load_image_from_pil(
                    pil_image=web_page.screenshot_image,
                    title=f"🌐 Web: {web_page.url}",
                    areas=web_areas
                )
        else:
            web_canvas.set_title(f"🌐 Web: {web_page.url} (画像なし)")
        
        # 右側: PDF画像用InteractiveCanvas
        pdf_frame = ctk.CTkFrame(main_paned, corner_radius=0)
        main_paned.add(pdf_frame, width=780)
        
        pdf_canvas = InteractiveCanvas(pdf_frame, width=760, height=700)
        pdf_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        # PDF画像とエリアデータをロード
        if pdf_page.page_image:
            # エリアデータを準備
            pdf_areas = []
            if pdf_page.areas:
                for idx, area in enumerate(pdf_page.areas):
                    pdf_areas.append({
                        "bbox": area.bbox if hasattr(area, 'bbox') else [0, 0, 100, 100],
                        "area_id": idx + 1
                    })
            
            pdf_filename = Path(pdf_page.filename).name
            
            pdf_canvas.load_data(
                image_path=pdf_page.image_path if pdf_page.image_path else None,
                title=f"📁 PDF: {pdf_filename} (ページ {pdf_page.page_num})",
                area_data_list=pdf_areas
            )
            
            # PIL Imageから直接読み込む場合
            if not pdf_page.image_path or not os.path.exists(pdf_page.image_path):
                pdf_canvas.load_image_from_pil(
                    pil_image=pdf_page.page_image,
                    title=f"📁 PDF: {pdf_filename} (ページ {pdf_page.page_num})",
                    areas=pdf_areas
                )
        else:
            pdf_filename = Path(pdf_page.filename).name
            pdf_canvas.set_title(f"📁 PDF: {pdf_filename} (ページ {pdf_page.page_num}) (画像なし)")
        
        # 閉じるボタン
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)
        
        ctk.CTkButton(
            button_frame,
            text="🔄 オニオンスキン表示",
            command=lambda: self._show_onion_skin_mode(web_page, pdf_page),
            width=180,
            height=35,
            font=("Meiryo", 12, "bold"),
            fg_color="#FF6F00",
            hover_color="#E65100"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="閉じる",
            command=dialog.destroy,
            width=150,
            height=35,
            font=("Meiryo", 12, "bold")
        ).pack(side="left", padx=5)
        
    def on_web_item_clicked(self, event):
        """Web項目がクリックされたときの処理"""
        selection = self.web_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.web_tree.item(item, "tags")
        if not tags:
            return
        
        try:
            page_id = int(tags[0])
            web_page = self.project_manager.get_web_page_by_id(page_id)
            
            if web_page:
                # テキストプレビューを更新
                self.web_text_preview.configure(state="normal")
                self.web_text_preview.delete("1.0", "end")
                self.web_text_preview.insert("1.0", web_page.text if web_page.text else "(テキストが抽出されていません)")
                self.web_text_preview.configure(state="disabled")
                
                # キャンバスに画像と領域を表示
                self._load_page_to_canvas(web_page, "web")
        except Exception as e:
            print(f"⚠️ Web項目表示エラー: {e}")
    
    def on_pdf_item_clicked(self, event):
        """PDF項目がクリックされたときの処理"""
        selection = self.pdf_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.pdf_tree.item(item, "tags")
        if not tags:
            return
        
        try:
            page_id = int(tags[0])
            pdf_page = self.project_manager.get_pdf_page_by_id(page_id)
            
            if pdf_page:
                # テキストプレビューを更新
                self.pdf_text_preview.configure(state="normal")
                self.pdf_text_preview.delete("1.0", "end")
                self.pdf_text_preview.insert("1.0", pdf_page.text if pdf_page.text else "(テキストが抽出されていません)")
                self.pdf_text_preview.configure(state="disabled")
                
                # キャンバスに画像と領域を表示
                self._load_page_to_canvas(pdf_page, "pdf")
        except Exception as e:
            print(f"⚠️ PDF項目表示エラー: {e}")
    
    def _load_page_to_canvas(self, page, page_type: str):
        """ページをキャンバスに読み込み
        Args:
            page: WebPage or PDFPage
            page_type: "web" or "pdf"
        """
        self.current_preview_type = page_type
        self.current_preview_page = page
        
        # 領域データを準備
        areas_list = []
        if page.areas:
            for idx, area in enumerate(page.areas):
                areas_list.append({
                    "bbox": area.bbox if hasattr(area, 'bbox') else area.get('bbox', [0, 0, 100, 100])
                })
        
        # ヘッダーとタイトルを設定
        if page_type == "web":
            title = f"🌐 {page.url}"
            # スクリーンショットを読み込み
            if page.screenshot_image:
                self.interactive_canvas.load_image_from_pil(page.screenshot_image, title, areas_list)
            elif page.screenshot_path and os.path.exists(page.screenshot_path):
                self.interactive_canvas.load_image(page.screenshot_path, title, areas_list)
            else:
                # 画像がない場合
                self.interactive_canvas.clear()
                self.interactive_canvas.set_title(title + " (画像なし)")
        else:  # pdf
            filename = Path(page.filename).name
            title = f"📁 {filename} (ページ {page.page_num})"
            # PDF画像を読み込み
            if page.page_image:
                self.interactive_canvas.load_image_from_pil(page.page_image, title, areas_list)
            elif page.image_path and os.path.exists(page.image_path):
                self.interactive_canvas.load_image(page.image_path, title, areas_list)
            else:
                # 画像がない場合
                self.interactive_canvas.clear()
                self.interactive_canvas.set_title(title + " (画像なし)")
    
    def toggle_mask_editing(self):
        """マスク編集モードの切り替え"""
        self.mask_editing = not self.mask_editing
        if self.mask_editing:
            messagebox.showinfo("マスク編集", "プレビューエリアで矩形を描画して、除外エリアを設定してください。")
    
    def _load_preview_image(self):
        """プレビュー画像を読み込み"""
        # 最初のPDFページの画像を表示（実装例）
        if self.project_manager.pdf_pages:
            # 実際の実装では、画像パスから読み込む
            pass
    
    def save_project(self):
        """プロジェクトを保存"""
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if path:
            try:
                self.project_manager.save_project(path)
                messagebox.showinfo("完了", "プロジェクトを保存しました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))
    
    def load_project(self):
        """プロジェクトを読み込み"""
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")]
        )
        if path:
            try:
                self.project_manager.load_project(path)
                self._refresh_web_tree()
                self._refresh_pdf_tree()
                self._refresh_matrix()
                self._update_step_status()
                messagebox.showinfo("完了", "プロジェクトを読み込みました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))
    
    def export_excel_report(self):
        """Excelレポートを出力"""
        # データチェック
        if not self.project_manager.pairs:
            messagebox.showwarning("警告", "マッチング結果がありません。\n先に「一括マッチング」を実行してください。")
            return
        
        # 保存先を選択
        output_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="比較レポート.xlsx"
        )
        
        if not output_path:
            return
        
        # プログレスバー表示
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        
        # バックグラウンドで実行
        threading.Thread(target=self._run_export_excel, args=(output_path,), daemon=True).start()
    
    def _run_export_excel(self, output_path: str):
        """Excelレポート出力（バックグラウンド）"""
        try:
            success = self.report_generator.generate_detailed_diff_report(
                output_path=output_path,
                web_pages=self.project_manager.web_pages,
                pdf_pages=self.project_manager.pdf_pages,
                pairs=self.project_manager.pairs,
                project_name="比較プロジェクト"
            )
            
            if success:
                self.after(0, lambda: messagebox.showinfo(
                    "完了",
                    f"Excelレポートを出力しました。\n\n{output_path}\n\n📊 2つのシートが含まれています:\n"
                    "• 比較結果: 画像とテキストの一覧\n"
                    "• 詳細差分: 行単位の差分分析"
                ))
            else:
                self.after(0, lambda: messagebox.showerror(
                    "エラー",
                    "Excelレポートの出力に失敗しました。"
                ))
                
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda err=e: messagebox.showerror(
                "エラー",
                f"Excelレポート出力エラー:\n{str(err)}"
            ))
        finally:
            self.after(0, self._reset_progress)
    
    def _show_onion_skin_mode(self, web_page, pdf_page):
        """オニオンスキンモードで比較表示"""
        # 新しいウィンドウを作成
        onion_window = ctk.CTkToplevel(self)
        onion_window.title("🔄 オニオンスキン - 重ね合わせ比較")
        onion_window.geometry("1200x900")
        onion_window.transient(self)
        
        # ヘッダー
        header = ctk.CTkFrame(onion_window, height=60, corner_radius=0, fg_color="#1A1A1A")
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🔄 オニオンスキン - 画像を重ね合わせて比較",
            font=("Meiryo", 16, "bold"),
            text_color="#FF6F00"
        ).pack(side="left", padx=20, pady=15)
        
        ctk.CTkLabel(
            header,
            text="💡 スライダーで透明度調整 | 矢印キー (↑↓←→) で位置調整",
            font=("Meiryo", 11),
            text_color="gray"
        ).pack(side="left", padx=20, pady=15)
        
        # メインエリア
        main_frame = ctk.CTkFrame(onion_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # InteractiveCanvasを作成
        onion_canvas = InteractiveCanvas(main_frame, width=1160, height=760)
        onion_canvas.pack(fill="both", expand=True)
        
        # 画像チェック
        if not web_page.screenshot_image or not pdf_page.page_image:
            messagebox.showwarning("警告", "画像データが見つかりません。")
            onion_window.destroy()
            return
        
        # オニオンスキンモードを有効化
        onion_canvas.enable_onion_skin_mode(
            base_image=web_page.screenshot_image,
            overlay_image=pdf_page.page_image,
            base_title=f"Web: {web_page.url[:50]}...",
            overlay_title=f"PDF: {Path(pdf_page.filename).name} (P.{pdf_page.page_num})"
        )
        
        # 閉じるボタン
        ctk.CTkButton(
            onion_window,
            text="閉じる",
            command=onion_window.destroy,
            width=150,
            height=35,
            font=("Meiryo", 12, "bold")
        ).pack(pady=10)
    
    def _reset_progress(self):
        """プログレスバーをリセット"""
        self.progress.stop()
        self.progress.pack_forget()
        self._update_step_status()
