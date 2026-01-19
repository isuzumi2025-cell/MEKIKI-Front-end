"""
Advanced Comparison View - 高度な校正ワークスペース
AI-based page detection + Dynamic Clustering OCR + Editable Regions

Features:
- Overview Map (ページサムネイル)
- Dual-pane Page Detail View (Web/PDF並列表示)
- Editable regions with P-Seq-Sync codes
- Real-time text synchronization
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Tuple, Callable
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import base64
import difflib
from dataclasses import dataclass


@dataclass 
class EditableRegion:
    """編集可能なエリア"""
    id: int
    rect: List[int]  # [x1, y1, x2, y2]
    text: str
    area_code: str  # "P1-2 S3"
    sync_number: Optional[int]
    similarity: float
    source: str  # "web" or "pdf"
    
    # キャンバス上でのID
    canvas_rect_id: Optional[int] = None
    canvas_text_id: Optional[int] = None


class AdvancedComparisonView(ctk.CTkFrame):
    """
    高度な校正ワークスペース
    埋め込みフレーム版 (比較マトリクスを置き換え)
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.parent_app = parent.winfo_toplevel()
        
        # データ
        self.web_image: Optional[Image.Image] = None
        self.pdf_image: Optional[Image.Image] = None
        self.web_clusters: List[Dict] = []
        self.pdf_clusters: List[Dict] = []
        self.web_regions: List[EditableRegion] = []
        self.pdf_regions: List[EditableRegion] = []
        self.page_regions: List[Tuple[int, int]] = []  # [(y_start, y_end), ...]
        self.current_page: int = 1
        
        # 選択状態
        self.selected_region: Optional[EditableRegion] = None
        self.drag_handle: Optional[str] = None  # "nw", "ne", "sw", "se", "move"
        self.drag_start: Optional[Tuple[int, int]] = None
        
        # 編集モード
        self.edit_mode: bool = False
        self.selection_box = None  # 選択範囲ボックス (x1, y1, x2, y2)
        self.selection_canvas = None  # どのキャンバスで選択中か
        
        # UI構築
        self._build_ui()
        
        # 初期データロード
        self.after(500, self._load_from_queue)
        
        # リサイズイベント
        self.bind("<Configure>", self._on_resize)
        self._last_resize_time = 0
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="⚖️ Advanced Proofing Workspace",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        # Sync Rate表示 (大きめに)
        self.sync_rate_display = ctk.CTkLabel(
            header,
            text="Sync: ---%",
            font=("Meiryo", 14, "bold"),
            text_color="#888888"
        )
        self.sync_rate_display.pack(side="left", padx=20)
        
        # ツールバー
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=10)
        
        ctk.CTkButton(
            toolbar, text="🔄 OCR実行", width=100, fg_color="#FF6F00",
            command=self._run_ocr_analysis
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="🔗 Sync再計算", width=100, fg_color="#2196F3",
            command=self._recalculate_sync
        ).pack(side="left", padx=5)
        
        # 高度クラスターマッチングボタン
        ctk.CTkButton(
            toolbar, text="🧠 高度マッチ", width=100, fg_color="#9C27B0",
            command=self._run_advanced_cluster_matching
        ).pack(side="left", padx=5)
        
        # Excel出力ボタン
        self.export_btn = ctk.CTkButton(
            toolbar, text="📊 Excel出力", width=100, fg_color="#4CAF50",
            command=self._export_to_excel, state="disabled"
        )
        self.export_btn.pack(side="left", padx=5)
        
        # 編集モードボタン
        self.edit_mode_btn = ctk.CTkButton(
            toolbar, text="✏️ 編集", width=80, fg_color="#616161",
            command=self._toggle_edit_mode
        )
        self.edit_mode_btn.pack(side="left", padx=5)
        
        # 📊 比較シートボタン（画面2）
        ctk.CTkButton(
            toolbar, text="📊 比較シート", width=100, fg_color="#9C27B0",
            command=self._open_comparison_spreadsheet
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="↗️ 全画面", width=80, fg_color="#616161",
            command=self._open_fullscreen
        ).pack(side="left", padx=5)
        
        # === メインコンテンツ (上下分割) ===
        main_paned = tk.PanedWindow(self, orient="vertical", sashwidth=5, bg="#444444")
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 上部: 3カラム (Overview + Canvas + Text)
        top_frame = ctk.CTkFrame(main_paned, fg_color="#2B2B2B")
        main_paned.add(top_frame, height=400)
        
        # 左パネル: Overview + Area List
        left_panel = ctk.CTkFrame(top_frame, fg_color="#2D2D2D", width=220)
        left_panel.pack(side="left", fill="y", padx=2, pady=2)
        left_panel.pack_propagate(False)
        
        self._build_left_panel(left_panel)
        
        # 中央パネル: Dual Page Detail
        center_panel = ctk.CTkFrame(top_frame, fg_color="#2D2D2D")
        center_panel.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        self._build_center_panel(center_panel)
        
        # 右パネル: Sync Text Panel (コンパクト版)
        right_panel = ctk.CTkFrame(top_frame, fg_color="#2D2D2D", width=280)
        right_panel.pack(side="right", fill="y", padx=2, pady=2)
        right_panel.pack_propagate(False)
        
        self._build_right_panel(right_panel)
        
        # 下部: スプレッドシートビュー
        bottom_frame = ctk.CTkFrame(main_paned, fg_color="#1E1E1E")
        main_paned.add(bottom_frame, height=200)
        
        self._build_spreadsheet_panel(bottom_frame)
        
        # ステータスバー
        status_bar = ctk.CTkFrame(self, height=25, fg_color="#1A1A1A")
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_bar,
            text="データを読み込み中...",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=10)
        
        self.sync_rate_label = ctk.CTkLabel(
            status_bar,
            text="Sync Rate: ---%",
            font=("Meiryo", 10, "bold"),
            text_color="gray"
        )
        self.sync_rate_label.pack(side="right", padx=10)
    
    def _build_left_panel(self, parent):
        """左パネル: Overview Map + Area List"""
        # Overview Map
        overview_frame = ctk.CTkFrame(parent, fg_color="#383838", corner_radius=8)
        overview_frame.pack(fill="x", padx=5, pady=5)
        
        # ヘッダー行
        overview_header = ctk.CTkFrame(overview_frame, fg_color="transparent")
        overview_header.pack(fill="x", padx=5, pady=3)
        
        ctk.CTkLabel(
            overview_header,
            text="📄 Overview Map",
            font=("Meiryo", 11, "bold")
        ).pack(side="left", padx=5)
        
        # 主体切替ボタン
        self.primary_source = "web"
        self.primary_toggle_btn = ctk.CTkButton(
            overview_header,
            text="主体: Web→PDF",
            width=100,
            height=22,
            font=("Meiryo", 9),
            fg_color="#616161",
            hover_color="#757575",
            command=self._toggle_primary_source
        )
        self.primary_toggle_btn.pack(side="right", padx=5)
        
        # ページサムネイル用スクロールフレーム (両方向スクロール対応)
        overview_scroll_container = ctk.CTkFrame(overview_frame, fg_color="transparent")
        overview_scroll_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.overview_canvas = tk.Canvas(overview_scroll_container, bg="#2D2D2D", highlightthickness=0, height=150)
        overview_scrollbar_y = ttk.Scrollbar(overview_scroll_container, orient="vertical", command=self.overview_canvas.yview)
        overview_scrollbar_x = ttk.Scrollbar(overview_scroll_container, orient="horizontal", command=self.overview_canvas.xview)
        
        self.overview_scroll = ctk.CTkFrame(self.overview_canvas, fg_color="transparent")
        self.overview_scroll.bind("<Configure>", lambda e: self.overview_canvas.configure(scrollregion=self.overview_canvas.bbox("all")))
        
        self.overview_canvas.create_window((0, 0), window=self.overview_scroll, anchor="nw")
        self.overview_canvas.configure(yscrollcommand=overview_scrollbar_y.set, xscrollcommand=overview_scrollbar_x.set)
        
        overview_scrollbar_y.pack(side="right", fill="y")
        overview_scrollbar_x.pack(side="bottom", fill="x")
        self.overview_canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールスクロール
        self.overview_canvas.bind("<MouseWheel>", lambda e: self.overview_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # プレースホルダー
        self.overview_placeholder = ctk.CTkLabel(
            self.overview_scroll,
            text="ページを検出中...",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.overview_placeholder.pack(pady=20)
        
        # Area List
        area_frame = ctk.CTkFrame(parent, fg_color="#383838", corner_radius=8)
        area_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            area_frame,
            text="📋 Area List",
            font=("Meiryo", 11, "bold")
        ).pack(anchor="w", padx=10, pady=5)
        
        # エリアリスト用スクロールフレーム
        self.area_list = ctk.CTkScrollableFrame(
            area_frame,
            fg_color="transparent"
        )
        self.area_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        # プレースホルダー
        self.area_placeholder = ctk.CTkLabel(
            self.area_list,
            text="OCRを実行すると\nエリアが表示されます",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.area_placeholder.pack(pady=30)
    
    def _build_center_panel(self, parent):
        """中央パネル: Dual Page Detail View"""
        # ページナビゲーション
        nav_frame = ctk.CTkFrame(parent, fg_color="#383838", height=40)
        nav_frame.pack(fill="x", padx=5, pady=5)
        nav_frame.pack_propagate(False)
        
        ctk.CTkButton(
            nav_frame, text="◀", width=30, fg_color="#616161",
            command=self._prev_page
        ).pack(side="left", padx=5, pady=5)
        
        self.page_label = ctk.CTkLabel(
            nav_frame,
            text="Page 1 / 1",
            font=("Meiryo", 11, "bold")
        )
        self.page_label.pack(side="left", padx=10)
        
        ctk.CTkButton(
            nav_frame, text="▶", width=30, fg_color="#616161",
            command=self._next_page
        ).pack(side="left", padx=5, pady=5)
        
        # Dual View (Web | PDF)
        dual_frame = ctk.CTkFrame(parent, fg_color="transparent")
        dual_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        dual_frame.grid_columnconfigure((0, 1), weight=1, uniform="col")
        dual_frame.grid_rowconfigure(0, weight=1)
        
        # Web側
        web_frame = ctk.CTkFrame(dual_frame, fg_color="#2D2D2D", corner_radius=8)
        web_frame.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        
        web_header = ctk.CTkFrame(web_frame, fg_color="#383838", height=30)
        web_header.pack(fill="x")
        web_header.pack_propagate(False)
        
        ctk.CTkLabel(
            web_header,
            text="🌐 Web Source",
            font=("Meiryo", 10, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        # Web分離ボタン
        ctk.CTkButton(
            web_header, text="↗️", width=25, height=22, fg_color="#505050",
            command=lambda: self._detach_panel("web")
        ).pack(side="right", padx=2, pady=4)
        
        # Web領域エディタボタン
        ctk.CTkButton(
            web_header, text="🖊️編集", width=50, height=22, fg_color="#4CAF50",
            command=lambda: self._open_region_editor("web")
        ).pack(side="right", padx=2, pady=4)
        
        # Webキャンバス with スクロールバー
        web_canvas_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        web_canvas_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.web_canvas = tk.Canvas(web_canvas_frame, bg="#1E1E1E", highlightthickness=0)
        web_scrollbar = ttk.Scrollbar(web_canvas_frame, orient="vertical", command=self.web_canvas.yview)
        self.web_canvas.configure(yscrollcommand=web_scrollbar.set)
        
        web_scrollbar.pack(side="right", fill="y")
        self.web_canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールスクロール
        self.web_canvas.bind("<MouseWheel>", lambda e: self.web_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # PDF側
        pdf_frame = ctk.CTkFrame(dual_frame, fg_color="#2D2D2D", corner_radius=8)
        pdf_frame.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        
        pdf_header = ctk.CTkFrame(pdf_frame, fg_color="#383838", height=30)
        pdf_header.pack(fill="x")
        pdf_header.pack_propagate(False)
        
        ctk.CTkLabel(
            pdf_header,
            text="📄 PDF Source",
            font=("Meiryo", 10, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        # PDF分離ボタン
        ctk.CTkButton(
            pdf_header, text="↗️", width=25, height=22, fg_color="#505050",
            command=lambda: self._detach_panel("pdf")
        ).pack(side="right", padx=2, pady=4)
        
        # PDF領域エディタボタン
        ctk.CTkButton(
            pdf_header, text="🖊️編集", width=50, height=22, fg_color="#4CAF50",
            command=lambda: self._open_region_editor("pdf")
        ).pack(side="right", padx=2, pady=4)
        
        # PDFページナビゲーション
        pdf_nav_frame = ctk.CTkFrame(pdf_header, fg_color="transparent")
        pdf_nav_frame.pack(side="right", padx=5)
        
        ctk.CTkButton(
            pdf_nav_frame, text="◀", width=25, height=22, fg_color="#505050",
            command=self._prev_pdf_page
        ).pack(side="left", padx=1)
        
        self.pdf_page_label = ctk.CTkLabel(
            pdf_nav_frame, text="1/1", font=("Meiryo", 9), width=40
        )
        self.pdf_page_label.pack(side="left", padx=2)
        
        ctk.CTkButton(
            pdf_nav_frame, text="▶", width=25, height=22, fg_color="#505050",
            command=self._next_pdf_page
        ).pack(side="left", padx=1)
        
        # PDFキャンバス with スクロールバー
        pdf_canvas_frame = ctk.CTkFrame(pdf_frame, fg_color="transparent")
        pdf_canvas_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.pdf_canvas = tk.Canvas(pdf_canvas_frame, bg="#1E1E1E", highlightthickness=0)
        pdf_scrollbar = ttk.Scrollbar(pdf_canvas_frame, orient="vertical", command=self.pdf_canvas.yview)
        self.pdf_canvas.configure(yscrollcommand=pdf_scrollbar.set)
        
        pdf_scrollbar.pack(side="right", fill="y")
        self.pdf_canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールスクロール
        self.pdf_canvas.bind("<MouseWheel>", lambda e: self.pdf_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # キャンバスイベント
        for canvas in [self.web_canvas, self.pdf_canvas]:
            canvas.bind("<ButtonPress-1>", self._on_canvas_click)
            canvas.bind("<B1-Motion>", self._on_canvas_drag)
            canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
    
    def _build_right_panel(self, parent):
        """右パネル: Sync Text Panel"""
        # 選択中エリア情報
        info_frame = ctk.CTkFrame(parent, fg_color="#383838", corner_radius=8)
        info_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            info_frame,
            text="🔍 Selected Area",
            font=("Meiryo", 11, "bold")
        ).pack(anchor="w", padx=10, pady=5)
        
        self.selected_info = ctk.CTkLabel(
            info_frame,
            text="エリアを選択してください",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.selected_info.pack(anchor="w", padx=10, pady=5)
        
        # Sync比較
        sync_frame = ctk.CTkFrame(parent, fg_color="#383838", corner_radius=8)
        sync_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            sync_frame,
            text="📝 Text Comparison",
            font=("Meiryo", 11, "bold")
        ).pack(anchor="w", padx=10, pady=5)
        
        # Webテキスト
        ctk.CTkLabel(
            sync_frame,
            text="Web:",
            font=("Meiryo", 9),
            text_color="#4CAF50"
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        self.web_text_box = ctk.CTkTextbox(
            sync_frame,
            height=80,
            font=("Meiryo", 10),
            fg_color="#1E1E1E"
        )
        self.web_text_box.pack(fill="x", padx=10, pady=2)
        
        # PDFテキスト
        ctk.CTkLabel(
            sync_frame,
            text="PDF:",
            font=("Meiryo", 9),
            text_color="#2196F3"
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        self.pdf_text_box = ctk.CTkTextbox(
            sync_frame,
            height=80,
            font=("Meiryo", 10),
            fg_color="#1E1E1E"
        )
        self.pdf_text_box.pack(fill="x", padx=10, pady=2)
        
        # Diff表示
        ctk.CTkLabel(
            sync_frame,
            text="Diff:",
            font=("Meiryo", 9),
            text_color="#FF9800"
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        self.diff_text_box = ctk.CTkTextbox(
            sync_frame,
            height=100,
            font=("Consolas", 9),
            fg_color="#1E1E1E"
        )
        self.diff_text_box.pack(fill="x", padx=10, pady=2)
        
        # 類似度表示
        self.similarity_label = ctk.CTkLabel(
            sync_frame,
            text="Similarity: ---%",
            font=("Meiryo", 12, "bold"),
            text_color="gray"
        )
        self.similarity_label.pack(pady=5)
        
        # テキスト編集ボタン
        edit_frame = ctk.CTkFrame(sync_frame, fg_color="transparent")
        edit_frame.pack(fill="x", padx=10, pady=5)
        
        self.edit_mode_var = ctk.BooleanVar(value=False)
        
        ctk.CTkButton(
            edit_frame,
            text="✏️ テキスト編集",
            command=self._toggle_edit_mode,
            width=100,
            height=28,
            font=("Meiryo", 10),
            fg_color="#4CAF50"
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            edit_frame,
            text="💾 保存して再計算",
            command=self._save_edited_text,
            width=120,
            height=28,
            font=("Meiryo", 10),
            fg_color="#FF6F00"
        ).pack(side="left", padx=2)
    
    def _build_spreadsheet_panel(self, parent):
        """下部パネル: インライン・ライブスプレッドシート（全データ+スクロール）"""
        # ヘッダー
        header = ctk.CTkFrame(parent, fg_color="#2D2D2D", height=35)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="📋 ライブ比較シート",
            font=("Meiryo", 11, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        # クイック統計
        self.quick_stats = ctk.CTkLabel(
            header, text="Web: 0件 | PDF: 0件 | マッチ: 0件",
            font=("Meiryo", 9), text_color="gray"
        )
        self.quick_stats.pack(side="left", padx=20)
        
        # ツールバー
        ctk.CTkButton(
            header, text="📊 全画面", width=80, height=25, fg_color="#9C27B0",
            command=self._open_comparison_spreadsheet
        ).pack(side="right", padx=5, pady=5)
        
        ctk.CTkButton(
            header, text="📥 Excel", width=70, height=25, fg_color="#4CAF50",
            command=self._export_to_excel
        ).pack(side="right", padx=2, pady=5)
        
        # =========================================
        # 単一グリッドコンテナ方式 (真のスプレッドシート)
        # ヘッダーとデータ行が同じグリッドを共有
        # =========================================
        
        # 列幅定数
        self._col_widths = {"web": 350, "pdf": 350, "sync": 80}
        
        # スクロール可能なコンテンツエリア
        content_frame = ctk.CTkFrame(parent, fg_color="#1E1E1E")
        content_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.spreadsheet_canvas = tk.Canvas(content_frame, bg="#1E1E1E", highlightthickness=0)
        spreadsheet_scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=self.spreadsheet_canvas.yview)
        
        # グリッドコンテナ (ヘッダー + データ行)
        self.spreadsheet_inner = ctk.CTkFrame(self.spreadsheet_canvas, fg_color="#1E1E1E")
        self.spreadsheet_inner.bind("<Configure>", lambda e: self.spreadsheet_canvas.configure(scrollregion=self.spreadsheet_canvas.bbox("all")))
        
        # グリッド列設定 (全行で共有) - 画面幅追従
        self.spreadsheet_inner.grid_columnconfigure(0, weight=1, minsize=200)  # Web: 拡張可能、最小200px
        self.spreadsheet_inner.grid_columnconfigure(1, weight=1, minsize=200)  # PDF: 拡張可能、最小200px
        self.spreadsheet_inner.grid_columnconfigure(2, weight=0, minsize=self._col_widths["sync"])  # Sync: 固定80px
        
        # ヘッダー行 (row=0)
        web_header = ctk.CTkFrame(self.spreadsheet_inner, fg_color="#2E7D32", height=35)
        web_header.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        web_header.grid_propagate(False)
        ctk.CTkLabel(web_header, text="🌐 Web側", font=("Meiryo", 10, "bold")).pack(side="left", padx=10, pady=5)
        
        pdf_header = ctk.CTkFrame(self.spreadsheet_inner, fg_color="#1565C0", height=35)
        pdf_header.grid(row=0, column=1, sticky="nsew", padx=1, pady=1)
        pdf_header.grid_propagate(False)
        ctk.CTkLabel(pdf_header, text="📄 PDF側", font=("Meiryo", 10, "bold")).pack(side="left", padx=10, pady=5)
        
        sync_header = ctk.CTkFrame(self.spreadsheet_inner, fg_color="#FF6F00", height=35)
        sync_header.grid(row=0, column=2, sticky="nsew", padx=1, pady=1)
        sync_header.grid_propagate(False)
        ctk.CTkLabel(sync_header, text="Sync", font=("Meiryo", 10, "bold")).pack(expand=True, pady=5)
        
        # 次のデータ行は row=1 から開始
        self._spreadsheet_next_row = 1
        
        # キャンバス設定
        self._spreadsheet_window = self.spreadsheet_canvas.create_window((0, 0), window=self.spreadsheet_inner, anchor="nw")
        def _update_inner_width(event):
            self.spreadsheet_canvas.itemconfig(self._spreadsheet_window, width=event.width)
        self.spreadsheet_canvas.bind("<Configure>", _update_inner_width)
        self.spreadsheet_canvas.configure(yscrollcommand=spreadsheet_scrollbar.set)
        
        spreadsheet_scrollbar.pack(side="right", fill="y")
        spreadsheet_scrollbar_x = ttk.Scrollbar(content_frame, orient="horizontal", command=self.spreadsheet_canvas.xview)
        self.spreadsheet_canvas.configure(xscrollcommand=spreadsheet_scrollbar_x.set)
        spreadsheet_scrollbar_x.pack(side="bottom", fill="x")
        self.spreadsheet_canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールスクロール
        self.spreadsheet_canvas.bind("<MouseWheel>", lambda e: self.spreadsheet_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.spreadsheet_inner.bind("<MouseWheel>", lambda e: self.spreadsheet_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # サムネイル参照保持
        self._spreadsheet_thumbs = []
    
    def _refresh_inline_spreadsheet(self):
        """インラインスプレッドシートを更新"""
        # ヘッダー行(row=0)を保持し、データ行のみ削除
        for widget in self.spreadsheet_inner.winfo_children():
            info = widget.grid_info()
            if info and int(info.get('row', 0)) > 0:  # row > 0 はデータ行
                widget.destroy()
        self._spreadsheet_thumbs = []
        self._spreadsheet_next_row = 1  # データ行カウンタをリセット
        
        if not self.web_regions and not self.pdf_regions:
            # 空メッセージをrow=1に配置
            empty_label = ctk.CTkLabel(
                self.spreadsheet_inner, 
                text="OCRを実行すると比較データが表示されます",
                font=("Meiryo", 10), text_color="gray"
            )
            empty_label.grid(row=1, column=0, columnspan=3, pady=20)
            return
        
        # sync_pairsからマッチペアを取得
        sync_pairs = getattr(self, 'sync_pairs', [])
        web_map = {r.area_code: r for r in self.web_regions}
        pdf_map = {r.area_code: r for r in self.pdf_regions}
        used_web = set()
        used_pdf = set()
        row_no = 0
        
        # デバッグ: ID形式を確認
        if sync_pairs:
            print(f"[DEBUG] sync_pairs[0]: web_id={sync_pairs[0].web_id}, pdf_id={sync_pairs[0].pdf_id}")
        if self.pdf_regions:
            print(f"[DEBUG] pdf_regions[0].area_code={self.pdf_regions[0].area_code}")
        print(f"[DEBUG] sync_pairs count: {len(sync_pairs)}, pdf_map keys sample: {list(pdf_map.keys())[:3]}")
        
        # 1. マッチペア
        lookup_debug_done = False
        for sp in sync_pairs:
            web_r = web_map.get(sp.web_id)
            pdf_r = pdf_map.get(sp.pdf_id)
            
            # 最初の数件でルックアップ結果をデバッグ
            if not lookup_debug_done and row_no < 3:
                print(f"[DEBUG LOOKUP] sp.pdf_id='{sp.pdf_id}' → pdf_r={pdf_r is not None}")
                if pdf_r is None and row_no == 0:
                    print(f"[DEBUG] pdf_map keys (all): {list(pdf_map.keys())}")
                    lookup_debug_done = True
            
            self._create_spreadsheet_row(row_no, web_r, pdf_r, sp.similarity, f"{sp.web_id}↔{sp.pdf_id}")
            if sp.web_id: used_web.add(sp.web_id)
            if sp.pdf_id: used_pdf.add(sp.pdf_id)
            row_no += 1
        
        # 2. 未マッチWeb
        for r in self.web_regions:
            if r.area_code not in used_web:
                self._create_spreadsheet_row(row_no, r, None, 0.0, "")
                row_no += 1
        
        # 3. 未マッチPDF
        for r in self.pdf_regions:
            if r.area_code not in used_pdf:
                self._create_spreadsheet_row(row_no, None, r, 0.0, "")
                row_no += 1
        
        # 統計更新
        matched = len(sync_pairs)
        self.quick_stats.configure(
            text=f"Web: {len(self.web_regions)}件 | PDF: {len(self.pdf_regions)}件 | マッチ: {matched}件"
        )
    
    def _create_spreadsheet_row(self, row_no: int, web_region, pdf_region, similarity: float, sync_area: str):
        """グリッドベースのスプレッドシート行 - ヘッダーと同じグリッドコンテナに配置"""
        grid_row = self._spreadsheet_next_row  # ヘッダーはrow=0、データはrow=1から
        self._spreadsheet_next_row += 1
        
        bg = "#2B2B2B" if row_no % 2 == 0 else "#333333"
        
        # === Webセル (column=0) ===
        web_cell = ctk.CTkFrame(self.spreadsheet_inner, fg_color="#2A3A2A" if web_region else bg)
        web_cell.grid(row=grid_row, column=0, sticky="nsew", padx=1, pady=1)
        web_cell.bind("<Button-1>", lambda e, r=web_region: self._on_cell_click("web", r))
        
        # セル内コンテンツ
        web_id = web_region.area_code if web_region else "-"
        ctk.CTkLabel(web_cell, text=web_id, width=60, font=("Meiryo", 9), text_color="#4CAF50", anchor="w").pack(side="left", padx=3)
        
        # サムネイル
        if web_region and self.web_image:
            web_img_frame = ctk.CTkFrame(web_cell, fg_color="#1E1E1E", width=50, height=40)
            web_img_frame.pack(side="left", padx=2)
            web_img_frame.pack_propagate(False)
            try:
                x1, y1, x2, y2 = web_region.rect
                cropped = self.web_image.crop((max(0,x1), max(0,y1), min(self.web_image.width,x2), min(self.web_image.height,y2)))
                if cropped.height > 0:
                    ratio = 35 / cropped.height
                    resized = cropped.resize((min(int(cropped.width * ratio), 50), 35), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(resized)
                    self._spreadsheet_thumbs.append(photo)
                    lbl = tk.Label(web_img_frame, image=photo, bg="#1E1E1E")
                    lbl.image = photo
                    lbl.pack(expand=True)
            except: pass
        
        # テキスト
        web_text = web_region.text.replace('\n', ' ') if web_region and web_region.text else ""
        ctk.CTkLabel(web_cell, text=web_text, font=("Meiryo", 8), anchor="nw", justify="left", wraplength=200).pack(side="left", fill="both", expand=True, padx=3, pady=3)
        
        # === PDFセル (column=1) ===
        pdf_cell = ctk.CTkFrame(self.spreadsheet_inner, fg_color="#2A2A3A" if pdf_region else bg)
        pdf_cell.grid(row=grid_row, column=1, sticky="nsew", padx=1, pady=1)
        pdf_cell.bind("<Button-1>", lambda e, r=pdf_region: self._on_cell_click("pdf", r))
        
        # セル内コンテンツ
        pdf_id = pdf_region.area_code if pdf_region else "-"
        ctk.CTkLabel(pdf_cell, text=pdf_id, width=60, font=("Meiryo", 9), text_color="#2196F3", anchor="w").pack(side="left", padx=3)
        
        # サムネイル
        if pdf_region and self.pdf_image:
            pdf_img_frame = ctk.CTkFrame(pdf_cell, fg_color="#1E1E1E", width=50, height=40)
            pdf_img_frame.pack(side="left", padx=2)
            pdf_img_frame.pack_propagate(False)
            try:
                x1, y1, x2, y2 = pdf_region.rect
                img_w, img_h = self.pdf_image.size
                if x2 > x1 and y2 > y1 and x1 < img_w and y1 < img_h:
                    cropped = self.pdf_image.crop((max(0,x1), max(0,y1), min(img_w,x2), min(img_h,y2)))
                    if cropped.width > 0 and cropped.height > 0:
                        ratio = 35 / cropped.height
                        resized = cropped.resize((min(int(cropped.width * ratio), 50), 35), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(resized)
                        self._spreadsheet_thumbs.append(photo)
                        lbl = tk.Label(pdf_img_frame, image=photo, bg="#1E1E1E")
                        lbl.image = photo
                        lbl.pack(expand=True)
            except: pass
        
        # テキスト
        pdf_text = pdf_region.text.replace('\n', ' ') if pdf_region and pdf_region.text else ""
        ctk.CTkLabel(pdf_cell, text=pdf_text, font=("Meiryo", 8), anchor="nw", justify="left", wraplength=200).pack(side="left", fill="both", expand=True, padx=3, pady=3)
        
        # === Syncセル (column=2) ===
        if similarity >= 0.5:
            sim_color = "#4CAF50"
            status_icon = "🟢"
        elif similarity >= 0.3:
            sim_color = "#FF9800"
            status_icon = "🟡"
        elif sync_area:
            sim_color = "#F44336"
            status_icon = "🔴"
        else:
            sim_color = "#888888"
            status_icon = "⚪"
        
        sync_cell = ctk.CTkFrame(self.spreadsheet_inner, fg_color="transparent")
        sync_cell.grid(row=grid_row, column=2, sticky="nsew", padx=1, pady=1)
        ctk.CTkLabel(sync_cell, text=f"{status_icon} {similarity*100:.0f}%", font=("Meiryo", 9, "bold"), text_color=sim_color).pack(expand=True)
    
    def _on_cell_click(self, source_type: str, region):
        """セルクリック時にSourceウィンドウで該当エリアを表示"""
        if not region:
            return
        
        # 選択状態を更新
        self.selected_region = region
        
        # Sourceウィンドウで該当エリアを表示
        if source_type == "web":
            for r in self.web_regions:
                if r.area_code == region.area_code:
                    self._select_region(r)
                    break
        elif source_type == "pdf":
            for r in self.pdf_regions:
                if r.area_code == region.area_code:
                    self._select_region(r)
                    break
        
        # 描画を更新
        self._redraw_regions()
        
        # Text Comparison パネルを更新
        self._update_text_comparison()
    
    def _on_spreadsheet_row_click(self, web_region, pdf_region):
        """スプレッドシート行クリック時のハイライト (後方互換)"""
        if web_region:
            self._on_cell_click("web", web_region)
        elif pdf_region:
            self._on_cell_click("pdf", pdf_region)

    
    # ===== イベントハンドラ =====
    
    def _on_resize(self, event):
        """ウィンドウリサイズ時に画像を再描画"""
        import time
        current_time = time.time()
        
        # デバウンス (0.3秒間隔で再描画)
        if current_time - self._last_resize_time < 0.3:
            return
        self._last_resize_time = current_time
        
        # 画像の再描画
        def delayed_redraw():
            if hasattr(self, 'web_image') and self.web_image:
                self._display_image(self.web_canvas, self.web_image)
            if hasattr(self, 'pdf_image') and self.pdf_image:
                self._display_image(self.pdf_canvas, self.pdf_image)
            # 領域も再描画
            self._redraw_regions()
        
        self.after(100, delayed_redraw)
    
    def _on_canvas_click(self, event):
        """キャンバスクリック"""
        canvas = event.widget
        x, y = event.x, event.y
        
        # スケール情報取得
        scale_x = getattr(canvas, 'scale_x', 1.0)
        scale_y = getattr(canvas, 'scale_y', 1.0)
        offset_x = getattr(canvas, 'offset_x', 0)
        offset_y = getattr(canvas, 'offset_y', 0)
        
        # クリック位置のエリアを検索
        regions = self.web_regions if canvas == self.web_canvas else self.pdf_regions
        
        for region in regions:
            # 座標をスケーリング（描画と同じ変換）
            rx1 = region.rect[0] * scale_x + offset_x
            ry1 = region.rect[1] * scale_y + offset_y
            rx2 = region.rect[2] * scale_x + offset_x
            ry2 = region.rect[3] * scale_y + offset_y
            
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                self._select_region(region)
                self.drag_start = (x, y)
                return
        
        # 何もない場所をクリック→選択解除
        self._deselect_region()
    
    def _on_canvas_drag(self, event):
        """キャンバスドラッグ"""
        if not self.selected_region or not self.drag_start:
            return
        
        # ドラッグによるリサイズ/移動（簡易版）
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        
        # 矩形を移動
        self.selected_region.rect[0] += dx
        self.selected_region.rect[1] += dy
        self.selected_region.rect[2] += dx
        self.selected_region.rect[3] += dy
        
        self.drag_start = (event.x, event.y)
        
        # 再描画
        self._redraw_regions()
    
    def _on_canvas_release(self, event):
        """キャンバスリリース"""
        if self.selected_region:
            # リアルタイムテキスト更新
            self._update_text_for_region(self.selected_region)
        
        self.drag_start = None
    
    def _select_region(self, region: EditableRegion):
        """エリアを選択"""
        self.selected_region = region
        self._update_selected_info()
        self._highlight_selected()
    
    def _deselect_region(self):
        """選択解除"""
        self.selected_region = None
        self.selected_info.configure(text="エリアを選択してください")
        self._redraw_regions()
    
    def _highlight_selected(self):
        """選択中のエリアをハイライト"""
        self._redraw_regions()
    
    def _update_selected_info(self):
        """選択中エリア情報を更新"""
        if not self.selected_region:
            return
        
        r = self.selected_region
        info = f"{r.area_code}\nSimilarity: {r.similarity:.0%}"
        self.selected_info.configure(text=info)
        
        # テキストボックス更新
        self.web_text_box.delete("1.0", "end")
        self.pdf_text_box.delete("1.0", "end")
        
        if r.source == "web":
            self.web_text_box.insert("1.0", r.text)
            # 対応するPDF領域を探す
            for pdf_r in self.pdf_regions:
                if pdf_r.sync_number == r.sync_number:
                    self.pdf_text_box.insert("1.0", pdf_r.text)
                    break
        else:
            self.pdf_text_box.insert("1.0", r.text)
            for web_r in self.web_regions:
                if web_r.sync_number == r.sync_number:
                    self.web_text_box.insert("1.0", web_r.text)
                    break
        
        # 類似度更新
        color = "#4CAF50" if r.similarity >= 0.95 else "#FF9800" if r.similarity >= 0.7 else "#F44336"
        self.similarity_label.configure(
            text=f"Similarity: {r.similarity:.0%}",
            text_color=color
        )
    
    def _update_text_for_region(self, region: EditableRegion):
        """領域変更時のテキスト再計算"""
        # TODO: raw_wordsから領域内のテキストを再計算
        pass
    
    def _redraw_regions(self):
        """エリア矩形を再描画 (シンク番号で色分け)"""
        # シンク色パレット
        sync_colors = [
            "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#00BCD4",
            "#E91E63", "#CDDC39", "#FF5722", "#607D8B", "#795548"
        ]
        
        for canvas, regions, source in [
            (self.web_canvas, self.web_regions, "web"),
            (self.pdf_canvas, self.pdf_regions, "pdf")
        ]:
            # 古い矩形を削除
            canvas.delete("region")
            
            # スケール情報取得
            scale_x = getattr(canvas, 'scale_x', 1.0)
            scale_y = getattr(canvas, 'scale_y', 1.0)
            offset_x = getattr(canvas, 'offset_x', 0)
            offset_y = getattr(canvas, 'offset_y', 0)
            
            for region in regions:
                # 元座標をキャンバス座標に変換
                x1 = region.rect[0] * scale_x + offset_x
                y1 = region.rect[1] * scale_y + offset_y
                x2 = region.rect[2] * scale_x + offset_x
                y2 = region.rect[3] * scale_y + offset_y
                
                # 色設定 (シンク番号ベース)
                if region == self.selected_region:
                    outline = "#FFFFFF"
                    width = 3
                elif region.sync_number is not None:
                    # シンク番号で色を決定
                    outline = sync_colors[region.sync_number % len(sync_colors)]
                    width = 2
                else:
                    # 未マッチ
                    outline = "#F44336"
                    width = 2
                
                # 矩形描画
                canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline=outline, width=width,
                    tags="region"
                )
                
                # エリアコード描画
                canvas.create_text(
                    x1 + 5, y1 + 5,
                    text=region.area_code,
                    fill=outline,
                    anchor="nw",
                    font=("Consolas", 9, "bold"),
                    tags="region"
                )
    
    def _build_spreadsheet_panel(self, parent):
        """下部スプレッドシートパネル構築 (Grid Layout)"""
        # 1. ツールバー
        toolbar = ctk.CTkFrame(parent, height=30, fg_color="#333333")
        toolbar.pack(fill="x", side="top")
        
        ctk.CTkLabel(toolbar, text="📋 ライブ比較シート", font=("Meiryo", 12, "bold")).pack(side="left", padx=10)
        
        self.stats_label = ctk.CTkLabel(toolbar, text="Web: - | PDF: - | マッチ: -", font=("Meiryo", 11))
        self.stats_label.pack(side="left", padx=20)
        
        self.export_btn = ctk.CTkButton(
            toolbar, 
            text="📥 Excel出力", 
            width=80, 
            height=24, 
            state="disabled",
            command=lambda: print("Export executed") # Placeholder
        )
        self.export_btn.pack(side="right", padx=5)
        
        # 2. テーブルヘッダー (固定)
        header_frame = ctk.CTkFrame(parent, height=28, fg_color="#2B2B2B")
        header_frame.pack(fill="x", side="top", pady=(1, 0))
        header_frame.grid_columnconfigure(2, weight=1) # Web Text
        header_frame.grid_columnconfigure(4, weight=1) # PDF Text
        
        # ヘッダー項目
        ctk.CTkLabel(header_frame, text="スコア", width=60, font=("Meiryo", 11, "bold")).grid(row=0, column=0, padx=2, pady=2)
        ctk.CTkLabel(header_frame, text="ID連結", width=120, font=("Meiryo", 11, "bold")).grid(row=0, column=1, padx=2, pady=2)
        ctk.CTkLabel(header_frame, text="Web抽出テキスト", anchor="w", font=("Meiryo", 11, "bold")).grid(row=0, column=2, sticky="ew", padx=5, pady=2)
        ctk.CTkLabel(header_frame, text="⇔", width=30, font=("Meiryo", 11, "bold")).grid(row=0, column=3, padx=2, pady=2)
        ctk.CTkLabel(header_frame, text="PDF抽出テキスト", anchor="w", font=("Meiryo", 11, "bold")).grid(row=0, column=4, sticky="ew", padx=5, pady=2)
        
        # 3. スクロール領域
        self.spreadsheet_scroll = ctk.CTkScrollableFrame(parent, fg_color="#1E1E1E", corner_radius=0)
        self.spreadsheet_scroll.pack(fill="both", expand=True)
        self.spreadsheet_scroll.grid_columnconfigure(2, weight=1)
        self.spreadsheet_scroll.grid_columnconfigure(4, weight=1)
        
        self.spreadsheet_rows_frame = self.spreadsheet_scroll

    def _refresh_inline_spreadsheet(self):
        """スプレッドシートの表示を更新"""
        if not hasattr(self, 'spreadsheet_rows_frame'):
            return
            
        # クリア
        for widget in self.spreadsheet_rows_frame.winfo_children():
            widget.destroy()
            
        if not hasattr(self, 'sync_pairs') or not self.sync_pairs:
            return
            
        # テキスト参照用のマップ作成
        web_map = {r.area_code: r.text for r in self.web_regions}
        pdf_map = {r.area_code: r.text for r in self.pdf_regions}
            
        # 行を追加 (最大50件)
        for i, pair in enumerate(self.sync_pairs[:50]):
            row_color = "#2D2D2D" if i % 2 == 0 else "#252525"
            row = ctk.CTkFrame(self.spreadsheet_rows_frame, fg_color=row_color, corner_radius=0)
            row.pack(fill="x", pady=0)
            
            # 各列の重みを設定 (ヘッダーと合わせる)
            row.grid_columnconfigure(2, weight=1)
            row.grid_columnconfigure(4, weight=1)
            
            # スコア
            sim_percent = int(pair.similarity * 100)
            color = "#4CAF50" if sim_percent >= 80 else "#FF9800" if sim_percent >= 40 else "#F44336"
            ctk.CTkLabel(row, text=f"{sim_percent}%", text_color=color, width=60, font=("Arial", 11, "bold")).grid(row=0, column=0, padx=2, pady=5)
            
            # ID
            id_text = f"{pair.web_id}-{pair.pdf_id}"
            ctk.CTkLabel(row, text=id_text, width=120, text_color="#AAAAAA").grid(row=0, column=1, padx=2, pady=5)
            
            # テキスト比較
            w_txt = (web_map.get(pair.web_id, "") or "").replace("\n", " ")
            p_txt = (pdf_map.get(pair.pdf_id, "") or "").replace("\n", " ")
            
            if len(w_txt) > 40: w_txt = w_txt[:40] + "..."
            if len(p_txt) > 40: p_txt = p_txt[:40] + "..."
            
            ctk.CTkLabel(row, text=w_txt, anchor="w", text_color="#E0E0E0").grid(row=0, column=2, sticky="ew", padx=5, pady=5)
            ctk.CTkLabel(row, text="⇔", width=30, text_color="#888").grid(row=0, column=3, padx=2, pady=5)
            ctk.CTkLabel(row, text=p_txt, anchor="w", text_color="#E0E0E0").grid(row=0, column=4, sticky="ew", padx=5, pady=5)

    # ===== ページナビゲーション =====
    
    def _prev_page(self):
        """前ページ"""
        if self.current_page > 1:
            self.current_page -= 1
            self._display_current_page()
    
    def _next_page(self):
        """次ページ"""
        if self.current_page < len(self.page_regions):
            self.current_page += 1
            self._display_current_page()
    
    def _display_current_page(self):
        """現在ページを表示"""
        self.page_label.configure(
            text=f"Page {self.current_page} / {len(self.page_regions) or 1}"
        )
        # TODO: ページ画像とエリアを表示
    
    def _prev_pdf_page(self):
        """前のPDFページ"""
        if not hasattr(self, 'pdf_pages_list') or not self.pdf_pages_list:
            return
        if not hasattr(self, 'current_pdf_group_idx'):
            self.current_pdf_group_idx = 0
        
        if self.current_pdf_group_idx > 0:
            self.current_pdf_group_idx -= 1
            self._display_pdf_group()
    
    def _next_pdf_page(self):
        """次のPDFグループ"""
        if not hasattr(self, 'pdf_stitched_groups') or not self.pdf_stitched_groups:
            return
        if not hasattr(self, 'current_pdf_group_idx'):
            self.current_pdf_group_idx = 0
        
        if self.current_pdf_group_idx < len(self.pdf_stitched_groups) - 1:
            self.current_pdf_group_idx += 1
            self._display_pdf_group()
    
    def _display_pdf_group(self):
        """現在のPDFグループを表示"""
        if not hasattr(self, 'pdf_stitched_groups') or not self.pdf_stitched_groups:
            return
        
        idx = getattr(self, 'current_pdf_group_idx', 0)
        if 0 <= idx < len(self.pdf_stitched_groups):
            group = self.pdf_stitched_groups[idx]
            self.pdf_image = group['image']
            self._display_image(self.pdf_canvas, self.pdf_image)
            
            # ラベル更新
            self.pdf_page_label.configure(
                text=f"{group['page_range']}/{len(getattr(self, 'pdf_pages_list', []))}"
            )
    
    # ===== 機能 =====
    
    def _load_from_queue(self):
        """comparison_queueからデータをロード"""
        if not hasattr(self.parent_app, 'comparison_queue'):
            self.status_label.configure(text="⚠️ データがありません")
            return
        
        queue = self.parent_app.comparison_queue
        if not queue:
            self.status_label.configure(text="⚠️ キューが空です - クロールを実行してください")
            return
        
        # 全Webページを収集
        self.web_pages = []  # List of dicts with image, url, title
        for item in queue:
            if item.get('type') == 'web':
                screenshot_b64 = item.get('screenshot_base64')
                if screenshot_b64:
                    try:
                        img_data = base64.b64decode(screenshot_b64)
                        img = Image.open(io.BytesIO(img_data))
                        self.web_pages.append({
                            'image': img,
                            'url': item.get('url', ''),
                            'title': item.get('title', 'Untitled'),
                            'text': item.get('text_content', item.get('text', ''))
                        })
                    except Exception as e:
                        print(f"画像読み込みエラー: {e}")
        
        # PDFデータをロード
        self._load_pdf_data()
        
        # 最初のページを表示
        if self.web_pages:
            self.current_web_page_idx = 0
            self.web_image = self.web_pages[0]['image']
            self._display_image(self.web_canvas, self.web_image)
            
            # Overview Mapにページ一覧を表示
            self._generate_page_selector()
            
            self.status_label.configure(
                text=f"✅ Webデータロード完了: {len(self.web_pages)}ページ"
            )
            self.page_label.configure(
                text=f"Page 1 / {len(self.web_pages)}"
            )
        else:
            self.status_label.configure(text="⚠️ Webデータがありません")
    
    def _load_pdf_data(self):
        """PDFデータをロード - 全ページを収集"""
        self.pdf_pages_list = []  # List of dicts with image, title
        
        # UnifiedAppにselected_pdf_pagesがあるかチェック (メイン)
        if hasattr(self.parent_app, 'selected_pdf_pages') and self.parent_app.selected_pdf_pages:
            print(f"📄 PDF読み込み: {len(self.parent_app.selected_pdf_pages)}ページ検出")
            for i, img in enumerate(self.parent_app.selected_pdf_pages):
                self.pdf_pages_list.append({
                    'image': img,
                    'title': f'PDF ページ {i+1}'
                })
        
        # selected_pdf_pagesが空の場合はcomparison_queueから取得
        if not self.pdf_pages_list and hasattr(self.parent_app, 'comparison_queue'):
            pdf_items = [item for item in self.parent_app.comparison_queue if item.get('type') == 'pdf']
            print(f"📄 Queue からPDF読み込み: {len(pdf_items)}ページ")
            
            for item in pdf_items:
                img_b64 = item.get('image_base64')
                if img_b64:
                    try:
                        img_data = base64.b64decode(img_b64)
                        img = Image.open(io.BytesIO(img_data))
                        self.pdf_pages_list.append({
                            'image': img,
                            'title': item.get('title', f"PDF ページ {len(self.pdf_pages_list)+1}")
                        })
                    except Exception as e:
                        print(f"PDF画像読み込みエラー: {e}")
        
        print(f"📄 PDF合計: {len(self.pdf_pages_list)}ページ")
        
        # 10ページごとに縦連結した画像を作成
        if self.pdf_pages_list:
            self.pdf_stitched_groups = []  # 10ページごとのグループ
            pages_per_group = 10
            
            for group_idx in range(0, len(self.pdf_pages_list), pages_per_group):
                group_pages = self.pdf_pages_list[group_idx:group_idx + pages_per_group]
                stitched_img = self._stitch_pages_vertically([p['image'] for p in group_pages])
                self.pdf_stitched_groups.append({
                    'image': stitched_img,
                    'page_range': f"{group_idx + 1}-{min(group_idx + pages_per_group, len(self.pdf_pages_list))}"
                })
            
            # 最初のグループを表示
            self.current_pdf_group_idx = 0
            if self.pdf_stitched_groups:
                self.pdf_image = self.pdf_stitched_groups[0]['image']
                self._display_image(self.pdf_canvas, self.pdf_image)
                
                # ページラベル更新
                total_groups = len(self.pdf_stitched_groups)
                self.pdf_page_label.configure(
                    text=f"1-{min(pages_per_group, len(self.pdf_pages_list))}/{len(self.pdf_pages_list)}"
                )
            
            self.status_label.configure(
                text=f"✅ Web: {len(getattr(self, 'web_pages', []))}p | PDF: {len(self.pdf_pages_list)}p ({len(self.pdf_stitched_groups)}グループ)"
            )
    
    def _stitch_pages_vertically(self, images: list) -> Image.Image:
        """複数の画像を縦に連結"""
        if not images:
            return Image.new('RGB', (100, 100), (30, 30, 30))
        
        # 最大幅に合わせる
        max_width = max(img.width for img in images)
        total_height = sum(img.height for img in images)
        
        # 連結画像を作成
        stitched = Image.new('RGB', (max_width, total_height), (30, 30, 30))
        y_offset = 0
        
        for img in images:
            # 幅を統一
            if img.width != max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            stitched.paste(img, (0, y_offset))
            y_offset += img.height
        
        return stitched
    
    def _generate_page_selector(self):
        """Overviewにページセレクターを生成"""
        if not hasattr(self, 'web_pages') or not self.web_pages:
            return
        
        # 古いウィジェットをクリア
        for widget in self.overview_scroll.winfo_children():
            widget.destroy()
        
        thumb_frame = ctk.CTkFrame(self.overview_scroll, fg_color="transparent")
        thumb_frame.pack(fill="x")
        
        self._page_thumbnails = []  # 参照を保持
        
        for i, page_data in enumerate(self.web_pages):
            # サムネイル生成
            img_copy = page_data['image'].copy()
            img_copy.thumbnail((60, 100))
            photo = ImageTk.PhotoImage(img_copy)
            self._page_thumbnails.append(photo)  # 参照を保持
            
            # 現在のページかどうか
            is_current = (i == getattr(self, 'current_web_page_idx', 0))
            
            btn = ctk.CTkButton(
                thumb_frame,
                image=photo,
                text=f"P{i+1}",
                compound="top",
                width=70,
                height=110,
                fg_color="#4A4A4A" if is_current else "#2D2D2D",
                command=lambda idx=i: self._select_web_page(idx)
            )
            btn.pack(side="left", padx=2, pady=2)
    
    def _select_web_page(self, idx: int):
        """Webページを選択"""
        if not hasattr(self, 'web_pages') or idx >= len(self.web_pages):
            return
        
        self.current_web_page_idx = idx
        self.web_image = self.web_pages[idx]['image']
        self._display_image(self.web_canvas, self.web_image)
        
        # エリアをクリア
        self.web_regions = []
        self._redraw_regions()
        
        # サムネイル更新
        self._generate_page_selector()
        
        # ステータス更新
        page_title = self.web_pages[idx].get('title', '')[:30]
        self.page_label.configure(
            text=f"Page {idx+1} / {len(self.web_pages)}"
        )
        self.status_label.configure(
            text=f"📄 {page_title}..."
        )
    
    def _display_image(self, canvas: tk.Canvas, image: Image.Image):
        """画像を表示 (幅優先フィット + 縦スクロール対応)"""
        if not image or image.width == 0 or image.height == 0:
            return
        
        # キャンバスサイズ取得
        canvas.update_idletasks()
        canvas_width = max(canvas.winfo_width(), 100)  # 最小100px
        
        # 幅に合わせてリサイズ (縦は比例)
        img_copy = image.copy()
        scale_factor = canvas_width / img_copy.width
        new_width = max(canvas_width, 1)
        new_height = max(int(img_copy.height * scale_factor), 1)
        
        img_copy = img_copy.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(img_copy)
        canvas.delete("all")
        
        # 左上に配置
        canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
        canvas.image = photo
        
        # スクロール領域を設定
        canvas.configure(scrollregion=(0, 0, new_width, new_height))
        
        # スケール情報を保存 (エリア座標変換用)
        canvas.scale_x = scale_factor
        canvas.scale_y = scale_factor
        canvas.offset_x = 0
        canvas.offset_y = 0
    
    def _run_ocr_analysis(self):
        """OCR + クラスタリング + Sync分析を実行"""
        if not self.web_image and not self.pdf_image:
            self.status_label.configure(text="⚠️ 画像がありません")
            return
        
        self.status_label.configure(text="🔄 OCR実行中...")
        self.update()
        
        try:
            from app.core.engine_cloud import CloudOCREngine
            from app.core.page_detector import PageBreakDetector
            from app.core.sync_matcher import SyncMatcher, AreaCode
            
            engine = CloudOCREngine()
            detector = PageBreakDetector()
            
            total_web_clusters = 0
            total_pdf_clusters = 0
            
            # Web OCR
            if self.web_image:
                clusters, raw_words = engine.extract_text(self.web_image)
                total_web_clusters = len(clusters)
                print(f"[AdvancedView] ★ Web OCR完了: clusters={len(clusters)}, raw_words={len(raw_words)}")
                
                # ページ検出
                pages = detector.detect_breaks(self.web_image, clusters)
                self.page_regions = [(p.y_start, p.y_end) for p in pages]
                print(f"[AdvancedView] ★ ページ検出: {len(self.page_regions)}ページ")
                
                # web_pagesにテキストを保存
                if hasattr(self, 'web_pages') and self.web_pages:
                    full_text = ' '.join(c.get('text', '') for c in clusters)
                    for i, page in enumerate(self.web_pages):
                        page['text'] = full_text
                        page['clusters'] = clusters
                
                # エリア生成
                self.web_regions = []
                for i, c in enumerate(clusters):
                    page_num = 1
                    y_center = (c['rect'][1] + c['rect'][3]) // 2
                    for j, (y_start, y_end) in enumerate(self.page_regions):
                        if y_start <= y_center < y_end:
                            page_num = j + 1
                            break
                    
                    seq = i + 1
                    region = EditableRegion(
                        id=c.get('id', i+1),
                        rect=c['rect'],
                        text=c.get('text', ''),
                        area_code=f"P{page_num}-{seq}",
                        sync_number=None,
                        similarity=1.0,
                        source="web"
                    )
                    self.web_regions.append(region)
            
            # PDF OCR
            if self.pdf_image:
                pdf_clusters, pdf_raw = engine.extract_text(self.pdf_image)
                total_pdf_clusters = len(pdf_clusters)
                
                # pdf_pages_listにテキストを保存
                if hasattr(self, 'pdf_pages_list') and self.pdf_pages_list:
                    full_pdf_text = ' '.join(c.get('text', '') for c in pdf_clusters)
                    for i, page in enumerate(self.pdf_pages_list):
                        page['text'] = full_pdf_text
                        page['clusters'] = pdf_clusters
                
                # PDFエリア生成
                self.pdf_regions = []
                for i, c in enumerate(pdf_clusters):
                    region = EditableRegion(
                        id=c.get('id', i+1),
                        rect=c['rect'],
                        text=c.get('text', ''),
                        area_code=f"PDF-{i+1}",
                        sync_number=None,
                        similarity=1.0,
                        source="pdf"
                    )
                    self.pdf_regions.append(region)
            
            # エリアリスト更新
            self._update_area_list()
            
            # 描画
            self._redraw_regions()
            
            # デバッグ: 領域数とスケール確認
            print(f"[AdvancedView] web_regions: {len(self.web_regions)}, pdf_regions: {len(self.pdf_regions)}")
            print(f"[AdvancedView] web_canvas scale_x: {getattr(self.web_canvas, 'scale_x', 'NOT SET')}")
            print(f"[AdvancedView] pdf_canvas scale_x: {getattr(self.pdf_canvas, 'scale_x', 'NOT SET')}")
            
            # ページサムネイル生成
            self._generate_thumbnails()
            
            self.status_label.configure(
                text=f"✅ OCR完了: Web {total_web_clusters}エリア, PDF {total_pdf_clusters}エリア"
            )
            if hasattr(self, 'page_regions') and self.page_regions:
                self.page_label.configure(
                    text=f"Page {self.current_page} / {len(self.page_regions)}"
                )
            
            # ★ 自動Sync計算実行
            self.after(100, self._auto_sync_and_display)
            
        except Exception as e:
            self.status_label.configure(text=f"❌ OCRエラー: {e}")
            print(f"OCR Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _auto_sync_and_display(self):
        """OCR後に自動でSync計算 + 範囲最適化 + 全テキスト表示 (高速化版)"""
        self.status_label.configure(text="🔄 自動Sync計算中...")
        self.update()
        
        # 1. ベースSync (UI更新なし)
        # まず標準的なパラグラフマッチングを行う
        self._recalculate_sync(update_ui=False)
        
        try:
            from app.core.cluster_matcher import AnchorMatcher, RangeOptimizationSimulator
            
            # 2. 範囲最適化 (Range Optimization)
            # 既存のペアに対して、領域を微調整してスコア向上を狙う
            if hasattr(self, 'sync_pairs') and self.sync_pairs:
                optimizer = RangeOptimizationSimulator()
                results = optimizer.optimize_all_pairs(
                    self.web_regions,
                    self.pdf_regions,
                    self.sync_pairs
                )
                
                # 最適化が行われた場合、テキスト/領域が変更されているため再計算 (UI更新なし)
                if results:
                    print(f"[RangeOptimizer] {len(results)}件の範囲を最適化しました")
                    self._recalculate_sync(update_ui=False)

            # 3. アンカーマッチング (Anchor Matcher) - 最終決定権
            # アンカー情報は絶対的なので、標準マッチングの結果を上書きする形で適用
            self.status_label.configure(text="⚓ アンカーポイント照合中...")
            self.update()
            
            anchor_matcher = AnchorMatcher()
            anchor_matches = anchor_matcher.match_clusters(self.web_regions, self.pdf_regions)
            
            if anchor_matches:
                print(f"[AnchorMatcher] {len(anchor_matches)}件のアンカーマッチを適用")
                # マッチ結果を反映（類似度情報を領域に書き込み）
                for m in anchor_matches:
                    m.web_region.similarity = m.similarity
                    m.web_region.sync_color = "#9C27B0"  # マゼンタ (アンカー一致)
                    
                    # PDF側も更新
                    m.pdf_region.similarity = m.similarity
                    m.pdf_region.sync_color = "#9C27B0"
            
            # 4. 最終描画
            self._redraw_regions_with_sync()
            
            # 5. UI成分の手動更新 (Silent Sync対応)
            total_web = len(self.web_regions)
            # 類似度はVisual(Region)を正とする
            match_count = sum(1 for r in self.web_regions if hasattr(r, 'similarity') and r.similarity >= 0.3)
            
            sync_percent = (match_count / total_web * 100) if total_web > 0 else 0
            
            # Status Label
            self.status_label.configure(text=f"✅ 最適化完了 (Matched: {match_count}/{total_web})")
            
            # Sync Rate Label
            color = "#4CAF50" if sync_percent >= 50 else "#FF9800" if sync_percent >= 30 else "#F44336"
            self.sync_rate_label.configure(text=f"Sync Rate: {sync_percent:.1f}%", text_color=color)
            if hasattr(self, 'sync_rate_display'):
                self.sync_rate_display.configure(text=f"Sync: {sync_percent:.1f}%")

            # Stats Label (Spreadsheet Header)
            if hasattr(self, 'stats_label'):
                 self.stats_label.configure(text=f"Web: {total_web} | PDF: {len(self.pdf_regions)} | マッチ: {match_count}")
                 
            # Spreadsheet Body (Sync Pairs更新)
            # アンカーマッチの結果をsync_pairsにも反映してリスト表示を整合させる
            if anchor_matches and hasattr(self, 'sync_pairs'):
                for m in anchor_matches:
                    for p in self.sync_pairs:
                        if p.web_id == m.web_region.area_code:
                            p.similarity = m.similarity
            
            self._refresh_inline_spreadsheet()


        except Exception as e:
            print(f"[MatcherStrategy] エラー: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.configure(text=f"❌ 最適化エラー: {e}")
        
        # 全テキスト表示パネルを更新
        self._show_all_texts()


                

    
    def _show_all_texts(self):
        """全パラグラフテキストを一括表示"""
        # Webテキスト集約
        web_text_parts = []
        for region in self.web_regions:
            similarity_str = f"[{region.similarity*100:.0f}%]" if hasattr(region, 'similarity') and region.similarity > 0 else ""
            web_text_parts.append(f"【{region.area_code}】{similarity_str}\n{region.text}\n")
        
        web_all_text = "\n".join(web_text_parts)
        
        # PDFテキスト集約
        pdf_text_parts = []
        for region in self.pdf_regions:
            similarity_str = f"[{region.similarity*100:.0f}%]" if hasattr(region, 'similarity') and region.similarity > 0 else ""
            pdf_text_parts.append(f"【{region.area_code}】{similarity_str}\n{region.text}\n")
        
        pdf_all_text = "\n".join(pdf_text_parts)
        
        # テキストボックスに表示
        if hasattr(self, 'web_text_box'):
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", web_all_text[:5000])  # 最大5000文字
        
        if hasattr(self, 'pdf_text_box'):
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", pdf_all_text[:5000])
        
        # Diff生成
        if hasattr(self, 'diff_text_box'):
            diff_summary = self._generate_diff_summary()
            self.diff_text_box.delete("1.0", "end")
            self.diff_text_box.insert("1.0", diff_summary)
        
        # 選択情報更新
        if hasattr(self, 'selected_info'):
            web_count = len(self.web_regions)
            pdf_count = len(self.pdf_regions)
            matched = len([r for r in self.web_regions if hasattr(r, 'similarity') and r.similarity >= 0.5])
            self.selected_info.configure(
                text=f"Web: {web_count}件 / PDF: {pdf_count}件\nマッチ: {matched}件",
                text_color="white"
            )
    
    def _generate_diff_summary(self) -> str:
        """Sync結果のサマリーを生成"""
        if not hasattr(self, 'sync_pairs'):
            return "Sync未実行"
        
        lines = ["=== Sync Summary ===\n"]
        
        high_matches = [(sp, "🟢") for sp in self.sync_pairs if sp.similarity >= 0.5]
        mid_matches = [(sp, "🟡") for sp in self.sync_pairs if 0.3 <= sp.similarity < 0.5]
        low_matches = [(sp, "🔴") for sp in self.sync_pairs if sp.similarity < 0.3]
        
        lines.append(f"🟢 高一致(50%+): {len(high_matches)}件")
        lines.append(f"🟡 部分一致(30-50%): {len(mid_matches)}件")
        lines.append(f"🔴 低一致(<30%): {len(low_matches)}件\n")
        
        # 上位マッチを表示
        for sp, icon in (high_matches + mid_matches)[:5]:
            lines.append(f"{icon} {sp.web_id} ↔ {sp.pdf_id}: {sp.similarity*100:.0f}%")
        
        return "\n".join(lines)
    
    def _update_area_list(self):
        """エリアリストを更新"""
        # 古いウィジェットをクリア
        for widget in self.area_list.winfo_children():
            widget.destroy()
        
        for region in self.web_regions:
            # エリアカード
            card = ctk.CTkFrame(self.area_list, fg_color="#3A3A3A", corner_radius=5)
            card.pack(fill="x", pady=2)
            
            # 状態アイコン
            if region.similarity >= 0.95:
                status = "✅"
                color = "#4CAF50"
            elif region.similarity >= 0.70:
                status = "⚠️"
                color = "#FF9800"
            else:
                status = "❌"
                color = "#F44336"
            
            ctk.CTkLabel(
                card,
                text=f"{status} {region.area_code}",
                font=("Consolas", 10, "bold"),
                text_color=color
            ).pack(side="left", padx=8, pady=5)
            
            ctk.CTkLabel(
                card,
                text=f"{region.similarity:.0%}",
                font=("Meiryo", 9),
                text_color="gray"
            ).pack(side="right", padx=8)
            
            # クリックで選択
            card.bind("<Button-1>", lambda e, r=region: self._select_region(r))
    
    def _generate_thumbnails(self):
        """ページサムネイルを生成 - 改善版"""
        if not self.web_image or not self.page_regions:
            # プレースホルダ表示
            for widget in self.overview_scroll.winfo_children():
                widget.destroy()
            ctk.CTkLabel(
                self.overview_scroll,
                text="OCRを実行するとセグメントが表示されます",
                font=("Meiryo", 10),
                text_color="gray"
            ).pack(pady=20)
            return
        
        # 古いウィジェットをクリア
        for widget in self.overview_scroll.winfo_children():
            widget.destroy()
        
        # ページごとのサムネイル（縦並び・大きめ）
        self._thumbnail_photos = []  # 参照保持
        
        for i, (y_start, y_end) in enumerate(self.page_regions):
            is_current = (i + 1 == self.current_page)
            
            # ページ行
            row = ctk.CTkFrame(
                self.overview_scroll, 
                fg_color="#4A4A4A" if is_current else "#2D2D2D",
                corner_radius=5
            )
            row.pack(fill="x", pady=3, padx=2)
            
            # ページ切り抜き・サムネイル
            try:
                cropped = self.web_image.crop((0, y_start, self.web_image.width, y_end))
                cropped.thumbnail((80, 60))  # 横長サムネイル
                photo = ImageTk.PhotoImage(cropped)
                self._thumbnail_photos.append(photo)
                
                thumb_label = ctk.CTkLabel(row, image=photo, text="")
                thumb_label.pack(side="left", padx=5, pady=5)
                thumb_label.bind("<Button-1>", lambda e, p=i+1: self._goto_page(p))
            except:
                pass
            
            # ページ番号とマッチ情報
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=5)
            
            # セグメント番号
            page_label = ctk.CTkLabel(
                info_frame,
                text=f"🔷 Seg.{i+1}",
                font=("Meiryo", 11, "bold"),
                text_color="white" if is_current else "#AAAAAA"
            )
            page_label.pack(anchor="w")
            page_label.bind("<Button-1>", lambda e, p=i+1: self._goto_page(p))
            
            # マッチング情報（あれば）
            if hasattr(self, 'web_page_entries') and i < len(self.web_page_entries):
                match_info = self.web_page_entries[i].match_display
                best_sim = self.web_page_entries[i].overall_sync
                
                if best_sim >= 70:
                    color = "#4CAF50"
                elif best_sim >= 40:
                    color = "#FF9800"
                else:
                    color = "#F44336"
                
                match_label = ctk.CTkLabel(
                    info_frame,
                    text=match_info[match_info.find('→')+1:].strip() if '→' in match_info else match_info,
                    font=("Meiryo", 9),
                    text_color=color
                )
                match_label.pack(anchor="w")
            
            # クリックでページ移動
            row.bind("<Button-1>", lambda e, p=i+1: self._goto_page(p))
            info_frame.bind("<Button-1>", lambda e, p=i+1: self._goto_page(p))
    
    def _goto_page(self, page_num: int):
        """指定ページに移動"""
        self.current_page = page_num
        self._display_current_page()
        self._generate_thumbnails()  # 選択状態更新
    
    def _recalculate_sync(self, update_ui: bool = True):
        """WebとPDFのSync率を再計算 (Ultimate Sync)"""
        if not self.web_regions and not self.pdf_regions:
            self.status_label.configure(text="⚠️ OCRを先に実行してください")
            return
        
        if update_ui:
            self._status_label.configure(text="🔄 パラグラフマッチング計算中...")
            self.update()
        
        try:
            from app.core.paragraph_matcher import (
                ParagraphMatcher, ParagraphEntry, 
                create_paragraph_entries_from_clusters
            )
            from app.core.sync_exporter import export_sync_results
            
            # クラスターからParagraphEntryを生成
            web_entries = []
            pdf_entries = []
            
            # Web パラグラフ生成
            for region in self.web_regions:
                entry = ParagraphEntry(
                    id=region.area_code,
                    source="web",
                    text=region.text,
                    rect=list(region.rect),
                    page=int(region.area_code.split('-')[0].replace('P', '')) if '-' in region.area_code else 1
                )
                web_entries.append(entry)
            
            # PDF パラグラフ生成
            for region in self.pdf_regions:
                entry = ParagraphEntry(
                    id=region.area_code,
                    source="pdf",
                    text=region.text,
                    rect=list(region.rect),
                    page=1
                )
                pdf_entries.append(entry)
            
            # マッチング実行
            matcher = ParagraphMatcher(threshold_high=0.5, threshold_low=0.3)
            web_entries, pdf_entries, sync_pairs = matcher.match_paragraphs(web_entries, pdf_entries)
            
            # 保存 (後でExcel出力に使用)
            self.web_paragraph_entries = web_entries
            self.pdf_paragraph_entries = pdf_entries
            self.sync_pairs = sync_pairs
            
            # 領域のsync_color更新
            web_entry_map = {e.id: e for e in web_entries}
            pdf_entry_map = {e.id: e for e in pdf_entries}
            
            for region in self.web_regions:
                if region.area_code in web_entry_map:
                    entry = web_entry_map[region.area_code]
                    region.sync_number = list(web_entry_map.keys()).index(region.area_code) if entry.sync_id else None
                    region.similarity = entry.similarity
                    if not hasattr(region, 'sync_color'):
                        region.sync_color = entry.sync_color
                    else:
                        region.sync_color = entry.sync_color
            
            for region in self.pdf_regions:
                if region.area_code in pdf_entry_map:
                    entry = pdf_entry_map[region.area_code]
                    region.sync_number = list(pdf_entry_map.keys()).index(region.area_code) if entry.sync_id else None
                    region.similarity = entry.similarity
                    if not hasattr(region, 'sync_color'):
                        region.sync_color = entry.sync_color
                    else:
                        region.sync_color = entry.sync_color
            
            # 描画更新 (update_ui=Trueの場合のみ)
            if update_ui:
                self._redraw_regions_with_sync()
            
                # 全体Sync率計算
                overall_sync = matcher.calculate_sync_rate(sync_pairs, len(web_entries), len(pdf_entries))
                overall_percent = overall_sync * 100
                
                color = "#4CAF50" if overall_percent >= 50 else "#FF9800" if overall_percent >= 30 else "#F44336"
                self.sync_rate_label.configure(text=f"Sync Rate: {overall_percent:.1f}%", text_color=color)
                self.sync_rate_display.configure(text=f"Sync: {overall_percent:.1f}%")
                
                # ステータス更新
                high_count = sum(1 for sp in sync_pairs if sp.similarity >= 0.5)
                mid_count = sum(1 for sp in sync_pairs if 0.3 <= sp.similarity < 0.5)
                low_count = sum(1 for sp in sync_pairs if sp.similarity < 0.3)
                
                self.status_label.configure(
                    text=f"✅ Sync完了: 🟢{high_count} 🟡{mid_count} 🔴{low_count}"
                )
                
                # Excelエクスポートボタンを有効化（あれば）
                if hasattr(self, 'export_btn'):
                    self.export_btn.configure(state="normal")
                
                # インラインスプレッドシート更新
                self._refresh_inline_spreadsheet()
            
        except Exception as e:
            print(f"パラグラフマッチングエラー: {e}")
            import traceback
            traceback.print_exc()
            if update_ui:
                self.status_label.configure(text=f"❌ Syncエラー: {e}")
    
    def _redraw_regions_with_sync(self):
        """Sync結果に基づいてマッチしたパラグラフを同色で描画"""
        for canvas, regions, source in [
            (self.web_canvas, self.web_regions, "web"),
            (self.pdf_canvas, self.pdf_regions, "pdf")
        ]:
            # 古い矩形を削除
            canvas.delete("region")
            
            # スケール情報取得
            scale_x = getattr(canvas, 'scale_x', 1.0)
            scale_y = getattr(canvas, 'scale_y', 1.0)
            offset_x = getattr(canvas, 'offset_x', 0)
            offset_y = getattr(canvas, 'offset_y', 0)
            
            for region in regions:
                # 元座標をキャンバス座標に変換
                x1 = region.rect[0] * scale_x + offset_x
                y1 = region.rect[1] * scale_y + offset_y
                x2 = region.rect[2] * scale_x + offset_x
                y2 = region.rect[3] * scale_y + offset_y
                
                # 色決定 (sync_colorを使用)
                outline = getattr(region, 'sync_color', '#F44336')
                width = 3 if region == self.selected_region else 2
                
                # 矩形描画
                canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline=outline, width=width,
                    tags="region"
                )
                
                # エリアコード描画
                similarity_str = f"{region.similarity*100:.0f}%" if hasattr(region, 'similarity') and region.similarity > 0 else ""
                label = f"{region.area_code} {similarity_str}"
                canvas.create_text(
                    x1 + 5, y1 + 5,
                    text=label,
                    fill=outline,
                    anchor="nw",
                    font=("Meiryo", 8, "bold"),
                    tags="region"
                )
    
    def _export_to_excel(self):
        """Sync結果をExcelにエクスポート"""
        print("[Export] Excel出力開始...")
        
        # sync_pairsがなくてもweb/pdf_regionsから直接出力
        if not self.web_regions and not self.pdf_regions:
            self.status_label.configure(text="⚠️ OCRを先に実行してください")
            return
        
        try:
            from app.core.sync_exporter import SyncExporter
            from app.core.paragraph_matcher import ParagraphEntry
            
            # ParagraphEntriesを作成（sync_pairsがなくても対応）
            web_entries = []
            for region in self.web_regions:
                entry = ParagraphEntry(
                    id=region.area_code,
                    source="web",
                    text=region.text,
                    rect=list(region.rect),
                    page=1,
                    similarity=getattr(region, 'similarity', 0.0),
                    sync_color=getattr(region, 'sync_color', '#F44336')
                )
                web_entries.append(entry)
            
            pdf_entries = []
            for region in self.pdf_regions:
                entry = ParagraphEntry(
                    id=region.area_code,
                    source="pdf",
                    text=region.text,
                    rect=list(region.rect),
                    page=1,
                    similarity=getattr(region, 'similarity', 0.0),
                    sync_color=getattr(region, 'sync_color', '#F44336')
                )
                pdf_entries.append(entry)
            
            print(f"[Export] Web entries: {len(web_entries)}, PDF entries: {len(pdf_entries)}")
            
            # sync_pairsを使用（あれば）
            sync_pairs = getattr(self, 'sync_pairs', [])
            
            exporter = SyncExporter(output_dir="./exports")
            output_path = exporter.export_to_excel(
                web_entries,
                pdf_entries,
                sync_pairs,
                self.web_image,
                self.pdf_image
            )
            
            self.status_label.configure(text=f"✅ Excel出力: {output_path}")
            print(f"[Export] 出力完了: {output_path}")
            
            # ファイルを開く
            import os
            os.startfile(output_path)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)[:50]
            self.status_label.configure(text=f"❌ エクスポートエラー: {error_msg}")
    
    def _display_page_matches(self):
        """ページマッチング結果をOverview Mapに表示"""
        # _generate_thumbnails がマッチ情報も表示するようになったので、そちらを呼ぶだけ
        self._generate_thumbnails()
    
    def _open_detail_for_page(self, page_entry=None):
        """詳細インスペクターを開く"""
        from app.gui.windows.detail_inspector import DetailInspectorWindow
        
        current_page = getattr(self, 'current_page', 1)
        print(f"[AdvancedView] _open_detail_for_page called, current_page={current_page}")
        print(f"[AdvancedView] web_image: {self.web_image.size if self.web_image else 'None'}")
        print(f"[AdvancedView] pdf_image: {self.pdf_image.size if self.pdf_image else 'None'}")
        
        web_data = {}
        pdf_data = {}
        
        # Web画像: 現在のページを切り抜き
        if self.web_image and hasattr(self, 'page_regions') and self.page_regions:
            if 0 < current_page <= len(self.page_regions):
                y_start, y_end = self.page_regions[current_page - 1]
                cropped = self.web_image.crop((0, y_start, self.web_image.width, y_end))
                web_data = {'image': cropped}
                print(f"[AdvancedView] Cropped web page {current_page}: ({0}, {y_start}, {self.web_image.width}, {y_end})")
            else:
                web_data = {'image': self.web_image}
        elif self.web_image:
            web_data = {'image': self.web_image}
        
        # PDF画像: 現在はそのまま（全ページ連結）
        if self.pdf_image:
            pdf_data = {'image': self.pdf_image}
        
        print(f"[AdvancedView] Passing web_data keys: {web_data.keys()}")
        print(f"[AdvancedView] Passing pdf_data keys: {pdf_data.keys()}")
        
        window = DetailInspectorWindow(
            self.parent_app,
            web_data=web_data,
            pdf_data=pdf_data
        )
        
        if page_entry:
            window.title(f"🔬 詳細インスペクター - {page_entry.match_display}")
        else:
            window.title(f"🔬 詳細インスペクター - ページ {current_page}")
        
        window.focus()
    
    def _toggle_primary_source(self):
        """主体ソースを切り替え"""
        current = getattr(self, 'primary_source', 'web')
        self.primary_source = 'pdf' if current == 'web' else 'web'
        
        # ボタンテキスト更新
        if hasattr(self, 'primary_toggle_btn'):
            new_text = "主体: PDF→Web" if self.primary_source == 'pdf' else "主体: Web→PDF"
            self.primary_toggle_btn.configure(text=new_text)
        
        # 再マッチング
        self._recalculate_sync()
    
    def _open_fullscreen(self):
        """フルスクリーンで開く"""
        from app.gui.windows.comparison_matrix import ComparisonMatrixWindow
        
        queue = []
        if hasattr(self.parent_app, 'comparison_queue'):
            queue = self.parent_app.comparison_queue
        
        window = ComparisonMatrixWindow(self.parent_app, comparison_queue=queue)
        window.focus()
    
    def _open_comparison_spreadsheet(self):
        """比較スプレッドシートウィンドウを開く (画面2)"""
        from app.gui.windows.comparison_spreadsheet import ComparisonSpreadsheetWindow
        
        def on_row_select(row, action):
            """スプレッドシート行選択時のコールバック"""
            target_id = row.web_id or row.pdf_id  # ComparisonRowにはweb_id/pdf_idがある
            if action == "click":
                # 対応するエリアをハイライト
                for region in self.web_regions:
                    if region.area_code == target_id:
                        self.selected_region = region
                        self._redraw_regions()
                        break
                for region in self.pdf_regions:
                    if region.area_code == target_id:
                        self.selected_region = region
                        self._redraw_regions()
                        break
            elif action == "double_click":
                # ズームして表示
                for region in self.web_regions:
                    if region.area_code == target_id:
                        self._zoom_to_region(region)
                        break
        
        # ウィンドウ作成
        self.spreadsheet_window = ComparisonSpreadsheetWindow(
            self.parent_app,
            on_row_select=on_row_select
        )
        
        # データ渡す
        sync_pairs = getattr(self, 'sync_pairs', [])
        self.spreadsheet_window.load_data(
            self.web_regions,
            self.pdf_regions,
            self.web_image,
            self.pdf_image,
            sync_pairs
        )
        
        self.spreadsheet_window.focus()
        self.status_label.configure(text="📊 比較シートを別ウィンドウで開きました")
    
    def _zoom_to_region(self, region):
        """指定リージョンにズーム"""
        # TODO: 編集モードでズーム機能実装
        self.selected_region = region
        self._redraw_regions()
        self.status_label.configure(text=f"🔍 {region.area_code} を選択")
    
    # ===== 編集モード機能 =====
    
    def _toggle_edit_mode(self):
        """編集モードの切り替え"""
        self.edit_mode = not self.edit_mode
        
        if self.edit_mode:
            self.edit_mode_btn.configure(
                text="✏️ 編集中", 
                fg_color="#E91E63"
            )
            self.status_label.configure(text="✏️ 編集モード: ドラッグで範囲選択、矩形をクリックで移動/リサイズ")
            
            # キャンバスにドラッグイベントをバインド
            for canvas in [self.web_canvas, self.pdf_canvas]:
                canvas.bind("<Button-1>", self._on_edit_click)
                canvas.bind("<B1-Motion>", self._on_edit_drag)
                canvas.bind("<ButtonRelease-1>", self._on_edit_release)
        else:
            self.edit_mode_btn.configure(
                text="✏️ 編集", 
                fg_color="#616161"
            )
            self.status_label.configure(text="")
            
            # 選択ボックスをクリア
            if self.selection_box:
                for canvas in [self.web_canvas, self.pdf_canvas]:
                    canvas.delete("selection_box")
                self.selection_box = None
    
    def _on_edit_click(self, event):
        """編集モードでのクリック"""
        if not self.edit_mode:
            return
        
        canvas = event.widget
        self.selection_canvas = canvas
        self.drag_start = (event.x, event.y)
        
        # 既存の選択矩形を削除
        canvas.delete("selection_box")
        
        # クリックした場所に既存リージョンがあるかチェック
        clicked_region = self._find_region_at(canvas, event.x, event.y)
        if clicked_region:
            self.selected_region = clicked_region
            self.drag_handle = "move"
            self._highlight_selected_region()
        else:
            self.selection_box = [event.x, event.y, event.x, event.y]
    
    def _on_edit_drag(self, event):
        """編集モードでのドラッグ"""
        if not self.edit_mode or not self.drag_start:
            return
        
        canvas = event.widget
        
        if self.selected_region and self.drag_handle == "move":
            # リージョンを移動
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            
            scale_x = getattr(canvas, 'scale_x', 1.0)
            scale_y = getattr(canvas, 'scale_y', 1.0)
            
            # 元座標で移動量を計算
            dx_orig = dx / scale_x
            dy_orig = dy / scale_y
            
            self.selected_region.rect[0] += int(dx_orig)
            self.selected_region.rect[1] += int(dy_orig)
            self.selected_region.rect[2] += int(dx_orig)
            self.selected_region.rect[3] += int(dy_orig)
            
            self.drag_start = (event.x, event.y)
            self._redraw_regions()
            
        elif self.selection_box:
            # 選択ボックスを更新
            self.selection_box[2] = event.x
            self.selection_box[3] = event.y
            
            canvas.delete("selection_box")
            canvas.create_rectangle(
                self.selection_box[0], self.selection_box[1],
                self.selection_box[2], self.selection_box[3],
                outline="#00BFFF", width=2, dash=(4, 4),
                tags="selection_box"
            )
    
    def _on_edit_release(self, event):
        """編集モードでのリリース"""
        if not self.edit_mode:
            return
        
        canvas = event.widget
        
        if self.selection_box and abs(self.selection_box[2] - self.selection_box[0]) > 10:
            # 新しい選択範囲を確定
            scale_x = getattr(canvas, 'scale_x', 1.0)
            scale_y = getattr(canvas, 'scale_y', 1.0)
            offset_x = getattr(canvas, 'offset_x', 0)
            offset_y = getattr(canvas, 'offset_y', 0)
            
            # キャンバス座標 → 元画像座標
            x1 = int((min(self.selection_box[0], self.selection_box[2]) - offset_x) / scale_x)
            y1 = int((min(self.selection_box[1], self.selection_box[3]) - offset_y) / scale_y)
            x2 = int((max(self.selection_box[0], self.selection_box[2]) - offset_x) / scale_x)
            y2 = int((max(self.selection_box[1], self.selection_box[3]) - offset_y) / scale_y)
            
            # 選択範囲を保存 (詳細インスペクターに渡せる)
            self.custom_selection = {
                'rect': [x1, y1, x2, y2],
                'canvas': 'web' if canvas == self.web_canvas else 'pdf'
            }
            
            self.status_label.configure(
                text=f"✅ 選択範囲: ({x1}, {y1}) - ({x2}, {y2})"
            )
            
            # 詳細インスペクターを開くボタンを有効化（または直接開く）
            self._open_detail_for_selection()
        
        self.drag_start = None
        self.selected_region = None
        self.drag_handle = None
    
    def _find_region_at(self, canvas, x, y) -> Optional[EditableRegion]:
        """指定座標にあるリージョンを探す"""
        regions = self.web_regions if canvas == self.web_canvas else self.pdf_regions
        
        scale_x = getattr(canvas, 'scale_x', 1.0)
        scale_y = getattr(canvas, 'scale_y', 1.0)
        offset_x = getattr(canvas, 'offset_x', 0)
        offset_y = getattr(canvas, 'offset_y', 0)
        
        for region in regions:
            rx1 = region.rect[0] * scale_x + offset_x
            ry1 = region.rect[1] * scale_y + offset_y
            rx2 = region.rect[2] * scale_x + offset_x
            ry2 = region.rect[3] * scale_y + offset_y
            
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                return region
        
        return None
    
    def _highlight_selected_region(self):
        """選択中のリージョンをハイライト"""
        if not self.selected_region:
            return
        
        # 再描画で選択状態を反映
        self._redraw_regions()
    
    def _open_detail_for_selection(self):
        """選択範囲を詳細インスペクターで開く"""
        if not hasattr(self, 'custom_selection') or not self.custom_selection:
            return
        
        from app.gui.windows.detail_inspector import DetailInspectorWindow
        
        rect = self.custom_selection['rect']
        source = self.custom_selection['canvas']
        
        web_data = {}
        pdf_data = {}
        
        # 選択範囲を切り抜き
        if source == 'web' and self.web_image:
            x1, y1, x2, y2 = rect
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(self.web_image.width, x2), min(self.web_image.height, y2)
            cropped = self.web_image.crop((x1, y1, x2, y2))
            web_data = {'image': cropped}
        elif source == 'pdf' and self.pdf_image:
            x1, y1, x2, y2 = rect
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(self.pdf_image.width, x2), min(self.pdf_image.height, y2)
            cropped = self.pdf_image.crop((x1, y1, x2, y2))
            pdf_data = {'image': cropped}
        
        # 相手側の画像も渡す
        if source == 'web' and self.pdf_image:
            pdf_data = {'image': self.pdf_image}
        elif source == 'pdf' and self.web_image:
            web_data = {'image': self.web_image}
        
        window = DetailInspectorWindow(
            self.parent_app,
            web_data=web_data,
            pdf_data=pdf_data
        )
        window.title(f"🔬 詳細インスペクター - 選択範囲")
        window.focus()
    
    def _detach_panel(self, panel_type: str):
        """パネルを別ウィンドウに分離"""
        # 分離ウィンドウ作成
        detached = ctk.CTkToplevel(self.parent_app)
        detached.title(f"{'🌐 Web Source' if panel_type == 'web' else '📄 PDF Source'}")
        detached.geometry("700x600")
        detached.configure(fg_color="#1E1E1E")
        
        # ヘッダー
        header = ctk.CTkFrame(detached, fg_color="#2D2D2D", height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text=f"{'🌐 Web Source' if panel_type == 'web' else '📄 PDF Source'} (分離ウィンドウ)",
            font=("Meiryo", 12, "bold")
        ).pack(side="left", padx=15, pady=8)
        
        # ステータス
        status_label = ctk.CTkLabel(header, text="", font=("Meiryo", 10), text_color="gray")
        status_label.pack(side="right", padx=10)
        
        # キャンバスフレーム
        canvas_frame = ctk.CTkFrame(detached, fg_color="#1A1A1A")
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # キャンバス + スクロールバー
        canvas = tk.Canvas(canvas_frame, bg="#1A1A1A", highlightthickness=0)
        scrollbar_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollbar_x = ttk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールスクロール
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas.bind("<Shift-MouseWheel>", lambda e: canvas.xview_scroll(int(-1*(e.delta/120)), "units"))
        
        # 画像を表示
        image = self.web_image if panel_type == "web" else self.pdf_image
        if image:
            # フルサイズで表示（スクロール可能）
            photo = ImageTk.PhotoImage(image)
            canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
            canvas.image = photo
            canvas.configure(scrollregion=(0, 0, image.width, image.height))
            status_label.configure(text=f"{image.width}x{image.height}px")
            
            # 領域描画
            regions = self.web_regions if panel_type == "web" else self.pdf_regions
            for region in regions:
                x1, y1, x2, y2 = region.rect
                color = getattr(region, 'sync_color', '#FF9800')
                canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="region")
                canvas.create_text(x1+3, y1+3, text=region.area_code, fill=color, anchor="nw", font=("Meiryo", 8, "bold"), tags="region")
        else:
            ctk.CTkLabel(canvas_frame, text="画像がありません", font=("Meiryo", 12), text_color="gray").pack(pady=50)
        
        # フッター
        footer = ctk.CTkFrame(detached, fg_color="#2D2D2D", height=35)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        
        ctk.CTkLabel(
            footer, text="ウィンドウをリサイズして拡大/縮小",
            font=("Meiryo", 9), text_color="gray"
        ).pack(side="left", padx=10, pady=8)
        
        detached.focus()
        self.status_label.configure(text=f"↗️ {panel_type.upper()} Sourceを分離ウィンドウで開きました")
    
    def _toggle_edit_mode(self):
        """テキスト編集モード切替"""
        is_editing = self.edit_mode_var.get()
        self.edit_mode_var.set(not is_editing)
        
        if not is_editing:
            # 編集モードON - テキストボックスを拡大
            self.web_text_box.configure(state="normal", fg_color="#2D3A2D", height=200)  # 高さ拡大
            self.pdf_text_box.configure(state="normal", fg_color="#2D3A3D", height=200)  # 高さ拡大
            self.diff_text_box.configure(height=150)  # Diffも拡大
            self.status_label.configure(text="✏️ 編集モード: テキストを修正後「保存して再計算」をクリック")
        else:
            # 編集モードOFF - 元のサイズに戻す
            self.web_text_box.configure(state="disabled", fg_color="#1E1E1E", height=80)
            self.pdf_text_box.configure(state="disabled", fg_color="#1E1E1E", height=80)
            self.diff_text_box.configure(height=100)
            self.status_label.configure(text="📖 閲覧モード")
    
    def _save_edited_text(self):
        """編集したテキストを保存してSync再計算"""
        try:
            # 編集後のテキストを取得
            web_text = self.web_text_box.get("1.0", "end-1c").strip()
            pdf_text = self.pdf_text_box.get("1.0", "end-1c").strip()
            
            # 現在選択中のペアを特定
            if hasattr(self, '_current_selected_web_id') and hasattr(self, '_current_selected_pdf_id'):
                # 既存のパラグラフを更新
                for entry in self.web_paragraphs:
                    if entry.id == self._current_selected_web_id:
                        entry.text = web_text
                        break
                
                for entry in self.pdf_paragraphs:
                    if entry.id == self._current_selected_pdf_id:
                        entry.text = pdf_text
                        break
            
            # 類似度を再計算
            from app.core.paragraph_matcher import ParagraphMatcher
            matcher = ParagraphMatcher()
            similarity = matcher.calculate_similarity(web_text, pdf_text)
            
            # 類似度表示を更新
            color = "#4CAF50" if similarity >= 0.5 else "#FF9800" if similarity >= 0.3 else "#F44336"
            self.similarity_label.configure(
                text=f"Similarity: {similarity * 100:.1f}%",
                text_color=color
            )
            
            # Diff表示を更新
            self._update_diff_display(web_text, pdf_text)
            
            self.status_label.configure(text=f"✅ テキスト保存完了 - 類似度: {similarity * 100:.1f}%")
            
            # 編集モードをOFFに
            self.edit_mode_var.set(False)
            self.web_text_box.configure(state="disabled", fg_color="#1E1E1E")
            self.pdf_text_box.configure(state="disabled", fg_color="#1E1E1E")
            
        except Exception as e:
            self.status_label.configure(text=f"❌ 保存エラー: {e}")
    
    def _update_diff_display(self, text1: str, text2: str):
        """Diff表示を更新"""
        try:
            import difflib
            diff = difflib.unified_diff(
                text1.splitlines(keepends=True),
                text2.splitlines(keepends=True),
                fromfile="Web",
                tofile="PDF",
                lineterm=""
            )
            diff_text = ''.join(diff)
            
            self.diff_text_box.configure(state="normal")
        except Exception:
            pass
    
    # ============================================================
    # Canvas Drag Selection - 画像上で矩形選択→テキスト抽出
    # ============================================================
    
    def _on_canvas_click(self, event):
        """キャンバスクリック - 選択開始"""
        canvas = event.widget
        
        # スクロール位置を考慮した実座標
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # 選択開始点を記録
        self._selection_start = (x, y)
        self._selection_canvas = canvas
        self._selection_source = "web" if canvas == self.web_canvas else "pdf"
        
        # 既存の選択矩形を削除
        canvas.delete("selection_rect")
    
    def _on_canvas_drag(self, event):
        """キャンバスドラッグ - 選択範囲描画"""
        if not hasattr(self, '_selection_start') or self._selection_start is None:
            return
        
        canvas = event.widget
        if canvas != self._selection_canvas:
            return
        
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        x1, y1 = self._selection_start
        
        # 選択矩形を描画
        canvas.delete("selection_rect")
        canvas.create_rectangle(
            x1, y1, x, y,
            outline="#00FF00", width=2, dash=(4, 2),
            tags="selection_rect"
        )
    
    def _on_canvas_release(self, event):
        """キャンバスリリース - 選択完了→テキスト抽出"""
        if not hasattr(self, '_selection_start') or self._selection_start is None:
            return
        
        canvas = event.widget
        if canvas != self._selection_canvas:
            return
        
        x2 = canvas.canvasx(event.x)
        y2 = canvas.canvasy(event.y)
        x1, y1 = self._selection_start
        
        # 正規化 (左上→右下)
        rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        
        # 選択範囲が小さすぎる場合はスキップ
        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            self._selection_start = None
            return
        
        # 選択範囲内のテキストを抽出
        extracted_text = self._extract_text_from_region(rect, self._selection_source)
        
        # テキストボックスに表示
        if self._selection_source == "web":
            self.web_text_box.configure(state="normal")
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", extracted_text)
        else:
            self.pdf_text_box.configure(state="normal")
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", extracted_text)
        
        # 選択完了
        canvas.itemconfig("selection_rect", outline="#4CAF50", dash=())
        self.status_label.configure(text=f"✅ {self._selection_source.upper()}から{len(extracted_text)}文字抽出")
        
        self._selection_start = None
    
    def _extract_text_from_region(self, rect, source: str) -> str:
        """選択範囲内のOCR領域からテキストを抽出"""
        x1, y1, x2, y2 = rect
        
        # 対象のパラグラフリスト
        paragraphs = self.web_paragraphs if source == "web" else self.pdf_paragraphs
        
        extracted_parts = []
        
        for para in paragraphs:
            px1, py1, px2, py2 = para.rect
            
            # 選択範囲と重なるかチェック
            if self._rects_overlap((x1, y1, x2, y2), (px1, py1, px2, py2)):
                extracted_parts.append(para.text)
        
        return '\n'.join(extracted_parts)
    
    def _rects_overlap(self, rect1, rect2) -> bool:
        """2つの矩形が重なっているか判定"""
        x1_1, y1_1, x2_1, y2_1 = rect1
        x1_2, y1_2, x2_2, y2_2 = rect2
        
        return not (x2_1 < x1_2 or x2_2 < x1_1 or y2_1 < y1_2 or y2_2 < y1_1)
    
    # ============================================================
    # Region Editor - 領域エディタ起動
    # ============================================================
    
    def _open_region_editor(self, source_type: str):
        """領域エディタを開く"""
        from app.gui.windows.region_editor import RegionEditor
        
        # 画像と領域データを取得
        if source_type == "web":
            image = self.web_image
            # web_regionsを優先、なければweb_paragraphsを使用
            if hasattr(self, 'web_regions') and self.web_regions:
                regions = [
                    {'id': r.area_code, 'rect': list(r.rect), 'text': r.text, 'color': getattr(r, 'sync_color', '#FF9800')}
                    for r in self.web_regions
                ]
            elif hasattr(self, 'web_paragraphs') and self.web_paragraphs:
                regions = [
                    {'id': p.id, 'rect': p.rect, 'text': p.text, 'color': getattr(p, 'sync_color', '#FF9800')}
                    for p in self.web_paragraphs
                ]
            else:
                regions = []
            print(f"[RegionEditor] Web: {len(regions)}件の領域をロード")
        else:
            image = self.pdf_image
            # pdf_regionsを優先、なければpdf_paragraphsを使用
            if hasattr(self, 'pdf_regions') and self.pdf_regions:
                regions = [
                    {'id': r.area_code, 'rect': list(r.rect), 'text': r.text, 'color': getattr(r, 'sync_color', '#2196F3')}
                    for r in self.pdf_regions
                ]
            elif hasattr(self, 'pdf_paragraphs') and self.pdf_paragraphs:
                regions = [
                    {'id': p.id, 'rect': p.rect, 'text': p.text, 'color': getattr(p, 'sync_color', '#2196F3')}
                    for p in self.pdf_paragraphs
                ]
            else:
                regions = []
            print(f"[RegionEditor] PDF: {len(regions)}件の領域をロード")
        
        if image is None:
            self.status_label.configure(text="❌ 画像がありません")
            return
        
        # エディタを開く
        editor = RegionEditor(
            self,
            image=image,
            regions=regions,
            source_type=source_type,
            on_update_callback=self._on_region_update
        )
        
        self.status_label.configure(text=f"🖊️ {source_type.upper()} 領域エディタを開きました")
    
    def _on_region_update(self, source_type: str, updated_regions: list):
        """領域エディタからの更新を反映 - 手動編集を保持"""
        from app.core.paragraph_matcher import ParagraphEntry
        
        print(f"[RegionEditor] 更新受信: {source_type}, {len(updated_regions)}件")
        
        # 1. EditableRegion リストを更新 (これが _recalculate_sync で使用される)
        new_regions = []
        for r in updated_regions:
            from app.gui.windows.advanced_comparison_view import EditableRegion
            region = EditableRegion(
                id=0,
                rect=r['rect'],
                text=r['text'],
                area_code=r['id'],
                sync_number=None,
                similarity=0.0,
                source=source_type
            )
            region.sync_color = r.get('color', '#FF9800')
            new_regions.append(region)
        
        if source_type == "web":
            self.web_regions = new_regions
        else:
            self.pdf_regions = new_regions
        
        # 2. ParagraphEntry リストも更新 (互換性のため)
        new_paragraphs = []
        for r in updated_regions:
            entry = ParagraphEntry(
                id=r['id'],
                source=source_type,
                text=r['text'],
                rect=r['rect'],
                page=1,
                sync_color=r.get('color', '#FF9800')
            )
            new_paragraphs.append(entry)
        
        if source_type == "web":
            self.web_paragraphs = new_paragraphs
        else:
            self.pdf_paragraphs = new_paragraphs
        
        # 3. 画面を更新 (既存のメソッドを使用)
        self._redraw_regions()
        self._refresh_inline_spreadsheet()
        
        self.status_label.configure(text=f"✅ {source_type.upper()} 領域を更新しました ({len(updated_regions)}件)")
        print(f"[RegionEditor] {source_type}_regions 更新完了: {len(new_regions)}件")
    
    # ============================================================
    # 高度クラスターマッチング
    # ============================================================
    
    def _run_advanced_cluster_matching(self):
        """高度マッチング実行 (現在はAnchorMatcherによる最適化パイプラインを使用)"""
        print("[AdvancedMatch] ★ ボタンクリック検出 - Anchor Optimizationへ転送", flush=True)
        
        if not self.web_regions or not self.pdf_regions:
            self.status_label.configure(text="⚠️ OCRを先に実行してください")
            return
            
        self.status_label.configure(text="🧠 高度アンカーマッチング実行中...")
        self.update()
        
        try:
            # Auto Syncパイプラインを再実行 (これが現在のベストプラクティス)
            # Silentモードではなく、明示的に実行することでUI更新も含む
            self._auto_sync_and_display()
            
            # ステータス上書き
            self.status_label.configure(text="✅ 高度マッチング完了 (Anchor Optimization)")
            
        except Exception as e:
            self.status_label.configure(text=f"❌ エラー: {e}")
            print(f"[AdvancedMatch] Error: {e}")
            import traceback
            traceback.print_exc()
            import tkinter.messagebox as mb
            mb.showerror("エラー", str(e))
            

    
    def _get_color_for_score(self, score: float) -> str:
        """スコアに応じた色を返す"""
        if score >= 0.5:
            return "#4CAF50"  # 緑
        elif score >= 0.3:
            return "#FF9800"  # オレンジ
        else:
            return "#F44336"  # 赤
    
    def _show_suggestions_popup(self, suggestions: list):
        """サジェストポップアップを表示"""
        popup = ctk.CTkToplevel(self)
        popup.title("📋 マッチング改善サジェスト")
        popup.geometry("600x400")
        popup.configure(fg_color="#1E1E1E")
        
        # ヘッダー
        ctk.CTkLabel(
            popup, text="🧠 高マッチ率を目指すための改善提案",
            font=("Meiryo", 14, "bold")
        ).pack(pady=10)
        
        # スクロール可能なリスト
        list_frame = ctk.CTkScrollableFrame(popup, fg_color="#252525")
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i, s in enumerate(suggestions):
            row = ctk.CTkFrame(list_frame, fg_color="#333333")
            row.pack(fill="x", pady=2)
            
            # 優先度アイコン
            priority_icon = "🔴" if s.priority == 1 else "🟡" if s.priority == 2 else "🟢"
            
            # 領域ID
            web_id = s.web_region.area_code if hasattr(s.web_region, 'area_code') else str(i)
            pdf_id = s.pdf_region.area_code if hasattr(s.pdf_region, 'area_code') else str(i)
            
            ctk.CTkLabel(
                row, 
                text=f"{priority_icon} {web_id} ↔ {pdf_id}",
                font=("Meiryo", 10, "bold")
            ).pack(side="left", padx=10, pady=5)
            
            ctk.CTkLabel(
                row,
                text=f"{s.current_similarity*100:.0f}% → {s.predicted_similarity*100:.0f}%",
                font=("Meiryo", 10),
                text_color="#4CAF50" if s.predicted_similarity > s.current_similarity else "#888"
            ).pack(side="left", padx=10)
            
            ctk.CTkLabel(
                row,
                text=s.adjustment_reason,
                font=("Meiryo", 9),
                text_color="#888"
            ).pack(side="left", padx=10, fill="x", expand=True)
        
        # 閉じるボタン
        ctk.CTkButton(
            popup, text="閉じる", width=100,
            command=popup.destroy
        ).pack(pady=10)
        
        popup.focus()
