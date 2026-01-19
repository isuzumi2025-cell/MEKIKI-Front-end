"""
比較マトリクスビュー (2x3)
Web/PDF画像・テキスト・比較結果を6パネルで表示
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Callable, Tuple
from PIL import Image, ImageTk
import io
import base64


class ComparisonMatrixWindow(ctk.CTkToplevel):
    """
    比較マトリクスウィンドウ - 分離可能
    2x3レイアウト: 
    - 上段: Web画像 | PDF画像 | 比較結果
    - 下段: Webテキスト | PDFテキスト | 校正ヒント
    """
    
    def __init__(self, parent, comparison_queue: Optional[List[Dict]] = None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.parent_app = parent  # UnifiedAppへの参照
        self.comparison_queue = comparison_queue or []
        
        # データ
        self.web_image: Optional[Image.Image] = None
        self.pdf_image: Optional[Image.Image] = None
        self.web_text: str = ""
        self.pdf_text: str = ""
        self.comparison_result: Optional[Dict] = None
        
        # ウィンドウ設定
        self.title("⚖️ 比較マトリクス")
        self.geometry("1400x900")
        self.minsize(800, 600)
        
        self._build_ui()
        
        # キューからデータを自動ロード
        if self.comparison_queue:
            self.after(500, self._load_from_queue)
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="⚖️ 比較マトリクス (2x3)",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        # ツールバー
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=10)
        
        ctk.CTkButton(
            toolbar, text="🔄 比較実行", width=100, fg_color="#FF6F00",
            command=self._run_comparison
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="📤 エクスポート", width=100, fg_color="#2196F3",
            command=self._export_results
        ).pack(side="left", padx=5)
        
        # 2x3マトリクス
        self.matrix_frame = ctk.CTkFrame(self, fg_color="#2B2B2B")
        self.matrix_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # グリッド設定 (3列 x 2行)
        self.matrix_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.matrix_frame.grid_rowconfigure((0, 1), weight=1, uniform="row")
        
        # 上段パネル
        self.web_canvas_panel = self._create_panel(
            self.matrix_frame, "🌐 Web Capture", 0, 0
        )
        self.pdf_canvas_panel = self._create_panel(
            self.matrix_frame, "📄 PDF Preview", 0, 1
        )
        self.diff_panel = self._create_panel(
            self.matrix_frame, "🔍 比較結果", 0, 2
        )
        
        # 下段パネル
        self.web_text_panel = self._create_panel(
            self.matrix_frame, "📝 Web Text", 1, 0
        )
        self.pdf_text_panel = self._create_panel(
            self.matrix_frame, "📝 PDF Text", 1, 1
        )
        self.hints_panel = self._create_panel(
            self.matrix_frame, "💡 校正ヒント", 1, 2
        )
        
        # パネル内コンテンツ構築
        self._build_canvas_panel(self.web_canvas_panel, "web")
        self._build_canvas_panel(self.pdf_canvas_panel, "pdf")
        self._build_diff_panel(self.diff_panel)
        self._build_text_panel(self.web_text_panel, "web")
        self._build_text_panel(self.pdf_text_panel, "pdf")
        self._build_hints_panel(self.hints_panel)
        
        # ステータスバー
        self.status_bar = ctk.CTkFrame(self, height=25, fg_color="#1A1A1A")
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Web/PDFを読み込んで比較を開始してください",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=10)
        
        self.sync_rate_label = ctk.CTkLabel(
            self.status_bar,
            text="Sync Rate: ---%",
            font=("Meiryo", 10, "bold"),
            text_color="gray"
        )
        self.sync_rate_label.pack(side="right", padx=10)
    
    def _create_panel(self, parent, title: str, row: int, col: int) -> ctk.CTkFrame:
        """パネルを作成"""
        panel = ctk.CTkFrame(parent, fg_color="#2D2D2D", corner_radius=10)
        panel.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        
        # ヘッダー
        header = ctk.CTkFrame(panel, fg_color="#383838", height=35, corner_radius=10)
        header.pack(fill="x", padx=3, pady=3)
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text=title, font=("Meiryo", 11, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        # コンテンツエリア
        content = ctk.CTkFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=5, pady=5)
        
        panel.content = content
        return panel
    
    def _build_canvas_panel(self, panel: ctk.CTkFrame, source: str):
        """画像キャンバスパネル構築"""
        content = panel.content
        
        # キャンバス
        canvas = ctk.CTkCanvas(content, bg="#1E1E1E", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        # スクロールバー
        h_scroll = ttk.Scrollbar(content, orient="horizontal", command=canvas.xview)
        v_scroll = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        # プレースホルダー
        canvas.create_text(
            200, 150,
            text=f"{'🌐 Web' if source == 'web' else '📄 PDF'}画像をドロップ\nまたはクリックして選択",
            fill="gray",
            font=("Meiryo", 12)
        )
        
        if source == "web":
            self.web_canvas = canvas
        else:
            self.pdf_canvas = canvas
        
        # クリックイベント
        canvas.bind("<Button-1>", lambda e: self._on_canvas_click(source))
        
        # スクロール同期設定
        canvas.bind("<MouseWheel>", lambda e: self._sync_scroll(e, source))
    
    def _build_diff_panel(self, panel: ctk.CTkFrame):
        """比較結果パネル構築"""
        content = panel.content
        
        # Sync Rate大きく表示
        self.sync_display = ctk.CTkLabel(
            content,
            text="---%",
            font=("Meiryo", 48, "bold"),
            text_color="gray"
        )
        self.sync_display.pack(pady=20)
        
        ctk.CTkLabel(
            content,
            text="Sync Rate",
            font=("Meiryo", 12),
            text_color="gray"
        ).pack()
        
        # Diff統計
        self.diff_stats = ctk.CTkLabel(
            content,
            text="追加: -- | 削除: -- | 変更: --",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.diff_stats.pack(pady=10)
        
        # Diff詳細スクロール
        self.diff_text = ctk.CTkTextbox(
            content,
            font=("Consolas", 10),
            fg_color="#1E1E1E"
        )
        self.diff_text.pack(fill="both", expand=True, pady=10)
    
    def _build_text_panel(self, panel: ctk.CTkFrame, source: str):
        """テキストパネル構築"""
        content = panel.content
        
        # テキストボックス
        textbox = ctk.CTkTextbox(
            content,
            font=("Meiryo", 11),
            fg_color="#1E1E1E"
        )
        textbox.pack(fill="both", expand=True)
        
        if source == "web":
            self.web_textbox = textbox
            textbox.insert("1.0", "Webテキストがここに表示されます...")
        else:
            self.pdf_textbox = textbox
            textbox.insert("1.0", "PDFテキストがここに表示されます...")
        
        # テキスト選択時のハイライト連動
        textbox.bind("<<Selection>>", lambda e: self._on_text_select(source))
    
    def _build_hints_panel(self, panel: ctk.CTkFrame):
        """校正ヒントパネル構築"""
        content = panel.content
        
        self.hints_list = ctk.CTkScrollableFrame(
            content, fg_color="transparent"
        )
        self.hints_list.pack(fill="both", expand=True)
        
        # プレースホルダー
        ctk.CTkLabel(
            self.hints_list,
            text="比較を実行すると\n校正ヒントが表示されます",
            font=("Meiryo", 11),
            text_color="gray"
        ).pack(pady=30)
    
    def _on_canvas_click(self, source: str):
        """キャンバスクリック時"""
        from tkinter import filedialog
        
        if source == "web":
            # 画像選択 or 既存ジョブから
            file_path = filedialog.askopenfilename(
                title="Web画像を選択",
                filetypes=[("画像", "*.png *.jpg *.jpeg *.webp"), ("全て", "*.*")]
            )
            if file_path:
                self._load_web_image(file_path)
        else:
            file_path = filedialog.askopenfilename(
                title="PDF/画像を選択",
                filetypes=[("PDF/画像", "*.pdf *.png *.jpg *.jpeg"), ("全て", "*.*")]
            )
            if file_path:
                self._load_pdf(file_path)
    
    def _sync_scroll(self, event, source: str):
        """スクロール同期"""
        # 相互スクロール
        if source == "web" and hasattr(self, 'pdf_canvas'):
            self.pdf_canvas.yview_scroll(-1 * (event.delta // 120), "units")
        elif source == "pdf" and hasattr(self, 'web_canvas'):
            self.web_canvas.yview_scroll(-1 * (event.delta // 120), "units")
    
    def _on_text_select(self, source: str):
        """テキスト選択時"""
        # TODO: 対応する画像領域をハイライト
        pass
    
    def _load_web_image(self, path: str):
        """Web画像読み込み"""
        try:
            img = Image.open(path)
            self.web_image = img
            self._display_image(self.web_canvas, img)
            self.status_label.configure(text=f"🌐 Web画像読込完了: {path}")
        except Exception as e:
            self.status_label.configure(text=f"❌ 画像読込エラー: {e}")
    
    def _load_pdf(self, path: str):
        """PDF/画像読み込み"""
        try:
            if path.lower().endswith('.pdf'):
                # PDF -> 画像変換 (pymupdf使用)
                import fitz
                doc = fitz.open(path)
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                self.pdf_text = page.get_text()
                self.pdf_textbox.delete("1.0", "end")
                self.pdf_textbox.insert("1.0", self.pdf_text)
            else:
                img = Image.open(path)
            
            self.pdf_image = img
            self._display_image(self.pdf_canvas, img)
            self.status_label.configure(text=f"📄 PDF読込完了: {path}")
        except Exception as e:
            self.status_label.configure(text=f"❌ PDF読込エラー: {e}")
    
    def _display_image(self, canvas: ctk.CTkCanvas, img: Image.Image):
        """画像をキャンバスに表示"""
        # リサイズ
        canvas_width = canvas.winfo_width() or 400
        canvas_height = canvas.winfo_height() or 300
        
        img_copy = img.copy()
        img_copy.thumbnail((canvas_width * 2, canvas_height * 2))
        
        photo = ImageTk.PhotoImage(img_copy)
        
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.image = photo
        
        # スクロール領域設定
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    def _run_comparison(self):
        """比較実行"""
        if not self.web_text:
            self.web_text = self.web_textbox.get("1.0", "end").strip()
        if not self.pdf_text:
            self.pdf_text = self.pdf_textbox.get("1.0", "end").strip()
        
        if not self.web_text or not self.pdf_text:
            self.status_label.configure(text="⚠️ 両方のテキストが必要です")
            return
        
        # Diff計算
        from difflib import SequenceMatcher
        
        matcher = SequenceMatcher(None, self.web_text, self.pdf_text)
        ratio = matcher.ratio()
        
        # Sync Rate更新
        sync_rate = int(ratio * 100)
        self.sync_display.configure(text=f"{sync_rate}%")
        self.sync_rate_label.configure(text=f"Sync Rate: {sync_rate}%")
        
        # 色設定
        if sync_rate >= 90:
            color = "#4CAF50"  # 緑
        elif sync_rate >= 70:
            color = "#FF9800"  # 橙
        else:
            color = "#F44336"  # 赤
        
        self.sync_display.configure(text_color=color)
        self.sync_rate_label.configure(text_color=color)
        
        # Diff詳細
        self.diff_text.delete("1.0", "end")
        
        opcodes = matcher.get_opcodes()
        added = deleted = changed = 0
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                self.diff_text.insert("end", self.web_text[i1:i2])
            elif tag == 'replace':
                self.diff_text.insert("end", f"[-{self.web_text[i1:i2]}-]", "deleted")
                self.diff_text.insert("end", f"[+{self.pdf_text[j1:j2]}+]", "added")
                changed += 1
            elif tag == 'delete':
                self.diff_text.insert("end", f"[-{self.web_text[i1:i2]}-]", "deleted")
                deleted += 1
            elif tag == 'insert':
                self.diff_text.insert("end", f"[+{self.pdf_text[j1:j2]}+]", "added")
                added += 1
        
        self.diff_stats.configure(text=f"追加: {added} | 削除: {deleted} | 変更: {changed}")
        
        # 校正ヒント生成
        self._generate_hints(sync_rate, added, deleted, changed)
        
        self.status_label.configure(text="✅ 比較完了")
    
    def _generate_hints(self, sync_rate: int, added: int, deleted: int, changed: int):
        """校正ヒント生成"""
        # クリア
        for widget in self.hints_list.winfo_children():
            widget.destroy()
        
        hints = []
        
        if sync_rate < 50:
            hints.append(("🚨 重大な差異", "Sync Rateが50%未満です。大幅な内容変更があります。"))
        elif sync_rate < 80:
            hints.append(("⚠️ 注意", "Sync Rateが80%未満です。確認が必要です。"))
        else:
            hints.append(("✅ 良好", "内容はほぼ一致しています。"))
        
        if added > 5:
            hints.append(("➕ 追加が多い", f"{added}箇所で追加があります。"))
        if deleted > 5:
            hints.append(("➖ 削除が多い", f"{deleted}箇所で削除があります。"))
        
        for title, desc in hints:
            card = ctk.CTkFrame(self.hints_list, fg_color="#3A3A3A", corner_radius=8)
            card.pack(fill="x", pady=3)
            
            ctk.CTkLabel(
                card, text=title, font=("Meiryo", 11, "bold")
            ).pack(anchor="w", padx=10, pady=(8, 2))
            
            ctk.CTkLabel(
                card, text=desc, font=("Meiryo", 10), text_color="gray"
            ).pack(anchor="w", padx=10, pady=(0, 8))
    
    def _export_results(self):
        """結果をエクスポート"""
        from tkinter import messagebox
        messagebox.showinfo("エクスポート", "レポートエディターで編集後、エクスポートできます\n(Phase 5で実装)")
    
    def set_web_data(self, image: Optional[Image.Image], text: str, url: str = ""):
        """Webデータを設定"""
        if image:
            self.web_image = image
            self._display_image(self.web_canvas, image)
        if text:
            self.web_text = text
            self.web_textbox.delete("1.0", "end")
            self.web_textbox.insert("1.0", text)
    
    def set_pdf_data(self, image: Optional[Image.Image], text: str, path: str = ""):
        """PDFデータを設定"""
        if image:
            self.pdf_image = image
            self._display_image(self.pdf_canvas, image)
        if text:
            self.pdf_text = text
            self.pdf_textbox.delete("1.0", "end")
            self.pdf_textbox.insert("1.0", text)
    
    def _load_from_queue(self):
        """キューからWebデータをロード"""
        if not self.comparison_queue:
            return
        
        # 最初のWebアイテムを取得
        web_item = None
        for item in self.comparison_queue:
            if item.get('type') == 'web':
                web_item = item
                break
        
        if not web_item:
            self.status_label.configure(text="⚠️ キューにWebページがありません")
            return
        
        # テキストをロード (text_content優先、後方互換性のためtextもチェック)
        text = web_item.get('text_content') or web_item.get('text', '')
        if text:
            self.web_text = text
            self.web_textbox.delete("1.0", "end")
            self.web_textbox.insert("1.0", text)
        
        # スクリーンショットをロード (base64から)
        screenshot_b64 = web_item.get('screenshot_base64')
        if screenshot_b64:
            try:
                img_data = base64.b64decode(screenshot_b64)
                img = Image.open(io.BytesIO(img_data))
                self.web_image = img
                self._display_image(self.web_canvas, img)
            except Exception as e:
                print(f"⚠️ スクリーンショット読み込みエラー: {e}")
        
        url = web_item.get('url', '')[:50]
        self.status_label.configure(text=f"✅ Webデータロード完了: {url}...")
        print(f"📥 キューからWebデータをロード: {web_item.get('url', '')} (テキスト: {len(text)}文字)")


class ComparisonMatrixFrame(ctk.CTkFrame):
    """比較マトリクス - 埋め込み用フレーム版"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.parent_app = parent.winfo_toplevel()  # UnifiedAppへの参照
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="⚖️ 比較マトリクス",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        # キュー件数表示
        self.queue_label = ctk.CTkLabel(
            header,
            text="キュー: 0件",
            font=("Meiryo", 11),
            text_color="gray"
        )
        self.queue_label.pack(side="left", padx=20)
        
        ctk.CTkButton(
            header,
            text="↗️ 別ウィンドウで開く",
            command=self._open_window,
            fg_color="#616161"
        ).pack(side="right", padx=15)
        
        # 簡易表示エリア
        content = ctk.CTkFrame(self, fg_color="#2D2D2D")
        content.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            content,
            text="サイトマップビューワーでページを選択して\n「⚖️ 比較に追加」するとキューに追加されます\n\n「別ウィンドウで開く」で比較を開始",
            font=("Meiryo", 12),
            text_color="gray"
        ).place(relx=0.5, rely=0.5, anchor="center")
        
        # キュー件数を更新
        self.after(1000, self._update_queue_count)
    
    def _update_queue_count(self):
        """キュー件数を更新"""
        if hasattr(self.parent_app, 'comparison_queue'):
            count = len(self.parent_app.comparison_queue)
            self.queue_label.configure(text=f"キュー: {count}件")
        self.after(2000, self._update_queue_count)
    
    def _open_window(self):
        """別ウィンドウで開く - キューを渡す"""
        queue = []
        if hasattr(self.parent_app, 'comparison_queue'):
            queue = self.parent_app.comparison_queue
        
        window = ComparisonMatrixWindow(
            self.parent_app,
            comparison_queue=queue
        )
        window.focus()

