"""
詳細インスペクター - 刷新版
Web/PDF並列表示、パラグラフ矩形ハイライト、テキストDiff比較
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Tuple
from PIL import Image, ImageTk, ImageDraw
from dataclasses import dataclass
import difflib
import io
import base64


@dataclass
class ParagraphRegion:
    """パラグラフ領域"""
    id: int
    rect: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    text: str
    sync_id: Optional[int] = None
    similarity: float = 0.0


class DetailInspectorWindow(ctk.CTkToplevel):
    """
    詳細インスペクター - 刷新版
    Web/PDF並列表示、パラグラフハイライト、Diff比較
    """
    
    # シンク色パレット
    SYNC_COLORS = [
        "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#00BCD4",
        "#E91E63", "#CDDC39", "#FF5722", "#607D8B", "#795548"
    ]
    
    def __init__(self, parent, web_data: Dict = None, pdf_data: Dict = None, **kwargs):
        super().__init__(parent, **kwargs)
        
        # データ
        self.web_image: Optional[Image.Image] = None
        self.pdf_image: Optional[Image.Image] = None
        self.web_regions: List[ParagraphRegion] = []
        self.pdf_regions: List[ParagraphRegion] = []
        self.selected_web_region: Optional[ParagraphRegion] = None
        self.selected_pdf_region: Optional[ParagraphRegion] = None
        
        # PhotoImage参照保持
        self._web_photo = None
        self._pdf_photo = None
        
        # ウィンドウ設定
        self.title("🔬 詳細インスペクター")
        self.geometry("1400x900")
        self.minsize(1000, 700)
        
        self._build_ui()
        
        # 初期データを保存
        self._pending_web_data = web_data
        self._pending_pdf_data = pdf_data
        
        # 遅延ロード (キャンバスサイズ確定後)
        self.after(200, self._delayed_load_data)
    
    def _delayed_load_data(self):
        """遅延データロード - キャンバスサイズ確定後に実行"""
        if self._pending_web_data:
            self.load_web_data(self._pending_web_data)
        if self._pending_pdf_data:
            self.load_pdf_data(self._pending_pdf_data)
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🔬 詳細インスペクター",
            font=("Meiryo", 18, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=20, pady=12)
        
        # Sync Rate表示
        self.sync_rate_label = ctk.CTkLabel(
            header,
            text="Sync Rate: ---%",
            font=("Meiryo", 14, "bold"),
            text_color="#888888"
        )
        self.sync_rate_label.pack(side="left", padx=30)
        
        # ツールバー
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=15)
        
        ctk.CTkButton(
            toolbar, text="🔄 OCR実行", width=100, fg_color="#FF6F00",
            font=("Meiryo", 11, "bold"),
            command=self._run_ocr
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="🔗 Sync計算", width=100, fg_color="#2196F3",
            font=("Meiryo", 11, "bold"),
            command=self._calculate_sync
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="📋 レポート", width=80, fg_color="#616161",
            font=("Meiryo", 11),
            command=self._add_to_report
        ).pack(side="left", padx=5)
        
        # メインコンテンツ (上下分割)
        main_paned = ctk.CTkFrame(self, fg_color="#2B2B2B")
        main_paned.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 上部: 画像比較エリア (左右分割)
        image_area = ctk.CTkFrame(main_paned, fg_color="transparent")
        image_area.pack(fill="both", expand=True, pady=(0, 5))
        image_area.grid_columnconfigure(0, weight=1)
        image_area.grid_columnconfigure(1, weight=1)
        image_area.grid_rowconfigure(0, weight=1)
        
        # 左: Web Source
        web_frame = ctk.CTkFrame(image_area, fg_color="#2D2D2D", corner_radius=10)
        web_frame.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        
        web_header = ctk.CTkFrame(web_frame, fg_color="#1E88E5", height=35, corner_radius=10)
        web_header.pack(fill="x", padx=3, pady=3)
        web_header.pack_propagate(False)
        
        ctk.CTkLabel(
            web_header, text="🌐 Web Source", font=("Meiryo", 12, "bold")
        ).pack(side="left", padx=15, pady=5)
        
        self.web_info_label = ctk.CTkLabel(
            web_header, text="", font=("Meiryo", 10), text_color="#B3D4FC"
        )
        self.web_info_label.pack(side="right", padx=15)
        
        # Web Canvas with scroll
        web_canvas_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        web_canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.web_canvas = tk.Canvas(web_canvas_frame, bg="#1E1E1E", highlightthickness=0)
        web_scrollbar_y = ttk.Scrollbar(web_canvas_frame, orient="vertical", command=self.web_canvas.yview)
        web_scrollbar_x = ttk.Scrollbar(web_canvas_frame, orient="horizontal", command=self.web_canvas.xview)
        
        self.web_canvas.configure(yscrollcommand=web_scrollbar_y.set, xscrollcommand=web_scrollbar_x.set)
        
        web_scrollbar_y.pack(side="right", fill="y")
        web_scrollbar_x.pack(side="bottom", fill="x")
        self.web_canvas.pack(side="left", fill="both", expand=True)
        
        self.web_canvas.bind("<Button-1>", lambda e: self._on_canvas_click(e, "web"))
        self.web_canvas.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.web_canvas))
        
        # 右: PDF Source
        pdf_frame = ctk.CTkFrame(image_area, fg_color="#2D2D2D", corner_radius=10)
        pdf_frame.grid(row=0, column=1, padx=(5, 0), sticky="nsew")
        
        pdf_header = ctk.CTkFrame(pdf_frame, fg_color="#E53935", height=35, corner_radius=10)
        pdf_header.pack(fill="x", padx=3, pady=3)
        pdf_header.pack_propagate(False)
        
        ctk.CTkLabel(
            pdf_header, text="📄 PDF Source", font=("Meiryo", 12, "bold")
        ).pack(side="left", padx=15, pady=5)
        
        self.pdf_info_label = ctk.CTkLabel(
            pdf_header, text="", font=("Meiryo", 10), text_color="#FFCDD2"
        )
        self.pdf_info_label.pack(side="right", padx=15)
        
        # PDF Canvas with scroll
        pdf_canvas_frame = ctk.CTkFrame(pdf_frame, fg_color="transparent")
        pdf_canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.pdf_canvas = tk.Canvas(pdf_canvas_frame, bg="#1E1E1E", highlightthickness=0)
        pdf_scrollbar_y = ttk.Scrollbar(pdf_canvas_frame, orient="vertical", command=self.pdf_canvas.yview)
        pdf_scrollbar_x = ttk.Scrollbar(pdf_canvas_frame, orient="horizontal", command=self.pdf_canvas.xview)
        
        self.pdf_canvas.configure(yscrollcommand=pdf_scrollbar_y.set, xscrollcommand=pdf_scrollbar_x.set)
        
        pdf_scrollbar_y.pack(side="right", fill="y")
        pdf_scrollbar_x.pack(side="bottom", fill="x")
        self.pdf_canvas.pack(side="left", fill="both", expand=True)
        
        self.pdf_canvas.bind("<Button-1>", lambda e: self._on_canvas_click(e, "pdf"))
        self.pdf_canvas.bind("<MouseWheel>", lambda e: self._on_mousewheel(e, self.pdf_canvas))
        
        # 下部: テキスト比較パネル
        text_panel = ctk.CTkFrame(main_paned, fg_color="#383838", corner_radius=10, height=250)
        text_panel.pack(fill="x", pady=(5, 0))
        text_panel.pack_propagate(False)
        
        text_header = ctk.CTkFrame(text_panel, fg_color="#424242", height=35, corner_radius=10)
        text_header.pack(fill="x", padx=5, pady=5)
        text_header.pack_propagate(False)
        
        ctk.CTkLabel(
            text_header, text="📝 テキスト比較 (Diff)", font=("Meiryo", 11, "bold")
        ).pack(side="left", padx=15, pady=5)
        
        self.diff_status_label = ctk.CTkLabel(
            text_header, text="パラグラフを選択してください", 
            font=("Meiryo", 10), text_color="gray"
        )
        self.diff_status_label.pack(side="right", padx=15)
        
        # テキスト比較エリア (3カラム)
        text_content = ctk.CTkFrame(text_panel, fg_color="transparent")
        text_content.pack(fill="both", expand=True, padx=10, pady=5)
        text_content.grid_columnconfigure(0, weight=1)
        text_content.grid_columnconfigure(1, weight=0)
        text_content.grid_columnconfigure(2, weight=1)
        text_content.grid_rowconfigure(0, weight=1)
        
        # Web テキスト
        web_text_frame = ctk.CTkFrame(text_content, fg_color="#1E3A5F", corner_radius=8)
        web_text_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        ctk.CTkLabel(
            web_text_frame, text="Web", font=("Meiryo", 10, "bold"), text_color="#64B5F6"
        ).pack(anchor="w", padx=10, pady=3)
        
        self.web_text = tk.Text(
            web_text_frame, wrap="word", bg="#1A2F47", fg="white",
            font=("Meiryo", 11), insertbackground="white", relief="flat"
        )
        self.web_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # 差分矢印
        arrow_frame = ctk.CTkFrame(text_content, fg_color="transparent", width=50)
        arrow_frame.grid(row=0, column=1, sticky="ns")
        
        self.similarity_display = ctk.CTkLabel(
            arrow_frame, text="⟷\n---%", font=("Meiryo", 14, "bold"), text_color="gray"
        )
        self.similarity_display.pack(expand=True)
        
        # PDF テキスト
        pdf_text_frame = ctk.CTkFrame(text_content, fg_color="#5D1A1A", corner_radius=8)
        pdf_text_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        
        ctk.CTkLabel(
            pdf_text_frame, text="PDF", font=("Meiryo", 10, "bold"), text_color="#EF9A9A"
        ).pack(anchor="w", padx=10, pady=3)
        
        self.pdf_text = tk.Text(
            pdf_text_frame, wrap="word", bg="#3D1A1A", fg="white",
            font=("Meiryo", 11), insertbackground="white", relief="flat"
        )
        self.pdf_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # Diffタグ設定
        self.web_text.tag_configure("match", foreground="#4CAF50")
        self.web_text.tag_configure("diff", foreground="#FF5722", background="#3D1A1A")
        self.pdf_text.tag_configure("match", foreground="#4CAF50")
        self.pdf_text.tag_configure("diff", foreground="#FF5722", background="#1A2F47")
        
        # ステータスバー
        status_bar = ctk.CTkFrame(self, height=30, fg_color="#1A1A1A")
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_bar, text="🟢 準備完了", font=("Meiryo", 10), text_color="gray"
        )
        self.status_label.pack(side="left", padx=15, pady=5)
    
    # ===== データロード =====
    
    def load_web_data(self, data: Dict):
        """Webデータをロード"""
        print(f"[DetailInspector] load_web_data called, data keys: {data.keys() if data else 'None'}")
        
        if data and 'image' in data and data['image']:
            self.web_image = data['image']
            print(f"[DetailInspector] Web image loaded: {self.web_image.size if self.web_image else 'None'}")
        elif data and 'image_base64' in data:
            img_data = base64.b64decode(data['image_base64'])
            self.web_image = Image.open(io.BytesIO(img_data))
        
        if data and 'regions' in data:
            self.web_regions = data['regions']
        
        if self.web_image:
            self._display_image(self.web_canvas, self.web_image, "web")
            self._draw_regions(self.web_canvas, self.web_regions, "web")
            self.web_info_label.configure(text=f"{self.web_image.width}x{self.web_image.height}")
        else:
            print("[DetailInspector] WARNING: No web image to display!")
    
    def load_pdf_data(self, data: Dict):
        """PDFデータをロード"""
        print(f"[DetailInspector] load_pdf_data called, data keys: {data.keys() if data else 'None'}")
        
        if data and 'image' in data and data['image']:
            self.pdf_image = data['image']
            print(f"[DetailInspector] PDF image loaded: {self.pdf_image.size if self.pdf_image else 'None'}")
        elif data and 'image_base64' in data:
            img_data = base64.b64decode(data['image_base64'])
            self.pdf_image = Image.open(io.BytesIO(img_data))
        
        if data and 'regions' in data:
            self.pdf_regions = data['regions']
        
        if self.pdf_image:
            self._display_image(self.pdf_canvas, self.pdf_image, "pdf")
            self._draw_regions(self.pdf_canvas, self.pdf_regions, "pdf")
            self.pdf_info_label.configure(text=f"{self.pdf_image.width}x{self.pdf_image.height}")
        else:
            print("[DetailInspector] WARNING: No PDF image to display!")
    
    def _display_image(self, canvas: tk.Canvas, image: Image.Image, source: str):
        """画像をキャンバスに表示"""
        if not image:
            print(f"[DetailInspector] _display_image: No image for {source}")
            return
        
        if image.width == 0 or image.height == 0:
            print(f"[DetailInspector] _display_image: Image has zero size for {source}")
            return
        
        canvas.delete("all")
        
        # キャンバスサイズに合わせてリサイズ
        canvas.update_idletasks()
        canvas_width = max(canvas.winfo_width(), 100)  # 最小100px
        
        ratio = canvas_width / image.width
        new_height = max(int(image.height * ratio), 1)  # 最小1px
        
        resized = image.resize((canvas_width, new_height), Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(resized)
        
        if source == "web":
            self._web_photo = photo
            canvas.scale_ratio = ratio
        else:
            self._pdf_photo = photo
            canvas.scale_ratio = ratio
        
        canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
        canvas.configure(scrollregion=(0, 0, canvas_width, new_height))
    
    def _draw_regions(self, canvas: tk.Canvas, regions: List[ParagraphRegion], source: str):
        """パラグラフ矩形を描画"""
        canvas.delete("region")
        
        scale = getattr(canvas, 'scale_ratio', 1.0)
        
        for region in regions:
            x1 = int(region.rect[0] * scale)
            y1 = int(region.rect[1] * scale)
            x2 = int(region.rect[2] * scale)
            y2 = int(region.rect[3] * scale)
            
            # シンク色決定
            if region.sync_id is not None:
                color = self.SYNC_COLORS[region.sync_id % len(self.SYNC_COLORS)]
            else:
                color = "#F44336"  # 未マッチ = 赤
            
            # 選択状態
            selected = (source == "web" and region == self.selected_web_region) or \
                       (source == "pdf" and region == self.selected_pdf_region)
            width = 3 if selected else 2
            
            # 矩形描画
            canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=color, width=width,
                tags=("region", f"region_{region.id}")
            )
            
            # ID表示
            canvas.create_text(
                x1 + 5, y1 + 5,
                text=f"#{region.id}",
                fill=color, anchor="nw",
                font=("Consolas", 9, "bold"),
                tags="region"
            )
    
    # ===== イベント =====
    
    def _on_canvas_click(self, event, source: str):
        """キャンバスクリック"""
        canvas = self.web_canvas if source == "web" else self.pdf_canvas
        regions = self.web_regions if source == "web" else self.pdf_regions
        
        scale = getattr(canvas, 'scale_ratio', 1.0)
        x = canvas.canvasx(event.x) / scale
        y = canvas.canvasy(event.y) / scale
        
        # 領域検索
        for region in regions:
            if region.rect[0] <= x <= region.rect[2] and region.rect[1] <= y <= region.rect[3]:
                self._select_region(region, source)
                return
        
        # 選択解除
        self._deselect_all()
    
    def _on_mousewheel(self, event, canvas):
        """マウスホイールスクロール"""
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _select_region(self, region: ParagraphRegion, source: str):
        """領域選択"""
        if source == "web":
            self.selected_web_region = region
            # 対応するPDF領域を自動選択
            if region.sync_id is not None:
                for pr in self.pdf_regions:
                    if pr.sync_id == region.sync_id:
                        self.selected_pdf_region = pr
                        break
        else:
            self.selected_pdf_region = region
            # 対応するWeb領域を自動選択
            if region.sync_id is not None:
                for wr in self.web_regions:
                    if wr.sync_id == region.sync_id:
                        self.selected_web_region = wr
                        break
        
        self._draw_regions(self.web_canvas, self.web_regions, "web")
        self._draw_regions(self.pdf_canvas, self.pdf_regions, "pdf")
        self._show_text_comparison()
    
    def _deselect_all(self):
        """選択解除"""
        self.selected_web_region = None
        self.selected_pdf_region = None
        self._draw_regions(self.web_canvas, self.web_regions, "web")
        self._draw_regions(self.pdf_canvas, self.pdf_regions, "pdf")
        
        self.web_text.delete("1.0", "end")
        self.pdf_text.delete("1.0", "end")
        self.diff_status_label.configure(text="パラグラフを選択してください")
        self.similarity_display.configure(text="⟷\n---%", text_color="gray")
    
    def _show_text_comparison(self):
        """テキスト比較表示"""
        web_str = self.selected_web_region.text if self.selected_web_region else ""
        pdf_str = self.selected_pdf_region.text if self.selected_pdf_region else ""
        
        self.web_text.delete("1.0", "end")
        self.pdf_text.delete("1.0", "end")
        
        if not web_str and not pdf_str:
            return
        
        # Diff計算
        matcher = difflib.SequenceMatcher(None, web_str, pdf_str)
        similarity = matcher.ratio() * 100
        
        # 類似度表示
        if similarity >= 95:
            color = "#4CAF50"
        elif similarity >= 70:
            color = "#FF9800"
        else:
            color = "#F44336"
        
        self.similarity_display.configure(text=f"⟷\n{similarity:.0f}%", text_color=color)
        self.diff_status_label.configure(
            text=f"#{self.selected_web_region.id if self.selected_web_region else '?'} ↔ "
                 f"#{self.selected_pdf_region.id if self.selected_pdf_region else '?'}"
        )
        
        # Diff表示
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                self.web_text.insert("end", web_str[i1:i2], "match")
                self.pdf_text.insert("end", pdf_str[j1:j2], "match")
            elif tag == 'replace':
                self.web_text.insert("end", web_str[i1:i2], "diff")
                self.pdf_text.insert("end", pdf_str[j1:j2], "diff")
            elif tag == 'delete':
                self.web_text.insert("end", web_str[i1:i2], "diff")
            elif tag == 'insert':
                self.pdf_text.insert("end", pdf_str[j1:j2], "diff")
    
    # ===== OCR・Sync =====
    
    def _run_ocr(self):
        """OCR実行"""
        self.status_label.configure(text="🔄 OCR実行中...")
        self.update()
        
        try:
            from app.core.engine_cloud import CloudOCREngine
            engine = CloudOCREngine()
            
            # Web OCR
            if self.web_image:
                clusters, raw_words = engine.extract_text(self.web_image)
                self.web_regions = [
                    ParagraphRegion(
                        id=c['id'],
                        rect=tuple(c['rect']),
                        text=c['text']
                    ) for c in clusters
                ]
                self._draw_regions(self.web_canvas, self.web_regions, "web")
                
            # PDF OCR
            if self.pdf_image:
                clusters, raw_words = engine.extract_text(self.pdf_image)
                self.pdf_regions = [
                    ParagraphRegion(
                        id=c['id'],
                        rect=tuple(c['rect']),
                        text=c['text']
                    ) for c in clusters
                ]
                self._draw_regions(self.pdf_canvas, self.pdf_regions, "pdf")
            
            self.status_label.configure(
                text=f"✅ OCR完了: Web {len(self.web_regions)}領域, PDF {len(self.pdf_regions)}領域"
            )
            
        except Exception as e:
            self.status_label.configure(text=f"❌ OCRエラー: {e}")
    
    def _calculate_sync(self):
        """Sync計算"""
        if not self.web_regions or not self.pdf_regions:
            self.status_label.configure(text="⚠️ OCRを先に実行してください")
            return
        
        self.status_label.configure(text="🔄 Sync計算中...")
        self.update()
        
        try:
            from app.core.sync_matcher import SyncMatcher
            matcher = SyncMatcher()
            
            # マッチング実行
            web_texts = [r.text for r in self.web_regions]
            pdf_texts = [r.text for r in self.pdf_regions]
            
            matches = matcher.match_paragraphs(web_texts, pdf_texts)
            
            # Sync ID付与
            for i, (web_idx, pdf_idx, sim) in enumerate(matches):
                if web_idx < len(self.web_regions):
                    self.web_regions[web_idx].sync_id = i
                    self.web_regions[web_idx].similarity = sim
                if pdf_idx < len(self.pdf_regions):
                    self.pdf_regions[pdf_idx].sync_id = i
                    self.pdf_regions[pdf_idx].similarity = sim
            
            # 再描画
            self._draw_regions(self.web_canvas, self.web_regions, "web")
            self._draw_regions(self.pdf_canvas, self.pdf_regions, "pdf")
            
            # 全体Sync Rate計算
            total_sim = sum(m[2] for m in matches) / len(matches) if matches else 0
            color = "#4CAF50" if total_sim >= 0.95 else "#FF9800" if total_sim >= 0.7 else "#F44336"
            self.sync_rate_label.configure(text=f"Sync Rate: {total_sim*100:.1f}%", text_color=color)
            
            self.status_label.configure(text=f"✅ Sync完了: {len(matches)}ペア")
            
        except Exception as e:
            self.status_label.configure(text=f"❌ Syncエラー: {e}")
    
    def _add_to_report(self):
        """レポートに追加"""
        # TODO: ReportEditorと連携
        self.status_label.configure(text="📋 レポートに追加しました")


class DetailInspectorFrame(ctk.CTkFrame):
    """埋め込みフレーム版"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.parent_app = parent.winfo_toplevel()
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🔬 詳細インスペクター",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        ctk.CTkButton(
            header,
            text="↗️ 別ウィンドウで開く",
            command=self._open_window,
            fg_color="#616161"
        ).pack(side="right", padx=15)
        
        # クイック表示
        content = ctk.CTkFrame(self, fg_color="#2D2D2D")
        content.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            content,
            text="Web/PDFを並列表示してパラグラフ単位で校正\n\n"
                 "• OCR実行で自動領域抽出\n"
                 "• Sync計算でパラグラフマッチング\n"
                 "• 差分表示で校正漏れ防止\n\n"
                 "「別ウィンドウで開く」をクリック",
            font=("Meiryo", 12),
            text_color="gray",
            justify="center"
        ).place(relx=0.5, rely=0.5, anchor="center")
    
    def _open_window(self):
        """別ウィンドウで開く"""
        web_data = {}
        pdf_data = {}
        
        # 親アプリを探す
        parent = self.parent_app
        print(f"[DetailInspectorFrame] Searching for images in parent: {type(parent)}")
        
        # AdvancedComparisonView からページ情報を取得
        current_page = 1
        page_regions = []
        advanced_view = None
        
        if hasattr(parent, 'comparison_view') and parent.comparison_view is not None:
            advanced_view = parent.comparison_view
            current_page = getattr(advanced_view, 'current_page', 1)
            page_regions = getattr(advanced_view, 'page_regions', [])
            print(f"[DetailInspectorFrame] ✅ Got page context: page={current_page}, regions={len(page_regions)}")
        else:
            print(f"[DetailInspectorFrame] ❌ comparison_view not found or None, using page 1")
        
        # デバッグ: comparison_queue の内容を確認
        if hasattr(parent, 'comparison_queue'):
            print(f"[DetailInspectorFrame] comparison_queue has {len(parent.comparison_queue)} items")
            for i, item in enumerate(parent.comparison_queue[:5]):  # 最初の5件
                print(f"  [{i}] type={item.get('type')}, has_screenshot={bool(item.get('screenshot_base64'))}")
        else:
            print("[DetailInspectorFrame] parent has NO comparison_queue!")
        
        # ★ comparison_view.web_image から画像を取得（全ページ連結済み画像）
        if advanced_view is not None and hasattr(advanced_view, 'web_image') and advanced_view.web_image:
            img = advanced_view.web_image.copy()
            print(f"[DetailInspectorFrame] Using comparison_view.web_image: {img.size}")
            
            # 現在のページを切り抜き
            if page_regions and 0 < current_page <= len(page_regions):
                y_start, y_end = page_regions[current_page - 1]
                img = img.crop((0, y_start, img.width, y_end))
                print(f"[DetailInspectorFrame] Cropped web page {current_page}: y={y_start}-{y_end}")
            
            web_data = {'image': img}
            print(f"[DetailInspectorFrame] Final web image: {img.size}")
        # フォールバック: comparison_queue から（古い方法）
        elif hasattr(parent, 'comparison_queue') and parent.comparison_queue:
            for item in parent.comparison_queue:
                if item.get('type') == 'web' and not web_data:
                    b64 = item.get('screenshot_base64')
                    if b64:
                        try:
                            img_data = base64.b64decode(b64)
                            img = Image.open(io.BytesIO(img_data))
                            web_data = {'image': img}
                            print(f"[DetailInspectorFrame] Fallback - Found web from queue: {img.size}")
                        except Exception as e:
                            print(f"[DetailInspectorFrame] Failed to decode web image: {e}")
                elif item.get('type') == 'pdf' and not pdf_data:
                    img = item.get('image')
                    if img:
                        pdf_data = {'image': img}
                        print(f"[DetailInspectorFrame] Found pdf from queue: {img.size}")
        
        # selected_pdf_pages からも探す（全ページ連結）
        if not pdf_data and hasattr(parent, 'selected_pdf_pages') and parent.selected_pdf_pages:
            pages = parent.selected_pdf_pages
            print(f"[DetailInspectorFrame] selected_pdf_pages has {len(pages)} pages")
            
            if len(pages) == 1:
                pdf_data = {'image': pages[0]}
            elif len(pages) > 1:
                # 全ページを縦連結
                total_height = sum(p.height for p in pages)
                max_width = max(p.width for p in pages)
                
                combined = Image.new('RGB', (max_width, total_height), (255, 255, 255))
                y_offset = 0
                for page_img in pages:
                    combined.paste(page_img, (0, y_offset))
                    y_offset += page_img.height
                
                pdf_data = {'image': combined}
                print(f"[DetailInspectorFrame] Combined {len(pages)} PDF pages: {combined.size}")
        
        # AdvancedComparisonView の子ウィジェットを探す
        for child in parent.winfo_children():
            if hasattr(child, 'web_image') and child.web_image and not web_data:
                web_data = {'image': child.web_image}
                print(f"[DetailInspectorFrame] Found web_image in child: {child.web_image.size}")
            if hasattr(child, 'pdf_image') and child.pdf_image and not pdf_data:
                pdf_data = {'image': child.pdf_image}
                print(f"[DetailInspectorFrame] Found pdf_image in child: {child.pdf_image.size}")
        
        print(f"[DetailInspectorFrame] Final web_data: {web_data.keys() if web_data else 'empty'}")
        print(f"[DetailInspectorFrame] Final pdf_data: {pdf_data.keys() if pdf_data else 'empty'}")
        
        window = DetailInspectorWindow(
            self.winfo_toplevel(),
            web_data=web_data,
            pdf_data=pdf_data
        )
        window.focus()


