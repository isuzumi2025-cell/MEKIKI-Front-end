"""
Phase 2: Dashboard (Matrix) 画面
WebとPDFのマッピング管理画面 - 実装版
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from typing import List, Dict, Optional
from PIL import Image
import threading

from app.core.pairing_manager import PairingManager
from app.core.pairing_manager import PairingManager
from app.core.crawler import WebCrawler
from app.utils.pdf_loader import PDFLoader
from app.gui.inspector import Inspector


class Dashboard(ctk.CTkToplevel):
    """Phase 2: マッピング管理画面（Dashboard） - 強化版"""
    
    def __init__(self, parent):
        """
        Args:
            parent: 親ウィンドウ
        """
        super().__init__(parent)
        
        self.title("📊 Dashboard - マッピング管理")
        self.geometry("1600x900")
        
        # マネージャー
        self.pairing_manager = PairingManager()
        # self.web_scraper = WebScraper() # 廃止: WebCrawlerを使用
        self.pdf_loader = PDFLoader()
        
        # データ
        self.web_pages: List[Dict] = []  # [{"id": int, "url": str, "title": str, "text": str, "image": Image}, ...]
        self.pdf_pages: List[Dict] = []  # [{"id": int, "filename": str, "page_num": int, "text": str, "image": Image}, ...]
        
        # 選択状態
        self.selected_web_id: Optional[int] = None
        self.selected_pdf_id: Optional[int] = None
        
        # プログレスバー
        self.progress = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """UI構築"""
        # ヘッダー
        self._build_header()
        
        # ツールバー
        self._build_toolbar()
        
        # メインエリア（左右分割）
        self._build_main_area()
        
        # ステータスバー
        self._build_status_bar()
    
    def _build_header(self):
        """ヘッダー構築"""
        header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color="#1A1A1A")
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="📊 Dashboard - マッピング管理",
            font=("Meiryo", 20, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=20, pady=20)
        
        ctk.CTkLabel(
            header,
            text="左からWebページ、右からPDFページを選択してペアリングしてください",
            font=("Meiryo", 11),
            text_color="gray"
        ).pack(side="left", padx=20, pady=20)
    
    def _build_toolbar(self):
        """ツールバー構築"""
        toolbar = ctk.CTkFrame(self, height=70, corner_radius=0)
        toolbar.pack(side="top", fill="x")
        toolbar.pack_propagate(False)
        
        # 左側: データ読み込みボタン
        left_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_frame.pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(
            left_frame,
            text="🌐 Webクロール",
            command=self.crawl_web,
            width=140,
            fg_color="#E08E00",
            hover_color="#D07E00"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            left_frame,
            text="📁 PDF読込",
            command=self.load_pdfs,
            width=140,
            fg_color="#4CAF50",
            hover_color="#45A049"
        ).pack(side="left", padx=5)
        
        # 中央: ペアリングボタン
        center_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        center_frame.pack(side="left", padx=20, pady=10)
        
        ctk.CTkButton(
            center_frame,
            text="🔗 手動ペアリング",
            command=self.create_manual_pair,
            width=150,
            fg_color="#2196F3",
            hover_color="#1976D2"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            center_frame,
            text="⚡ 自動マッチング",
            command=self.auto_match,
            width=150,
            fg_color="#9C27B0",
            hover_color="#7B1FA2"
        ).pack(side="left", padx=5)
        
        # 右側: アクションボタン
        right_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_frame.pack(side="right", padx=10, pady=10)
        
        ctk.CTkButton(
            right_frame,
            text="💡 Inspector使い方",
            command=self.open_inspector,
            width=150,
            fg_color="#757575",
            hover_color="#616161"
        ).pack(side="left", padx=5)
    
    def _build_main_area(self):
        """メインエリア構築"""
        main_paned = tk.PanedWindow(self, orient="horizontal", bg="#2B2B2B", sashwidth=4)
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左パネル: Webページリスト
        web_frame = ctk.CTkFrame(main_paned, corner_radius=0)
        main_paned.add(web_frame, width=540)
        
        ctk.CTkLabel(
            web_frame,
            text="🌐 Webページ一覧",
            font=("Meiryo", 14, "bold"),
            text_color="#E08E00"
        ).pack(pady=10)
        
        # Webページリスト（Treeview）
        web_tree_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        web_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.web_tree = ttk.Treeview(
            web_tree_frame,
            columns=("title", "status"),
            show="tree headings",
            height=25
        )
        self.web_tree.heading("#0", text="URL")
        self.web_tree.heading("title", text="タイトル")
        self.web_tree.heading("status", text="ペア")
        self.web_tree.column("#0", width=250)
        self.web_tree.column("title", width=200)
        self.web_tree.column("status", width=60)
        
        self.web_tree.bind("<<TreeviewSelect>>", self._on_web_select)
        
        web_scroll = tk.Scrollbar(web_tree_frame, orient="vertical", command=self.web_tree.yview)
        self.web_tree.configure(yscrollcommand=web_scroll.set)
        self.web_tree.pack(side="left", fill="both", expand=True)
        web_scroll.pack(side="right", fill="y")
        
        # 中央パネル: ペアリングリスト
        pair_frame = ctk.CTkFrame(main_paned, corner_radius=0)
        main_paned.add(pair_frame, width=480)
        
        ctk.CTkLabel(
            pair_frame,
            text="🔗 ペアリング結果",
            font=("Meiryo", 14, "bold"),
            text_color="#2196F3"
        ).pack(pady=10)
        
        # ペアリストはスクロール可能なフレーム内に配置
        self.pair_scroll_frame = ctk.CTkScrollableFrame(pair_frame, fg_color="transparent")
        self.pair_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 右パネル: PDFページリスト
        pdf_frame = ctk.CTkFrame(main_paned, corner_radius=0)
        main_paned.add(pdf_frame, width=540)
        
        ctk.CTkLabel(
            pdf_frame,
            text="📁 PDFページ一覧",
            font=("Meiryo", 14, "bold"),
            text_color="#4CAF50"
        ).pack(pady=10)
        
        # PDFページリスト（Treeview）
        pdf_tree_frame = ctk.CTkFrame(pdf_frame, fg_color="transparent")
        pdf_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.pdf_tree = ttk.Treeview(
            pdf_tree_frame,
            columns=("page", "status"),
            show="tree headings",
            height=25
        )
        self.pdf_tree.heading("#0", text="ファイル名")
        self.pdf_tree.heading("page", text="ページ")
        self.pdf_tree.heading("status", text="ペア")
        self.pdf_tree.column("#0", width=300)
        self.pdf_tree.column("page", width=80)
        self.pdf_tree.column("status", width=60)
        
        self.pdf_tree.bind("<<TreeviewSelect>>", self._on_pdf_select)
        
        pdf_scroll = tk.Scrollbar(pdf_tree_frame, orient="vertical", command=self.pdf_tree.yview)
        self.pdf_tree.configure(yscrollcommand=pdf_scroll.set)
        self.pdf_tree.pack(side="left", fill="both", expand=True)
        pdf_scroll.pack(side="right", fill="y")
    
    def _build_status_bar(self):
        """ステータスバー構築"""
        status_bar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#1A1A1A")
        status_bar.pack(side="bottom", fill="x")
        status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_bar,
            text="準備完了",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=20, pady=10)
        
        # プログレスバー
        self.progress = ctk.CTkProgressBar(
            status_bar,
            mode='indeterminate',
            width=200
        )
        self.progress.pack(side="right", padx=20, pady=10)
        self.progress.pack_forget()  # 初期状態で非表示
    
    def _on_web_select(self, event):
        """Webページ選択時のコールバック"""
        selection = self.web_tree.selection()
        if selection:
            item = selection[0]
            tags = self.web_tree.item(item, "tags")
            if tags:
                self.selected_web_id = int(tags[0])
                print(f"Web選択: ID={self.selected_web_id}")
    
    def _on_pdf_select(self, event):
        """PDFページ選択時のコールバック"""
        selection = self.pdf_tree.selection()
        if selection:
            item = selection[0]
            tags = self.pdf_tree.item(item, "tags")
            if tags:
                self.selected_pdf_id = int(tags[0])
                print(f"PDF選択: ID={self.selected_pdf_id}")
    
    def crawl_web(self):
        """Webクロール設定ダイアログ"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Web一括クロール設定")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="Web一括クロール設定",
            font=("Meiryo", 16, "bold")
        ).pack(pady=15)
        
        # URL入力
        ctk.CTkLabel(dialog, text="開始URL:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_url = ctk.CTkEntry(dialog, placeholder_text="https://example.com")
        entry_url.pack(fill="x", padx=20, pady=5)
        
        # 認証情報
        auth_frame = ctk.CTkFrame(dialog)
        auth_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(
            auth_frame,
            text="🔒 Basic認証 (必要な場合のみ)",
            font=("Meiryo", 11, "bold")
        ).pack(pady=5)
        
        ctk.CTkLabel(auth_frame, text="ユーザー名:", anchor="w").pack(fill="x", padx=10)
        entry_user = ctk.CTkEntry(auth_frame)
        entry_user.pack(fill="x", padx=10, pady=(0, 5))
        
        ctk.CTkLabel(auth_frame, text="パスワード:", anchor="w").pack(fill="x", padx=10)
        entry_pass = ctk.CTkEntry(auth_frame, show="*")
        entry_pass.pack(fill="x", padx=10, pady=(0, 10))
        
        # 詳細設定
        settings_frame = ctk.CTkFrame(dialog)
        settings_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(
            settings_frame,
            text="⚙️ 詳細設定",
            font=("Meiryo", 11, "bold")
        ).pack(pady=5)
        
        ctk.CTkLabel(settings_frame, text="最大ページ数:", anchor="w").pack(fill="x", padx=10)
        entry_max = ctk.CTkEntry(settings_frame, placeholder_text="50")
        entry_max.insert(0, "50")
        entry_max.pack(fill="x", padx=10, pady=(0, 5))
        
        ctk.CTkLabel(settings_frame, text="最大深さ:", anchor="w").pack(fill="x", padx=10)
        entry_depth = ctk.CTkEntry(settings_frame, placeholder_text="3")
        entry_depth.insert(0, "3")
        entry_depth.pack(fill="x", padx=10, pady=(0, 10))
        
        def on_execute():
            url = entry_url.get().strip()
            if not url:
                messagebox.showwarning("必須", "開始URLを入力してください", parent=dialog)
                return
            
            try:
                max_pages = int(entry_max.get().strip() or "50")
                max_depth = int(entry_depth.get().strip() or "3")
            except ValueError:
                messagebox.showwarning("エラー", "数値を正しく入力してください", parent=dialog)
                return
            
            user = entry_user.get().strip() or None
            pw = entry_pass.get().strip() or None
            
            dialog.destroy()
            self._run_crawl(url, max_pages, max_depth, user, pw)
        
        # ボタン
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=20)
        
        ctk.CTkButton(
            button_frame,
            text="実行",
            command=on_execute,
            width=120,
            fg_color="#E08E00",
            hover_color="#D07E00"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            button_frame,
            text="キャンセル",
            command=dialog.destroy,
            width=120,
            fg_color="gray"
        ).pack(side="left", padx=10)
    
    def _run_crawl(self, url, max_pages, max_depth, username, password):
        """Webクロールを実行（バックグラウンド）"""
        self.progress.pack(side="right", padx=20, pady=10)
        self.progress.start()
        self.status_label.configure(text="クローリング中...")
        
        def progress_callback(current, total, current_url):
            msg = f"クローリング中... [{current}/{total}] {current_url[:50]}..."
            self.after(0, lambda: self.status_label.configure(text=msg))
        
        def crawl_thread():
            try:
                # WebCrawlerを使用 (Smart Stitching対応)
                crawler = WebCrawler(
                    max_pages=max_pages,
                    max_depth=max_depth,
                    username=username,
                    password=password,
                    delay=1.0
                )
                
                # プログレス表示用ラッパー
                def _progress_wrapper(url, current, total):
                    progress_callback(current, max_pages, url) # totalはmax_pagesとして扱う
                
                results = crawler.crawl(
                    root_url=url,
                    progress_callback=_progress_wrapper
                )
                
                # データを格納 (crawlerのresult形式に合わせて変換)
                # Crawler returns: [{"url":.., "title":.., "text":.., "screenshot_image":.., "full_image":.., "error":..}]
                self.web_pages = []
                for idx, result in enumerate(results):
                    # 画像データの検証
                    # 優先してStitched Full Imageを使用
                    full_img = result.get("full_image")
                    if full_img is None:
                         # フォールバック: Viewport Image
                         full_img = result.get("screenshot_image")
                    
                    viewport_img = result.get("screenshot_image")
                    
                    # Noneの場合はプレースホルダーを作成
                    if full_img is None:
                        print(f"⚠️ 警告: {result['url']} の画像がNoneです")
                        from PIL import Image, ImageDraw
                        full_img = Image.new('RGB', (1280, 800), color='#2B2B2B')
                        draw = ImageDraw.Draw(full_img)
                        draw.rectangle([50, 50, 1230, 750], outline='#FF4444', width=5)
                        draw.text((640, 400), "⚠️ 画像なし", fill='#FF4444', anchor="mm")
                    
                    if viewport_img is None:
                        viewport_img = full_img  # フォールバック
                    
                    self.web_pages.append({
                        "id": idx + 1,
                        "url": result["url"],
                        "title": result["title"],
                        "text": result["text"],
                        "image": full_img,
                        "viewport_image": viewport_img,
                        "depth": result.get("depth", 0),
                        "error": result.get("error")
                    })
                
                # UI更新
                self.after(0, self._refresh_web_tree)
                self.after(0, lambda: messagebox.showinfo(
                    "完了",
                    f"{len(results)}ページ取得しました"
                ))
                self.after(0, lambda: self.status_label.configure(
                    text=f"クローリング完了: {len(results)}ページ"
                ))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
                self.after(0, lambda: self.status_label.configure(text="エラー発生"))
            finally:
                self.after(0, self.progress.stop)
                self.after(0, self.progress.pack_forget)
        
        threading.Thread(target=crawl_thread, daemon=True).start()
    
    def _refresh_web_tree(self):
        """Webページリストを更新"""
        # 既存項目をクリア
        for item in self.web_tree.get_children():
            self.web_tree.delete(item)
        
        # データを追加
        for page in self.web_pages:
            error = page.get("error")
            if error:
                # エラーは赤で表示
                self.web_tree.insert(
                    "",
                    "end",
                    text=f"❌ {page['url'][:40]}...",
                    values=(f"取得失敗", ""),
                    tags=(str(page["id"]), "error")
                )
                self.web_tree.tag_configure("error", foreground="red")
            else:
                pair = self.pairing_manager.get_pair_by_web_id(page["id"])
                status = "✓" if pair else ""
                self.web_tree.insert(
                    "",
                    "end",
                    text=page["url"],
                    values=(page["title"], status),
                    tags=(str(page["id"]),)
                )
    
    def load_pdfs(self):
        """PDF読込設定ダイアログ"""
        folder_path = filedialog.askdirectory(title="PDFフォルダを選択")
        if folder_path:
            self._run_load_pdfs(folder_path)
    
    def _run_load_pdfs(self, folder_path):
        """PDF読込を実行（バックグラウンド）"""
        self.progress.pack(side="right", padx=20, pady=10)
        self.progress.start()
        self.status_label.configure(text="PDF読込中...")
        
        def load_thread():
            try:
                results = self.pdf_loader.load_pdfs_from_folder(
                    folder_path,
                    recursive=True
                )
                
                # データを格納
                self.pdf_pages = []
                for idx, result in enumerate(results):
                    # 画像データの検証（念のため）
                    page_img = result.get("page_image")
                    
                    # Noneの場合はプレースホルダーを作成
                    if page_img is None:
                        print(f"⚠️ 警告: {result['filename']} P.{result['page_num']} の画像がNoneです")
                        from PIL import Image, ImageDraw
                        page_img = Image.new('RGB', (800, 600), color='#2B2B2B')
                        draw = ImageDraw.Draw(page_img)
                        draw.rectangle([50, 50, 750, 550], outline='#FF4444', width=5)
                        draw.text((400, 300), "⚠️ 画像なし", fill='#FF4444', anchor="mm")
                    
                    self.pdf_pages.append({
                        "id": idx + 1,
                        "filename": result["filename"],
                        "page_num": result["page_num"],
                        "text": result["text"],
                        "image": page_img,
                        "areas": result.get("areas", [])
                    })
                
                # UI更新
                self.after(0, self._refresh_pdf_tree)
                self.after(0, lambda: messagebox.showinfo(
                    "完了",
                    f"{len(results)}ページ読み込みました"
                ))
                self.after(0, lambda: self.status_label.configure(
                    text=f"PDF読込完了: {len(results)}ページ"
                ))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
                self.after(0, lambda: self.status_label.configure(text="エラー発生"))
            finally:
                self.after(0, self.progress.stop)
                self.after(0, self.progress.pack_forget)
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _refresh_pdf_tree(self):
        """PDFページリストを更新"""
        # 既存項目をクリア
        for item in self.pdf_tree.get_children():
            self.pdf_tree.delete(item)
        
        # データを追加
        from pathlib import Path
        for page in self.pdf_pages:
            filename = Path(page["filename"]).name
            pair = self.pairing_manager.get_pair_by_pdf_id(page["id"])
            status = "✓" if pair else ""
            self.pdf_tree.insert(
                "",
                "end",
                text=filename,
                values=(f"P.{page['page_num']}", status),
                tags=(str(page["id"]),)
            )
    
    def create_manual_pair(self):
        """手動ペアリング"""
        if self.selected_web_id is None or self.selected_pdf_id is None:
            messagebox.showwarning("警告", "WebページとPDFページの両方を選択してください")
            return
        
        # 選択されたページを検索
        web_page = next((p for p in self.web_pages if p["id"] == self.selected_web_id), None)
        pdf_page = next((p for p in self.pdf_pages if p["id"] == self.selected_pdf_id), None)
        
        if not web_page or not pdf_page:
            messagebox.showerror("エラー", "選択されたページが見つかりません")
            return
        
        # エラーページはペアリング不可
        if web_page.get("error"):
            messagebox.showwarning("警告", "取得に失敗したWebページはペアリングできません")
            return
        
        # ペアを作成
        from pathlib import Path
        pair_id = self.pairing_manager.add_pair(
            web_id=web_page["id"],
            pdf_id=pdf_page["id"],
            web_url=web_page["url"],
            pdf_filename=pdf_page["filename"],
            pdf_page_num=pdf_page["page_num"],
            similarity_score=0.0,
            is_manual=True,
            notes="手動ペアリング"
        )
        
        # UI更新
        self._refresh_web_tree()
        self._refresh_pdf_tree()
        self._refresh_pair_list()
        
        messagebox.showinfo(
            "手動ペアリング完了",
            f"✅ ペアリングを作成しました (ID: {pair_id})\n\n"
            "【次のステップ】\n"
            "中央のペアリング結果から「🔍 Inspector」ボタンを\n"
            "クリックして詳細比較を開始できます。"
        )
    
    def _refresh_pair_list(self):
        """ペアリストを更新"""
        # 既存項目をクリア
        for widget in self.pair_scroll_frame.winfo_children():
            widget.destroy()
        
        # ペアを取得
        pairs = self.pairing_manager.get_all_pairs()
        
        if not pairs:
            ctk.CTkLabel(
                self.pair_scroll_frame,
                text="ペアリングがありません\n\n左右のリストから項目を選択して\n「手動ペアリング」または\n「自動マッチング」を実行してください",
                font=("Meiryo", 12),
                text_color="gray"
            ).pack(pady=50)
            return
        
        # ペアカードを表示
        from pathlib import Path
        for pair in pairs:
            card = ctk.CTkFrame(self.pair_scroll_frame, fg_color="#2B2B2B")
            card.pack(fill="x", padx=5, pady=5)
            
            # ヘッダー
            header = ctk.CTkFrame(card, fg_color="#1A1A1A")
            header.pack(fill="x", padx=5, pady=5)
            
            ctk.CTkLabel(
                header,
                text=f"ペア #{pair.pair_id}",
                font=("Meiryo", 10, "bold")
            ).pack(side="left", padx=10, pady=5)
            
            # 類似度バッジ
            score_color = "#4CAF50" if pair.similarity_score >= 0.7 else "#FFA500" if pair.similarity_score >= 0.3 else "#FF4444"
            ctk.CTkLabel(
                header,
                text=f"{pair.similarity_score:.1%}",
                font=("Meiryo", 9, "bold"),
                text_color=score_color
            ).pack(side="right", padx=10, pady=5)
            
            # 内容
            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(
                content,
                text=f"🌐 {pair.web_url[:40]}...",
                font=("Meiryo", 9),
                anchor="w"
            ).pack(fill="x")
            
            pdf_name = Path(pair.pdf_filename).name
            ctk.CTkLabel(
                content,
                text=f"📁 {pdf_name} (P.{pair.pdf_page_num})",
                font=("Meiryo", 9),
                anchor="w"
            ).pack(fill="x")
            
            # ボタン
            button_frame = ctk.CTkFrame(card, fg_color="transparent")
            button_frame.pack(fill="x", padx=5, pady=5)
            
            ctk.CTkButton(
                button_frame,
                text="🔍 Inspector",
                command=lambda p=pair: self._open_inspector_for_pair(p),
                width=100,
                height=25,
                fg_color="#FF6F00",
                hover_color="#E65100"
            ).pack(side="left", padx=5)
            
            ctk.CTkButton(
                button_frame,
                text="削除",
                command=lambda p=pair: self._delete_pair(p.pair_id),
                width=80,
                height=25,
                fg_color="#B71C1C",
                hover_color="#8B0000"
            ).pack(side="right", padx=5)
    
    def _delete_pair(self, pair_id):
        """ペアを削除"""
        if messagebox.askyesno("確認", "このペアリングを削除しますか?"):
            self.pairing_manager.remove_pair(pair_id)
            self._refresh_web_tree()
            self._refresh_pdf_tree()
            self._refresh_pair_list()
            messagebox.showinfo("完了", "ペアリングを削除しました")
    
    def _open_inspector_for_pair(self, pair):
        """指定したペアのInspectorを開く"""
        # WebページとPDFページを検索
        web_page = next((p for p in self.web_pages if p["id"] == pair.web_id), None)
        pdf_page = next((p for p in self.pdf_pages if p["id"] == pair.pdf_id), None)
        
        if not web_page or not pdf_page:
            messagebox.showerror("エラー", "ページデータが見つかりません")
            return
        
        # Inspectorを開く
        inspector = Inspector(self, web_page, pdf_page)
        inspector.lift()
    
    def auto_match(self):
        """自動マッチング"""
        if not self.web_pages or not self.pdf_pages:
            messagebox.showwarning("警告", "WebページとPDFページの両方を読み込んでください")
            return
        
        self.progress.pack(side="right", padx=20, pady=10)
        self.progress.start()
        self.status_label.configure(text="自動マッチング中...")
        
        def match_thread():
            try:
                # WebページとPDFページを変換
                web_data = [
                    {
                        "id": p["id"],
                        "url": p["url"],
                        "text": p["text"]
                    }
                    for p in self.web_pages
                    if not p.get("error")  # エラーページは除外
                ]
                
                pdf_data = [
                    {
                        "id": p["id"],
                        "filename": p["filename"],
                        "page_num": p["page_num"],
                        "text": p["text"]
                    }
                    for p in self.pdf_pages
                ]
                
                # マッチング実行
                matched_pairs = self.pairing_manager.auto_match(
                    web_pages=web_data,
                    pdf_pages=pdf_data,
                    threshold=0.1  # 緩い閾値
                )
                
                # UI更新
                self.after(0, self._refresh_web_tree)
                self.after(0, self._refresh_pdf_tree)
                self.after(0, self._refresh_pair_list)
                self.after(0, lambda: messagebox.showinfo(
                    "自動マッチング完了",
                    f"✅ {len(matched_pairs)}件のペアを作成しました\n\n"
                    "【次のステップ】\n"
                    "中央のペアリング結果から、詳細比較したいペアの\n"
                    "「🔍 Inspector」ボタンをクリックしてください。"
                ))
                self.after(0, lambda: self.status_label.configure(
                    text=f"自動マッチング完了: {len(matched_pairs)}ペア"
                ))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
                self.after(0, lambda: self.status_label.configure(text="エラー発生"))
            finally:
                self.after(0, self.progress.stop)
                self.after(0, self.progress.pack_forget)
        
        threading.Thread(target=match_thread, daemon=True).start()
    
    def open_inspector(self):
        """選択されたペアのInspectorを起動"""
        pairs = self.pairing_manager.get_all_pairs()
        if not pairs:
            messagebox.showwarning("警告", "ペアリングが作成されていません")
            return
        
        # ユーザーに選択を促す（自動で開かない）
        messagebox.showinfo(
            "Inspector起動",
            f"{len(pairs)}件のペアが作成されています。\n\n"
            "ペアリング結果リストから「🔍 Inspector」ボタンをクリックして、\n"
            "詳細比較を行いたいペアを選択してください。"
        )

