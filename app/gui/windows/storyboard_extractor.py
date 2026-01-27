"""
StoryboardExtractor - コンテ素材抽出ツール GUI

Phase 2.5: NotebookLM等で生成されたPDFから
文字と画像をレイヤー分離してExcel/PowerPointに出力

メインアプリから独立したウィンドウとして起動
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import threading
import io

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    print("⚠️ CustomTkinter not available")

from PIL import Image, ImageTk

# SelectionMixin 統合 - comparison_matrix流用
try:
    from app.gui.windows.comparison_mixins.selection_mixin import SelectionMixin
    SELECTION_MIXIN_AVAILABLE = True
except ImportError:
    SELECTION_MIXIN_AVAILABLE = False
    print("⚠️ SelectionMixin not available")


class StoryboardExtractor(ctk.CTkToplevel if CTK_AVAILABLE else tk.Toplevel):
    """
    コンテ素材抽出ツール - 専用GUI
    
    機能:
    1. PDFインポート
    2. レイヤー分離ビュー（文字/画像）
    3. 画像パーツ分割エディタ
    4. Excel/PowerPointエクスポート
    """
    
    WINDOW_TITLE = "📎 コンテ素材抽出ツール"
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title(self.WINDOW_TITLE)
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        
        # データ
        self.current_pdf_path: Optional[str] = None
        self.layer_result = None
        self.paragraphs: List = []
        self.image_parts: List = []
        
        # 画像参照保持（GC防止）
        self._image_refs = []
        
        # パイプラインモジュール
        self._layer_separator = None
        self._paragraph_splitter = None
        self._image_slicer = None
        self._exporter = None

        # SDK (v2)
        self._layer_analyzer = None
        self._sheet_generator = None

        # リサイズ対応 (comparison_matrix流用)
        self._resize_job = None
        self._last_canvas_size = {}
        self._display_in_progress = False
        self._current_page_image = None  # 現在表示中のPDF画像
        
        # 選択機能 (SelectionMixin互換)
        self._edit_mode = False
        self._selection_start = None
        self._selection_rect_id = None
        self._selections = []  # 選択済み領域リスト
        self._selection_counter = 0  # SEL_001, SEL_002...
        
        # クロスヘア座標表示 (comparison_matrix流用)
        self._crosshair_enabled = True
        self._last_crosshair_pos = None
        
        # UI構築
        self._build_ui()
        
        # キーバインド
        self.bind("<Escape>", lambda e: self.destroy())
        
        # フォーカス
        self.focus_force()
        self.lift()
    
    def _build_ui(self):
        """UIを構築 - v2: 3パネルレイアウト (comparison_matrix準拠)"""
        # ★ ステータスバー (ウィンドウ下部に配置 - comparison_matrix流用)
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color="#1A1A1A") if CTK_AVAILABLE else tk.Frame(self, height=30, bg="#1A1A1A")
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)
        
        self.bottom_status_label = ctk.CTkLabel(
            self.status_bar,
            text="📌 Ready - PDFを読み込んでください",
            font=("Consolas", 11),
            text_color="#00FF00",
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.status_bar, text="📌 Ready", font=("Consolas", 11), fg="#00FF00", anchor="w")
        self.bottom_status_label.pack(side="left", fill="x", expand=True, padx=10)
        
        # メインPanedWindow: 上部/下部を垂直分割
        self.main_paned = tk.PanedWindow(self, orient=tk.VERTICAL, sashwidth=5, bg="#444444")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        # ===== 上部フレーム: Action + Source View =====
        top_frame = ctk.CTkFrame(self.main_paned, fg_color="#2B2B2B") if CTK_AVAILABLE else tk.Frame(self.main_paned)
        self.main_paned.add(top_frame, height=500, minsize=300)  # 最小高さ設定

        # 上部を左右に分割
        # 左パネル (Action Panel)
        self.action_panel = ctk.CTkFrame(top_frame, width=250, corner_radius=0, fg_color="#2D2D2D") if CTK_AVAILABLE else tk.Frame(top_frame, width=250)
        self.action_panel.pack(side="left", fill="y")
        self.action_panel.pack_propagate(False)

        self._build_action_panel()

        # 右パネル (Source View)
        self.source_panel = ctk.CTkFrame(top_frame, fg_color="#2D2D2D") if CTK_AVAILABLE else tk.Frame(top_frame)
        self.source_panel.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self._build_source_panel()

        # ===== 下部フレーム: 素材シート =====
        bottom_frame = ctk.CTkFrame(self.main_paned, fg_color="#1E1E1E") if CTK_AVAILABLE else tk.Frame(self.main_paned)
        self.main_paned.add(bottom_frame, height=250, minsize=100)  # 最小高さ設定

        self._build_material_sheet(bottom_frame)
        
        # サッシュ変更時に画像を再描画
        self.main_paned.bind("<ButtonRelease-1>", self._on_sash_release)
    
    def _build_action_panel(self):
        """Action Panelを構築 (v2: レイヤー統計 + エクスポート拡張)"""
        # ロゴ/タイトル
        title_label = ctk.CTkLabel(
            self.action_panel,
            text="📎 コンテ素材抽出",
            font=("Meiryo", 18, "bold")
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="📎 コンテ素材抽出", font=("Meiryo", 18, "bold"))
        title_label.pack(pady=(20, 5))

        subtitle = ctk.CTkLabel(
            self.action_panel,
            text="Storyboard Asset Extractor",
            font=("Meiryo", 10),
            text_color="gray"
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="Storyboard Asset Extractor", font=("Meiryo", 10), fg="gray")
        subtitle.pack(pady=(0, 20))
        
        # セパレーター
        if CTK_AVAILABLE:
            sep1 = ctk.CTkFrame(self.action_panel, height=2, fg_color="gray30")
            sep1.pack(fill="x", padx=20, pady=10)

        # === インポートセクション ===
        section_import = ctk.CTkLabel(
            self.action_panel,
            text="📥 インポート",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="📥 インポート", font=("Meiryo", 12, "bold"), anchor="w")
        section_import.pack(fill="x", padx=20, pady=(10, 5))

        # PDFインポートボタン
        self.import_btn = ctk.CTkButton(
            self.action_panel,
            text="📄 PDFを開く",
            command=self._import_pdf,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=("Meiryo", 14)
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="📄 PDFを開く", command=self._import_pdf)
        self.import_btn.pack(fill="x", padx=20, pady=5)

        # ファイル情報ラベル
        self.file_label = ctk.CTkLabel(
            self.action_panel,
            text="ファイル未選択",
            font=("Meiryo", 10),
            text_color="gray",
            wraplength=200
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="ファイル未選択", font=("Meiryo", 10), fg="gray", wraplength=200)
        self.file_label.pack(fill="x", padx=20, pady=(0, 10))
        
        # セパレーター
        if CTK_AVAILABLE:
            sep2 = ctk.CTkFrame(self.action_panel, height=2, fg_color="gray30")
            sep2.pack(fill="x", padx=20, pady=10)
        
        # === 抽出セクション ===
        section_extract = ctk.CTkLabel(
            self.action_panel,
            text="🔍 レイヤー抽出",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="🔍 レイヤー抽出", font=("Meiryo", 12, "bold"), anchor="w")
        section_extract.pack(fill="x", padx=20, pady=(10, 5))
        
        # テキスト抽出
        self.extract_text_btn = ctk.CTkButton(
            self.action_panel,
            text="📝 テキスト抽出",
            command=self._extract_text_layer,
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="📝 テキスト抽出", command=self._extract_text_layer, state="disabled")
        self.extract_text_btn.pack(fill="x", padx=20, pady=3)
        
        # 画像抽出
        self.extract_image_btn = ctk.CTkButton(
            self.action_panel,
            text="🖼️ 画像抽出",
            command=self._extract_image_layer,
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="🖼️ 画像抽出", command=self._extract_image_layer, state="disabled")
        self.extract_image_btn.pack(fill="x", padx=20, pady=3)

        # 一括OCR (v2: Gemini Vision使用)
        self.batch_ocr_btn = ctk.CTkButton(
            self.action_panel,
            text="🤖 一括OCR (AI)",
            command=lambda: self._run_batch_ocr(),
            fg_color="#FF6B35",
            hover_color="#E85A24",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="🤖 一括OCR (AI)", command=lambda: self._run_batch_ocr(), state="disabled")
        self.batch_ocr_btn.pack(fill="x", padx=20, pady=3)

        # 🖊️編集ボタン (SelectionMixin互換 - comparison_matrix流用)
        self.edit_btn = ctk.CTkButton(
            self.action_panel,
            text="🖊️ 手動選択",
            command=self._toggle_edit_mode,
            fg_color="#6B7280",
            hover_color="#4B5563",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="🖊️ 手動選択", command=self._toggle_edit_mode, state="disabled")
        self.edit_btn.pack(fill="x", padx=20, pady=3)
        
        # セパレーター
        if CTK_AVAILABLE:
            sep3 = ctk.CTkFrame(self.action_panel, height=2, fg_color="gray30")
            sep3.pack(fill="x", padx=20, pady=10)

        # === レイヤー統計セクション (v2) ===
        section_stats = ctk.CTkLabel(
            self.action_panel,
            text="📊 レイヤー統計",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="📊 レイヤー統計", font=("Meiryo", 12, "bold"), anchor="w")
        section_stats.pack(fill="x", padx=20, pady=(10, 5))

        # 統計表示フレーム
        self.stats_frame = ctk.CTkFrame(self.action_panel, fg_color="#3A3A3A") if CTK_AVAILABLE else tk.Frame(self.action_panel)
        self.stats_frame.pack(fill="x", padx=20, pady=5)

        # テキストレイヤー統計
        self.text_stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="テキスト: --",
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.stats_frame, text="テキスト: --", font=("Meiryo", 10), fg="gray", anchor="w")
        self.text_stats_label.pack(fill="x", padx=10, pady=3)

        # 画像レイヤー統計
        self.image_stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="画像: --",
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.stats_frame, text="画像: --", font=("Meiryo", 10), fg="gray", anchor="w")
        self.image_stats_label.pack(fill="x", padx=10, pady=3)

        # セパレーター
        if CTK_AVAILABLE:
            sep4 = ctk.CTkFrame(self.action_panel, height=2, fg_color="gray30")
            sep4.pack(fill="x", padx=20, pady=10)

        # === エクスポートセクション ===
        section_export = ctk.CTkLabel(
            self.action_panel,
            text="📤 エクスポート",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="📤 エクスポート", font=("Meiryo", 12, "bold"), anchor="w")
        section_export.pack(fill="x", padx=20, pady=(10, 5))
        
        # Excelエクスポート
        self.export_excel_btn = ctk.CTkButton(
            self.action_panel,
            text="📊 Excelに出力",
            command=self._export_excel,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="📊 Excelに出力", command=self._export_excel, state="disabled")
        self.export_excel_btn.pack(fill="x", padx=20, pady=3)
        
        # PowerPointエクスポート
        self.export_pptx_btn = ctk.CTkButton(
            self.action_panel,
            text="📑 PowerPointに出力",
            command=self._export_pptx,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="📑 PowerPointに出力", command=self._export_pptx, state="disabled")
        self.export_pptx_btn.pack(fill="x", padx=20, pady=3)

        # CSVエクスポート (v2)
        self.export_csv_btn = ctk.CTkButton(
            self.action_panel,
            text="📄 CSVに出力",
            command=self._export_csv,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="📄 CSVに出力", command=self._export_csv, state="disabled")
        self.export_csv_btn.pack(fill="x", padx=20, pady=3)

        # PNGエクスポート (v2)
        self.export_png_btn = ctk.CTkButton(
            self.action_panel,
            text="🖼️ PNGに出力",
            command=self._export_png,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.action_panel, text="🖼️ PNGに出力", command=self._export_png, state="disabled")
        self.export_png_btn.pack(fill="x", padx=20, pady=3)

        # プログレスバー (v2)
        if CTK_AVAILABLE:
            self.progress_bar = ctk.CTkProgressBar(self.action_panel, mode="indeterminate")
            self.progress_bar.pack(fill="x", padx=20, pady=10)
            self.progress_bar.set(0)

        # ステータス表示（下部）- より目立つ色
        self.status_label = ctk.CTkLabel(
            self.action_panel,
            text="📌 Ready",
            font=("Meiryo", 11, "bold"),
            text_color="#00BFFF",
            wraplength=220
        ) if CTK_AVAILABLE else tk.Label(self.action_panel, text="📌 Ready", font=("Meiryo", 11, "bold"), fg="#00BFFF", wraplength=220)
        self.status_label.pack(side="bottom", pady=20)
    
    def _build_source_panel(self):
        """Source Panelを構築 (v2: テキスト/画像の2タブのみ)"""
        # タブビュー
        if CTK_AVAILABLE:
            self.tabview = ctk.CTkTabview(self.source_panel)
            self.tabview.pack(fill="both", expand=True)

            # タブ追加 (v2: 2タブのみ)
            self.tab_text = self.tabview.add("📝 テキスト")
            self.tab_images = self.tabview.add("🖼️ 画像")
        else:
            # tkinterの場合はNotebookを使用
            import tkinter.ttk as ttk
            self.tabview = ttk.Notebook(self.source_panel)
            self.tabview.pack(fill="both", expand=True)

            self.tab_text = tk.Frame(self.tabview)
            self.tab_images = tk.Frame(self.tabview)

            self.tabview.add(self.tab_text, text="📝 テキスト")
            self.tabview.add(self.tab_images, text="🖼️ 画像")

        # 各タブの内容を構築
        self._build_text_tab()
        self._build_images_tab()
    
    def _build_material_sheet(self, parent):
        """素材シートを構築 (v2: 下部パネル)"""
        # ヘッダー
        header_frame = ctk.CTkFrame(parent, fg_color="#2A2A2A", height=40) if CTK_AVAILABLE else tk.Frame(parent, height=40)
        header_frame.pack(fill="x", padx=5, pady=5)
        header_frame.pack_propagate(False)

        header_label = ctk.CTkLabel(
            header_frame,
            text="📋 素材シート",
            font=("Meiryo", 14, "bold")
        ) if CTK_AVAILABLE else tk.Label(header_frame, text="📋 素材シート", font=("Meiryo", 14, "bold"))
        header_label.pack(side="left", padx=10)

        # スクロール可能なコンテナ
        self.sheet_scroll = ctk.CTkScrollableFrame(parent) if CTK_AVAILABLE else tk.Frame(parent)
        self.sheet_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # プレースホルダー
        placeholder = ctk.CTkLabel(
            self.sheet_scroll,
            text="レイヤー抽出後、ここに素材が表示されます",
            text_color="gray",
            font=("Meiryo", 11)
        ) if CTK_AVAILABLE else tk.Label(self.sheet_scroll, text="レイヤー抽出後、ここに素材が表示されます", fg="gray", font=("Meiryo", 11))
        placeholder.pack(pady=50)

    def _build_text_tab(self):
        """テキストタブを構築 (v2: Canvas + スクロールバー + 手動選択)"""
        import tkinter.ttk as ttk
        
        # キャンバスコンテナ
        canvas_frame = ctk.CTkFrame(self.tab_text, fg_color="#2D2D2D") if CTK_AVAILABLE else tk.Frame(self.tab_text)
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Canvas + Scrollbar (comparison_matrixパターン)
        self.text_canvas = tk.Canvas(canvas_frame, bg="#1E1E1E", highlightthickness=0)
        text_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.text_canvas.yview)
        self.text_canvas.configure(yscrollcommand=text_scrollbar.set)
        text_scrollbar.pack(side="right", fill="y")
        self.text_canvas.pack(side="left", fill="both", expand=True)

        # マウスホイールスクロール
        self.text_canvas.bind("<MouseWheel>", lambda e: self.text_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # ★ クロスヘア座標表示 (comparison_matrix流用 - 常時バインド)
        self.text_canvas.bind("<Motion>", lambda e: self._on_mouse_motion(e, self.text_canvas))
        self.text_canvas.bind("<Leave>", lambda e: self._on_mouse_leave(e, self.text_canvas))

        # プレースホルダー
        self.text_canvas.create_text(
            400, 300,
            text="PDFを読み込んでください",
            fill="gray60",
            font=("Meiryo", 14),
            tags="placeholder"
        )

        # リサイズ対応 (comparison_matrixパターン)
        self.text_canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e, "text"))

        # 手動範囲選択バインディング (v2)
        self._selection_rect = None
        self._selection_start = None
        self.text_canvas.bind("<Button-1>", self._on_selection_start)
        self.text_canvas.bind("<B1-Motion>", self._on_selection_drag)
        self.text_canvas.bind("<ButtonRelease-1>", self._on_selection_end)

    def _on_selection_start(self, event):
        """手動選択開始"""
        self._selection_start = (event.x, event.y)
        # 既存の選択矩形を削除
        if self._selection_rect:
            self.text_canvas.delete(self._selection_rect)
            self._selection_rect = None

    def _on_selection_drag(self, event):
        """手動選択ドラッグ中"""
        if not self._selection_start:
            return
        
        x0, y0 = self._selection_start
        x1, y1 = event.x, event.y
        
        # 矩形を描画/更新
        if self._selection_rect:
            self.text_canvas.coords(self._selection_rect, x0, y0, x1, y1)
        else:
            self._selection_rect = self.text_canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="#00D4FF",
                width=2,
                dash=(5, 5),
                tags="selection"
            )

    def _on_selection_end(self, event):
        """手動選択完了"""
        if not self._selection_start:
            return
        
        x0, y0 = self._selection_start
        x1, y1 = event.x, event.y
        
        # 選択範囲が小さすぎる場合は無視
        if abs(x1 - x0) < 10 or abs(y1 - y0) < 10:
            if self._selection_rect:
                self.text_canvas.delete(self._selection_rect)
                self._selection_rect = None
            return
        
        # 選択範囲を正規化
        bbox = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        
        # 選択範囲を確定表示
        if self._selection_rect:
            self.text_canvas.itemconfig(self._selection_rect, outline="#FFD700", dash=())
        
        self._set_status(f"選択範囲: ({bbox[0]}, {bbox[1]}) - ({bbox[2]}, {bbox[3]})")
        
        # TODO: 選択範囲からテキスト/画像を抽出する処理を追加
        print(f"[Selection] BBox: {bbox}")
    
    def _build_images_tab(self):
        """画像タブを構築 (v2: Canvas + スクロールバー + 手動選択)"""
        import tkinter.ttk as ttk
        
        # キャンバスコンテナ
        canvas_frame = ctk.CTkFrame(self.tab_images, fg_color="#2D2D2D") if CTK_AVAILABLE else tk.Frame(self.tab_images)
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Canvas + Scrollbar (comparison_matrixパターン)
        self.images_canvas = tk.Canvas(canvas_frame, bg="#1E1E1E", highlightthickness=0)
        images_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.images_canvas.yview)
        self.images_canvas.configure(yscrollcommand=images_scrollbar.set)
        images_scrollbar.pack(side="right", fill="y")
        self.images_canvas.pack(side="left", fill="both", expand=True)

        # マウスホイールスクロール
        self.images_canvas.bind("<MouseWheel>", lambda e: self.images_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # ★ クロスヘア座標表示 (comparison_matrix流用 - 常時バインド)
        self.images_canvas.bind("<Motion>", lambda e: self._on_mouse_motion(e, self.images_canvas))
        self.images_canvas.bind("<Leave>", lambda e: self._on_mouse_leave(e, self.images_canvas))

        # プレースホルダー
        self.images_canvas.create_text(
            400, 300,
            text="PDFを読み込んでください",
            fill="gray60",
            font=("Meiryo", 14),
            tags="placeholder"
        )

        # リサイズ対応 (comparison_matrixパターン)
        self.images_canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e, "images"))
    
    # ===== アクションハンドラ =====
    
    def _import_pdf(self):
        """PDFをインポート"""
        file_path = filedialog.askopenfilename(
            title="PDFファイルを選択",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        
        if not file_path:
            return
        
        self.current_pdf_path = file_path
        self.file_label.configure(text=Path(file_path).name)
        self._set_status("PDF読み込み中...")

        # ボタン有効化
        self._enable_buttons()

        # PDF画像を表示 (v2)
        self._show_pdf_on_canvas()

        self._set_status(f"読み込み完了: {Path(file_path).name}")

    def _show_pdf_on_canvas(self):
        """PDFをテキスト/画像キャンバスに表示 (v2)"""
        if not self.current_pdf_path:
            return
        
        try:
            from app.pipeline.storyboard.layer_separator import LayerSeparator
            
            if self._layer_separator is None:
                self._layer_separator = LayerSeparator(force_ocr=False)
            
            # 最初のページを画像としてレンダリング
            preview_img = self._layer_separator.render_page_as_image(
                self.current_pdf_path, 
                page_num=0, 
                scale=1.5
            )
            
            if preview_img:
                # 画像を保存 (リサイズ用)
                self._current_page_image = preview_img
                
                # ★ 遅延呼び出し: UIレイアウト完了を待ってから表示
                # CTkTabviewのタブは初回表示時にサイズが確定しない問題への対処
                def _delayed_display():
                    print(f"🎨 [DelayedDisplay] Executing after 100ms delay...", flush=True)
                    self._display_image_on_canvas(self.text_canvas, preview_img)
                    self._display_image_on_canvas(self.images_canvas, preview_img)
                
                self.after(100, _delayed_display)
                
        except Exception as e:
            print(f"⚠️ PDF preview failed: {e}")
            import traceback
            traceback.print_exc()

    def _display_image_on_canvas(self, canvas, pil_image):
        """画像を表示 (幅優先フィット + 縦スクロール対応) - comparison_matrix流用"""
        try:
            # ★ 描画中フラグを設定（configureイベント干渉防止）
            self._display_in_progress = True

            if not pil_image or not hasattr(pil_image, 'width') or pil_image.width == 0 or pil_image.height == 0:
                print(f"[_display_image] SKIP: invalid image")
                self._display_in_progress = False
                return

            # キャンバスサイズ取得（レイアウト完了を待つ）
            self.update_idletasks()
            self.update()
            canvas.update_idletasks()

            # キャンバス幅を取得（複数の方法を試行）
            canvas_width = canvas.winfo_width()
            if canvas_width <= 1:
                # 親コンテナから幅を取得
                parent = canvas.master
                if parent:
                    canvas_width = parent.winfo_width()
            if canvas_width <= 1:
                # それでもダメなら、selfの幅を分割して使用
                canvas_width = max(self.winfo_width() // 2 - 50, 400)
            canvas_width = max(canvas_width, 400)  # 最小400px

            # キャンバス高さも取得
            canvas_height = canvas.winfo_height()
            if canvas_height <= 1:
                parent = canvas.master
                if parent:
                    canvas_height = parent.winfo_height()
            if canvas_height <= 1:
                canvas_height = max(self.winfo_height() - 200, 300)
            canvas_height = max(canvas_height, 300)

            print(f"[_display_image] canvas={canvas_width}x{canvas_height}, image={pil_image.size}")

            # ★ 幅優先Fit: キャンバス幅に合わせてスケール（縦はスクロール）
            img_copy = pil_image.copy()
            scale_factor = canvas_width / img_copy.width  # 幅優先

            new_width = max(int(img_copy.width * scale_factor), 1)
            new_height = max(int(img_copy.height * scale_factor), 1)

            # サイズ制限（パフォーマンス保護）
            if new_height > 50000:
                scale_factor = 50000 / img_copy.height
                new_width = max(int(img_copy.width * scale_factor), 1)
                new_height = 50000

            print(f"[_display_image] Resized: {new_width}x{new_height} (scale: {scale_factor:.2f})")

            img_copy = img_copy.resize((new_width, new_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img_copy)
            self._image_refs.append(photo)
            
            # 画像のみ削除
            canvas.delete("all")

            # ★ 画像を(0,0)に配置（スクロール可能）
            canvas.create_image(0, 0, anchor="nw", image=photo, tags="pdf_image")
            canvas.image = photo

            # ★ scrollregionを画像全体に設定（スクロール可能）
            canvas.configure(scrollregion=(0, 0, new_width, new_height))
            canvas.yview_moveto(0)
            canvas.xview_moveto(0)

            # 画像サイズを保存（手動選択用/リサイズ用）
            canvas._pdf_image_info = {
                "width": new_width,
                "height": new_height,
                "offset_x": 0,
                "offset_y": 0,
                "scale_factor": scale_factor
            }

            # ★ 描画完了フラグをリセット
            self._display_in_progress = False

        except Exception as e:
            self._display_in_progress = False
            print(f"⚠️ Display image failed: {e}")
            import traceback
            traceback.print_exc()

    def _on_canvas_configure(self, event, source: str):
        """
        スマートリサイズハンドラ (comparison_matrix流用)
        - サイズ変化を検知して必要な場合のみ再描画
        - 150msのデバウンスでリサイズ完了を待機
        """
        # 描画中はスキップ
        if getattr(self, '_display_in_progress', False):
            return

        # 最小サイズチェック
        if event.width < 50 or event.height < 50:
            return

        # サイズ変化チェック（5px以上の変化のみ処理）
        current_size = (event.width, event.height)
        last_size = self._last_canvas_size.get(source, (0, 0))
        if abs(current_size[0] - last_size[0]) < 5 and abs(current_size[1] - last_size[1]) < 5:
            return

        # 前回のジョブをキャンセル
        if self._resize_job:
            self.after_cancel(self._resize_job)

        # 150ms後に再描画（リサイズ完了を待機）
        def _smart_redisplay():
            self._resize_job = None
            self._execute_smart_resize(source)

        self._resize_job = self.after(150, _smart_redisplay)

    def _execute_smart_resize(self, source: str):
        """実際のリサイズ処理を実行 (comparison_matrix流用)"""
        try:
            # フラグは最後にリセットするので、ここでは設定しない
            if not self._current_page_image:
                print("[SmartResize] No image to resize")
                return

            resized_any = False
            
            # 両方のキャンバスを更新（どちらがトリガーでも）
            for canvas_name, canvas in [("text", self.text_canvas), ("images", self.images_canvas)]:
                if not canvas or not canvas.winfo_exists():
                    continue
                    
                new_size = (canvas.winfo_width(), canvas.winfo_height())
                old_size = self._last_canvas_size.get(canvas_name, (0, 0))

                # サイズが変わった場合のみ更新
                if new_size != old_size and new_size[0] > 100 and new_size[1] > 100:
                    self._last_canvas_size[canvas_name] = new_size
                    self._display_in_progress = True  # 描画中フラグ
                    self._display_image_on_canvas(canvas, self._current_page_image)
                    self._display_in_progress = False
                    resized_any = True
                    print(f"[SmartResize] {canvas_name}: {old_size} -> {new_size}")

            if resized_any:
                self._set_status("✅ 画像サイズ調整完了")

        except Exception as e:
            print(f"[SmartResize] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._display_in_progress = False

    def _on_sash_release(self, event):
        """PanedWindowのサッシュ移動後に画像を再描画"""
        # 少し遅延してから再描画（レイアウトが確定してから）
        self.after(100, lambda: self._execute_smart_resize("sash"))
    
    def _extract_text_layer(self):
        """テキストレイヤーを抽出（バックグラウンドスレッドで実行）"""
        if not self.current_pdf_path:
            return
        
        self._set_status("テキスト抽出中... (処理には時間がかかります)", show_progress=True)
        self.extract_text_btn.configure(state="disabled")
        
        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=self._do_text_extraction, daemon=True)
        thread.start()
    
    def _do_text_extraction(self):
        """実際のテキスト抽出処理（バックグラウンドスレッド）"""
        try:
            from app.pipeline.storyboard.layer_separator import LayerSeparator
            from app.pipeline.storyboard.paragraph_splitter import ParagraphSplitter
            
            print(f"[DEBUG] Starting text extraction for: {self.current_pdf_path}")
            
            if self._layer_separator is None:
                self._layer_separator = LayerSeparator(force_ocr=False)  # 埋め込みテキスト優先、なければOCR
                print("[DEBUG] LayerSeparator created with force_ocr=True")
            if self._paragraph_splitter is None:
                self._paragraph_splitter = ParagraphSplitter()
            
            # レイヤー抽出
            print("[DEBUG] Calling extract_layers...")
            self.layer_result = self._layer_separator.extract_layers(self.current_pdf_path)
            print(f"[DEBUG] LayerResult: text_blocks={len(self.layer_result.text_layer.blocks)}, images={len(self.layer_result.image_layer.blocks)}")
            print(f"[DEBUG] Full text length: {len(self.layer_result.text_layer.full_text)}")
            
            # パラグラフ分割
            self.paragraphs = self._paragraph_splitter.split_from_blocks(
                self.layer_result.text_layer.blocks
            )
            print(f"[DEBUG] Paragraphs created: {len(self.paragraphs)}")
            
            # GUIスレッドで更新
            self.after(0, self._on_text_extraction_complete)
            
        except Exception as e:
            import traceback
            print(f"[DEBUG] Error in text extraction: {e}")
            traceback.print_exc()
            self.after(0, lambda: self._on_text_extraction_error(str(e)))
    
    def _on_text_extraction_complete(self):
        """テキスト抽出完了時のGUI更新"""
        # テキスト表示を更新
        self._update_text_display()

        # レイヤー統計を更新 (v2)
        self._update_layer_stats()

        # 素材シートを更新 (v2)
        self._update_material_sheet()

        # エクスポートボタン有効化
        self.export_excel_btn.configure(state="normal")
        self.export_pptx_btn.configure(state="normal")
        self.export_csv_btn.configure(state="normal")
        self.export_png_btn.configure(state="normal")
        self.extract_text_btn.configure(state="normal")

        self._set_status(f"テキスト抽出完了: {len(self.paragraphs)}パラグラフ")

        # テキストタブに切り替え
        if CTK_AVAILABLE:
            self.tabview.set("📝 テキスト")
    
    def _on_text_extraction_error(self, error_msg: str):
        """テキスト抽出エラー時のGUI更新"""
        self.extract_text_btn.configure(state="normal")
        self._set_status(f"エラー: {error_msg}")
        messagebox.showerror("エラー", f"テキスト抽出に失敗しました:\n{error_msg}")
    
    def _update_text_display(self):
        """テキスト表示を更新 (v2: Canvasにテキストブロック描画)"""
        # プレースホルダーを削除
        self.text_canvas.delete("placeholder")

        # TODO: 実際のテキストブロック表示は素材シートで行う
        # Canvasには PDF画像 + ハイライト表示を実装予定
        self._set_status(f"テキストブロック {len(self.paragraphs)}件を抽出しました")
    
    def _extract_image_layer(self):
        """画像レイヤーを抽出"""
        if not self.current_pdf_path:
            return
        
        self._set_status("画像抽出中...")
        
        try:
            from app.pipeline.storyboard.layer_separator import LayerSeparator
            
            if self._layer_separator is None:
                self._layer_separator = LayerSeparator(force_ocr=False)  # 埋め込みテキスト優先、なければOCR
            
            if self.layer_result is None:
                self.layer_result = self._layer_separator.extract_layers(self.current_pdf_path)
            
            # 画像一覧を表示
            self._update_images_display()

            # レイヤー統計を更新 (v2)
            self._update_layer_stats()

            # 素材シートを更新 (v2)
            self._update_material_sheet()

            self._set_status(f"画像抽出完了: {len(self.layer_result.image_layer.blocks)}枚")

            # 画像タブに切り替え
            if CTK_AVAILABLE:
                self.tabview.set("🖼️ 画像")
            
        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"画像抽出に失敗しました:\n{e}")
    
    def _update_images_display(self):
        """画像表示を更新 (v2: Canvasに画像描画)"""
        # プレースホルダーを削除
        self.images_canvas.delete("placeholder")

        # TODO: 実際の画像表示は素材シートで行う
        # Canvasには PDF画像 + 画像レイヤーハイライトを実装予定
        image_count = len(self.layer_result.image_layer.blocks) if self.layer_result and self.layer_result.image_layer else 0
        self._set_status(f"画像 {image_count}件を抽出しました")

    def _update_layer_stats(self):
        """レイヤー統計を更新 (v2: LayerAnalyzer SDK使用)"""
        if not self.layer_result:
            return

        try:
            from app.sdk.storyboard import LayerAnalyzer

            if self._layer_analyzer is None:
                self._layer_analyzer = LayerAnalyzer()

            self._layer_analyzer.set_layer_result(self.layer_result)
            stats = self._layer_analyzer.get_layer_stats()

            # テキストレイヤー統計
            text_stats_text = "テキスト: "
            text_parts = []
            if stats.text_layers.get("Bold", 0) > 0:
                text_parts.append(f"Bold {stats.text_layers['Bold']}")
            if stats.text_layers.get("Regular", 0) > 0:
                text_parts.append(f"Regular {stats.text_layers['Regular']}")
            if stats.text_layers.get("Light", 0) > 0:
                text_parts.append(f"Light {stats.text_layers['Light']}")

            if text_parts:
                text_stats_text += " / ".join(text_parts)
            else:
                text_stats_text += "0件"

            self.text_stats_label.configure(text=text_stats_text)

            # 画像レイヤー統計
            self.image_stats_label.configure(text=f"画像: {stats.image_layers}件")

        except Exception as e:
            print(f"⚠️ LayerAnalyzer error: {e}")

    def _update_material_sheet(self):
        """素材シートを更新 (v2: SheetGenerator SDK使用)"""
        if not self.layer_result:
            return

        try:
            from app.sdk.storyboard import SheetGenerator

            # 既存の行をクリア
            for widget in self.sheet_scroll.winfo_children():
                widget.destroy()

            # SheetGenerator初期化
            if self._sheet_generator is None:
                self._sheet_generator = SheetGenerator()

            # ページ画像取得 (サムネイル生成用)
            page_images = []
            if self._layer_separator and self.current_pdf_path:
                try:
                    from app.pipeline.storyboard.layer_separator import LayerSeparator
                    import fitz
                    doc = fitz.open(self.current_pdf_path)
                    for page_num in range(len(doc)):
                        page_img = self._layer_separator.render_page_as_image(self.current_pdf_path, page_num, scale=1.5)
                        if page_img:
                            page_images.append(page_img)
                    doc.close()
                except:
                    pass

            self._sheet_generator.set_data(self.layer_result, page_images)
            sheet_rows = self._sheet_generator.generate_sheet_data()

            # ヘッダー行を追加
            header_frame = ctk.CTkFrame(self.sheet_scroll, fg_color="#3A3A3A", height=30) if CTK_AVAILABLE else tk.Frame(self.sheet_scroll, height=30)
            header_frame.pack(fill="x", pady=(0, 2))
            header_frame.pack_propagate(False)

            headers = ["#", "サムネイル", "タイプ", "レイヤー", "テキスト"]
            widths = [40, 100, 70, 80, 400]

            for i, (header, width) in enumerate(zip(headers, widths)):
                label = ctk.CTkLabel(
                    header_frame,
                    text=header,
                    font=("Meiryo", 10, "bold"),
                    width=width
                ) if CTK_AVAILABLE else tk.Label(header_frame, text=header, font=("Meiryo", 10, "bold"), width=width)
                label.pack(side="left", padx=2)

            # データ行を追加
            for row_data in sheet_rows:
                self._create_material_sheet_row(row_data)

        except Exception as e:
            print(f"⚠️ Material sheet error: {e}")
            import traceback
            traceback.print_exc()

    def _create_material_sheet_row(self, row_data):
        """素材シート行を作成"""
        row_frame = ctk.CTkFrame(self.sheet_scroll, fg_color="#2D2D2D", height=70) if CTK_AVAILABLE else tk.Frame(self.sheet_scroll, height=70)
        row_frame.pack(fill="x", pady=1)
        row_frame.pack_propagate(False)

        # ID
        id_label = ctk.CTkLabel(
            row_frame,
            text=str(row_data.id),
            width=40,
            font=("Meiryo", 9)
        ) if CTK_AVAILABLE else tk.Label(row_frame, text=str(row_data.id), width=40, font=("Meiryo", 9))
        id_label.pack(side="left", padx=2)

        # サムネイル
        thumb_container = tk.Frame(row_frame, width=100, height=60, bg="gray30")
        thumb_container.pack(side="left", padx=2, pady=5)
        thumb_container.pack_propagate(False)

        if row_data.thumbnail:
            try:
                photo = ImageTk.PhotoImage(row_data.thumbnail)
                self._image_refs.append(photo)
                thumb_label = tk.Label(thumb_container, image=photo, bg="gray30")
                thumb_label.pack(expand=True)
            except:
                pass

        # タイプ
        type_label = ctk.CTkLabel(
            row_frame,
            text=row_data.item_type,
            width=70,
            font=("Meiryo", 9)
        ) if CTK_AVAILABLE else tk.Label(row_frame, text=row_data.item_type, width=70, font=("Meiryo", 9))
        type_label.pack(side="left", padx=2)

        # レイヤー
        layer_label = ctk.CTkLabel(
            row_frame,
            text=row_data.layer_name,
            width=80,
            font=("Meiryo", 9)
        ) if CTK_AVAILABLE else tk.Label(row_frame, text=row_data.layer_name, width=80, font=("Meiryo", 9))
        layer_label.pack(side="left", padx=2)

        # テキスト
        text_label = ctk.CTkLabel(
            row_frame,
            text=row_data.text[:50] + ("..." if len(row_data.text) > 50 else ""),
            width=400,
            font=("Meiryo", 9),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(row_frame, text=row_data.text[:50] + ("..." if len(row_data.text) > 50 else ""), width=400, font=("Meiryo", 9), anchor="w")
        text_label.pack(side="left", padx=2)

    def _export_excel(self):
        """Excelにエクスポート"""
        if not self.layer_result:
            messagebox.showwarning("警告", "エクスポートするデータがありません。先にレイヤーを抽出してください。")
            return
        
        output_path = filedialog.asksaveasfilename(
            title="Excelファイルを保存",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            initialfile=f"storyboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        
        if not output_path:
            return
        
        self._set_status("Excel出力中...")
        
        try:
            from app.pipeline.storyboard.storyboard_exporter import StoryboardExporter
            
            if self._exporter is None:
                self._exporter = StoryboardExporter()

            images = self.layer_result.image_layer.blocks if self.layer_result and self.layer_result.image_layer else []

            success = self._exporter.export_to_excel(
                paragraphs=self.paragraphs,
                images=images,
                output_path=output_path,
                title=Path(self.current_pdf_path).stem if self.current_pdf_path else "Storyboard"
            )
            
            if success:
                self._set_status(f"Excel出力完了: {Path(output_path).name}")
                messagebox.showinfo("完了", f"Excelファイルを保存しました:\n{output_path}")
            else:
                self._set_status("Excel出力失敗")
                
        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"Excel出力に失敗しました:\n{e}")
    
    def _export_pptx(self):
        """PowerPointにエクスポート"""
        if not self.layer_result:
            messagebox.showwarning("警告", "エクスポートするデータがありません。先にレイヤーを抽出してください。")
            return
        
        output_path = filedialog.asksaveasfilename(
            title="PowerPointファイルを保存",
            defaultextension=".pptx",
            filetypes=[("PowerPoint Files", "*.pptx")],
            initialfile=f"storyboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )
        
        if not output_path:
            return
        
        self._set_status("PowerPoint出力中...")
        
        try:
            from app.pipeline.storyboard.storyboard_exporter import StoryboardExporter
            
            if self._exporter is None:
                self._exporter = StoryboardExporter()

            images = self.layer_result.image_layer.blocks if self.layer_result and self.layer_result.image_layer else []

            success = self._exporter.export_to_pptx(
                paragraphs=self.paragraphs,
                images=images,
                output_path=output_path,
                title=Path(self.current_pdf_path).stem if self.current_pdf_path else "Storyboard"
            )
            
            if success:
                self._set_status(f"PowerPoint出力完了: {Path(output_path).name}")
                messagebox.showinfo("完了", f"PowerPointファイルを保存しました:\n{output_path}")
            else:
                self._set_status("PowerPoint出力失敗")
                
        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"PowerPoint出力に失敗しました:\n{e}")
    
    def _export_csv(self):
        """CSVにエクスポート (v2: LayoutExporter SDK使用)"""
        if not self.layer_result:
            messagebox.showwarning("警告", "エクスポートするデータがありません。先にレイヤーを抽出してください。")
            return

        output_path = filedialog.asksaveasfilename(
            title="CSVファイルを保存",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"storyboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not output_path:
            return

        self._set_status("CSV出力中...")

        try:
            from app.sdk.storyboard import LayoutExporter

            exporter = LayoutExporter(self.layer_result)
            success = exporter.to_csv(output_path)

            if success:
                self._set_status(f"CSV出力完了: {Path(output_path).name}")
                messagebox.showinfo("完了", f"CSVファイルを保存しました:\n{output_path}")
            else:
                self._set_status("CSV出力失敗")

        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"CSV出力に失敗しました:\n{e}")

    def _export_png(self):
        """PNGにエクスポート (v2: LayoutExporter SDK使用)"""
        if not self.layer_result:
            messagebox.showwarning("警告", "エクスポートするデータがありません。先にレイヤーを抽出してください。")
            return

        output_dir = filedialog.askdirectory(
            title="PNG画像の出力先フォルダを選択"
        )

        if not output_dir:
            return

        self._set_status("PNG出力中...")

        try:
            from app.sdk.storyboard import LayoutExporter

            # ページ画像を取得
            page_images = []
            if self._layer_separator and self.current_pdf_path:
                try:
                    import fitz
                    doc = fitz.open(self.current_pdf_path)
                    for page_num in range(len(doc)):
                        page_img = self._layer_separator.render_page_as_image(self.current_pdf_path, page_num, scale=1.5)
                        if page_img:
                            page_images.append(page_img)
                    doc.close()
                except:
                    pass

            exporter = LayoutExporter(self.layer_result, page_images)
            success = exporter.to_png(output_dir)

            if success:
                self._set_status(f"PNG出力完了: {output_dir}")
                messagebox.showinfo("完了", f"PNG画像を保存しました:\n{output_dir}")
            else:
                self._set_status("PNG出力失敗")

        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"PNG出力に失敗しました:\n{e}")

    def _run_batch_ocr(self):
        """一括OCR処理 (v2: GeminiOCREngine使用)"""
        print("🔥 [BatchOCR] Button clicked!")
        
        if not self.current_pdf_path:
            print("⚠️ [BatchOCR] No PDF selected")
            messagebox.showwarning("警告", "PDFを選択してください。")
            return
        
        print(f"📄 [BatchOCR] PDF path: {self.current_pdf_path}")
        self._set_status("🤖 一括OCR処理中... (Gemini Vision AI)", show_progress=True)
        self.batch_ocr_btn.configure(state="disabled")
        
        # バックグラウンドスレッドで実行
        print("🚀 [BatchOCR] Starting background thread...")
        thread = threading.Thread(target=self._do_batch_ocr, daemon=True)
        thread.start()
        print("✅ [BatchOCR] Thread started")

    def _do_batch_ocr(self):
        """MEKIKI同等: CloudOCREngine + HybridOCR補正"""
        try:
            import fitz  # PyMuPDF
            from app.core.engine_cloud import CloudOCREngine
            
            print("🚀 [BatchOCR] Starting MEKIKI-style OCR (CloudOCREngine)...")
            self.after(0, lambda: self._set_status("🔥 MEKIKI OCR 初期化中...", show_progress=True))
            
            # ★ MEKIKI同等: CloudOCREngine を使用
            ocr_engine = CloudOCREngine()
            
            # ★ HybridOCREngine（Gemini補正用）
            hybrid_engine = None
            try:
                from app.core.hybrid_ocr import HybridOCREngine
                hybrid_engine = HybridOCREngine()
                if hybrid_engine._is_initialized:
                    print("✅ [BatchOCR] HybridOCREngine initialized (Gemini correction enabled)")
                else:
                    hybrid_engine = None
                    print("⚠️ [BatchOCR] HybridOCR failed, using CloudOCR only")
            except Exception as e:
                print(f"⚠️ [BatchOCR] HybridOCR import failed: {e}")
            
            # PDFを開く
            doc = fitz.open(self.current_pdf_path)
            total_pages = len(doc)
            all_blocks = []
            self._batch_ocr_page_images = {}  # サムネイル用に画像を保持
            
            print(f"📄 [BatchOCR] Processing {total_pages} pages with CloudOCREngine...")
            
            for page_num in range(total_pages):
                # 進捗更新
                self.after(0, lambda p=page_num: self._set_status(
                    f"🔥 MEKIKI OCR... {p+1}/{total_pages}ページ", show_progress=True
                ))
                
                # ★ MEKIKI同等: 3x スケールで高品質レンダリング
                page = doc[page_num]
                mat = fitz.Matrix(3.0, 3.0)  # 3x scale for OCR quality (MEKIKI同等)
                pix = page.get_pixmap(matrix=mat)
                page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # OCR前処理（MEKIKI同等）
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(page_img)
                page_img = enhancer.enhance(1.3)  # コントラスト強調
                enhancer = ImageEnhance.Sharpness(page_img)
                page_img = enhancer.enhance(1.5)  # シャープネス強調
                
                print(f"🔍 [BatchOCR] Page {page_num+1}: {pix.width}x{pix.height} (3x scale)", flush=True)
                
                # サムネイル用に画像を保存
                self._batch_ocr_page_images[page_num] = page_img.copy()
                
                try:
                    # ★ CloudOCREngine でクラスタリング抽出（MEKIKI同等）
                    print(f"🚀 [BatchOCR] Page {page_num+1}: CloudOCREngine extracting...", flush=True)
                    clusters, raw_words = ocr_engine.extract_text(page_img)
                    
                    print(f"✅ [BatchOCR] Page {page_num+1}: {len(clusters)} clusters extracted", flush=True)
                    
                    for i, cluster in enumerate(clusters):
                        raw_text = cluster.get('text', '').strip()
                        
                        if len(raw_text) < 3:
                            continue
                        
                        # ★ HybridOCR補正は処理速度のため一時無効化
                        # 各クラスター×API呼び出し時間でブロックするため
                        # 必要な場合は後処理で一括補正を実装予定
                        # if hybrid_engine and len(raw_text) >= 20:
                        #     try:
                        #         corrected = hybrid_engine._call_gemini_correction(raw_text)
                        #         if corrected:
                        #             raw_text = corrected
                        #     except:
                        #         pass
                        
                        all_blocks.append({
                            "type": "text",
                            "text": raw_text,
                            "page_num": page_num,
                            "block_id": f"P{page_num+1}_{i+1:02d}",
                            "bbox": cluster.get('rect'),
                            "corrected": hybrid_engine is not None
                        })
                    
                    print(f"✅ [BatchOCR] Page {page_num+1}: {len([b for b in all_blocks if b['page_num']==page_num and b.get('type')=='text'])} text blocks added", flush=True)
                    
                    # ★ 画像抽出（PyMuPDF page.get_images()）
                    try:
                        images = page.get_images(full=True)
                        print(f"🖼️ [BatchOCR] Page {page_num+1}: {len(images)} embedded images found", flush=True)
                        
                        for img_idx, img_info in enumerate(images):
                            xref = img_info[0]
                            try:
                                base_img = doc.extract_image(xref)
                                img_bytes = base_img["image"]
                                img_ext = base_img["ext"]
                                
                                # PIL Imageに変換
                                pil_img = Image.open(io.BytesIO(img_bytes))
                                
                                # 画像の位置を取得（rect情報がない場合は推定）
                                # get_image_bbox() を使用して正確な位置を取得
                                try:
                                    img_bbox = page.get_image_bbox(img_info)
                                    # 3x スケールに変換
                                    scaled_bbox = [
                                        img_bbox.x0 * 3,
                                        img_bbox.y0 * 3,
                                        img_bbox.x1 * 3,
                                        img_bbox.y1 * 3
                                    ]
                                except:
                                    scaled_bbox = None
                                
                                all_blocks.append({
                                    "type": "image",
                                    "image": pil_img,
                                    "page_num": page_num,
                                    "block_id": f"IMG{page_num+1}_{img_idx+1:02d}",
                                    "bbox": scaled_bbox,
                                    "format": img_ext,
                                    "size": f"{pil_img.width}x{pil_img.height}"
                                })
                                print(f"   ✅ Image {img_idx+1}: {pil_img.width}x{pil_img.height} ({img_ext})", flush=True)
                                
                            except Exception as img_err:
                                print(f"   ⚠️ Image {img_idx+1} extraction failed: {img_err}", flush=True)
                    except Exception as img_list_err:
                        print(f"⚠️ [BatchOCR] Page {page_num+1} image list failed: {img_list_err}", flush=True)
                        
                except Exception as e:
                    print(f"⚠️ [BatchOCR] Page {page_num+1} failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            doc.close()
            
            print(f"📊 [BatchOCR] Complete: {len(all_blocks)} blocks extracted")
            
            # 結果を保存
            self._batch_ocr_blocks = all_blocks
            
            # GUIスレッドで更新
            self.after(0, self._on_batch_ocr_complete)
            
        except Exception as e:
            print(f"❌ [BatchOCR] Error: {e}")
            import traceback
            traceback.print_exc()
            self.after(0, lambda: self._set_status(f"❌ エラー: {e}"))
            self.after(0, lambda: self.batch_ocr_btn.configure(state="normal"))


    def _on_batch_ocr_complete(self):
        """一括OCR完了時のGUI更新"""
        blocks = getattr(self, '_batch_ocr_blocks', [])
        
        # 素材シートを更新
        self._update_material_sheet_with_blocks(blocks)
        
        # レイヤー統計更新
        self.text_stats_label.configure(text=f"テキスト: {len(blocks)}ブロック")
        
        # ボタン有効化
        self.batch_ocr_btn.configure(state="normal")
        self.export_excel_btn.configure(state="normal")
        self.export_pptx_btn.configure(state="normal")
        self.export_csv_btn.configure(state="normal")
        self.export_png_btn.configure(state="normal")
        
        self._set_status(f"✅ 一括OCR完了: {len(blocks)}ブロック抽出")

    def _update_material_sheet_with_blocks(self, blocks):
        """OCR抽出ブロックで素材シートを更新（テキスト+画像対応）"""
        # 既存の行をクリア（CTkFont destroy エラー対策）
        for widget in self.sheet_scroll.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass  # CTkFont attribute error を無視
        
        # サムネイル参照を保持（GC対策）
        self._sheet_thumbnails = {}
        
        if not blocks:
            placeholder = ctk.CTkLabel(
                self.sheet_scroll,
                text="OCRでブロックが検出されませんでした",
                text_color="gray"
            ) if CTK_AVAILABLE else tk.Label(self.sheet_scroll, text="OCRでブロックが検出されませんでした", fg="gray")
            placeholder.pack(pady=50)
            return
        
        # ソース画像（テキストサムネイル用）
        page_images = getattr(self, '_batch_ocr_page_images', {})
        
        # ===== サムネイル生成 =====
        thumb_h = 50
        for i, block in enumerate(blocks):
            thumb_photo = None
            block_type = block.get('type', 'text')
            
            if block_type == 'image':
                # 画像ブロック: 直接PIL Imageからサムネイル生成
                pil_img = block.get('image')
                if pil_img:
                    try:
                        img_copy = pil_img.copy()
                        img_copy.thumbnail((90, thumb_h), Image.Resampling.LANCZOS)
                        thumb_photo = ImageTk.PhotoImage(img_copy)
                    except Exception:
                        pass
            else:
                # テキストブロック: ページ画像からbbox切り出し
                bbox = block.get('bbox')
                page_idx = block.get('page_num', 0)
                
                # bboxが有効か確認（4要素以上で全てNoneでないこと）
                if bbox and len(bbox) >= 4 and all(v is not None for v in bbox[:4]) and page_idx in page_images:
                    try:
                        src_img = page_images[page_idx]
                        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
                        x1 = max(0, min(x1, src_img.width - 1))
                        y1 = max(0, min(y1, src_img.height - 1))
                        x2 = max(x1 + 1, min(x2, src_img.width))
                        y2 = max(y1 + 1, min(y2, src_img.height))
                        
                        cropped = src_img.crop((x1, y1, x2, y2))
                        if cropped.height > 0:
                            ratio = thumb_h / cropped.height
                            resized = cropped.resize((min(int(cropped.width * ratio), 90), thumb_h), Image.Resampling.LANCZOS)
                            thumb_photo = ImageTk.PhotoImage(resized)
                    except Exception:
                        pass
            
            self._sheet_thumbnails[i] = thumb_photo
        
        # ===== ヘッダー行 =====
        header_frame = ctk.CTkFrame(self.sheet_scroll, fg_color="#383838", height=30) if CTK_AVAILABLE else tk.Frame(self.sheet_scroll, height=30)
        header_frame.pack(fill="x", pady=(0, 2))
        header_frame.pack_propagate(False)
        
        for text, w in [("#", 40), ("P", 30), ("タイプ", 50), ("サムネイル", 100), ("内容", 0)]:
            label = ctk.CTkLabel(header_frame, text=text, width=w if w > 0 else None, font=("Meiryo", 10, "bold")) if CTK_AVAILABLE else tk.Label(header_frame, text=text, font=("Meiryo", 10, "bold"))
            label.pack(side="left", padx=5)
        
        # ===== データ行 =====
        for i, block in enumerate(blocks):
            block_type = block.get('type', 'text')
            bg = "#2B2B2B" if i % 2 == 0 else "#333333"
            row_frame = ctk.CTkFrame(self.sheet_scroll, fg_color=bg, height=60) if CTK_AVAILABLE else tk.Frame(self.sheet_scroll, height=60)
            row_frame.pack(fill="x", pady=1)
            row_frame.pack_propagate(False)
            
            # No
            ctk.CTkLabel(row_frame, text=str(i+1), width=40, font=("Meiryo", 9)).pack(side="left", padx=2) if CTK_AVAILABLE else tk.Label(row_frame, text=str(i+1), width=5).pack(side="left", padx=2)
            
            # ページ
            page_num = block.get('page_num', 0) + 1
            ctk.CTkLabel(row_frame, text=str(page_num), width=30, font=("Meiryo", 9)).pack(side="left", padx=2) if CTK_AVAILABLE else tk.Label(row_frame, text=str(page_num), width=3).pack(side="left", padx=2)
            
            # タイプ（アイコン）
            type_icon = "🖼️" if block_type == 'image' else "📝"
            type_color = "#FF9800" if block_type == 'image' else "#4CAF50"
            ctk.CTkLabel(row_frame, text=type_icon, width=50, font=("Meiryo", 14), text_color=type_color).pack(side="left", padx=2) if CTK_AVAILABLE else tk.Label(row_frame, text=type_icon, width=5).pack(side="left", padx=2)
            
            # サムネイル
            img_frame = ctk.CTkFrame(row_frame, fg_color="#1E1E1E", width=100, height=55) if CTK_AVAILABLE else tk.Frame(row_frame, width=100, height=55)
            img_frame.pack(side="left", padx=2)
            img_frame.pack_propagate(False)
            
            thumb = self._sheet_thumbnails.get(i)
            if thumb:
                lbl = tk.Label(img_frame, image=thumb, bg="#1E1E1E")
                lbl.image = thumb
                lbl.pack(expand=True)
            else:
                ctk.CTkLabel(img_frame, text="❌", font=("Meiryo", 14)).pack(expand=True) if CTK_AVAILABLE else tk.Label(img_frame, text="❌").pack(expand=True)
            
            # 内容（テキストまたは画像サイズ）
            txt_frame = ctk.CTkFrame(row_frame, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(row_frame)
            txt_frame.pack(side="left", fill="both", expand=True, padx=2)
            
            if block_type == 'image':
                # 画像ブロック: サイズ情報を表示
                size_info = block.get('size', 'N/A')
                fmt = block.get('format', 'unknown')
                content_text = f"画像: {size_info} ({fmt})"
                ctk.CTkLabel(txt_frame, text=content_text, font=("Meiryo", 10), text_color="#FF9800").pack(fill="both", expand=True, padx=5, pady=5) if CTK_AVAILABLE else tk.Label(txt_frame, text=content_text, fg="#FF9800").pack(fill="both", expand=True, padx=5, pady=5)
            else:
                # テキストブロック: テキスト内容を表示
                text_widget = tk.Text(txt_frame, bg=bg, fg="#E0E0E0", relief="flat", font=("Meiryo", 9), wrap="char", height=3)
                text_widget.pack(fill="both", expand=True)
                text_widget.insert("1.0", block.get('text', ''))
                text_widget.configure(state="disabled")


    # ===== ユーティリティ =====

    def _enable_buttons(self):
        """ボタンを有効化"""
        self.extract_text_btn.configure(state="normal")
        self.extract_image_btn.configure(state="normal")
        self.batch_ocr_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")

    def _set_status(self, message: str, show_progress: bool = False):
        """ステータスを設定（プログレスバー制御付き）- comparison_matrix流用"""
        # 両方のステータスラベルを更新
        self.status_label.configure(text=f"📌 {message}")
        if hasattr(self, 'bottom_status_label'):
            self.bottom_status_label.configure(text=f"📌 {message}")
        self.update_idletasks()
        print(f"[StoryboardExtractor] {message}")
        
        # プログレスバー制御
        if CTK_AVAILABLE and hasattr(self, 'progress_bar'):
            if show_progress:
                self.progress_bar.start()
            else:
                self.progress_bar.stop()
                self.progress_bar.set(0)

    # ============================================================
    # 選択機能 (SelectionMixin 流用 - comparison_matrix から直接コピー)
    # ============================================================

    def _toggle_edit_mode(self):
        """編集モード切り替え (comparison_matrix流用)"""
        self._edit_mode = not self._edit_mode
        
        if self._edit_mode:
            self.edit_btn.configure(fg_color="#22C55E", text="🖊️ 選択中...")
            self._set_status("🖊️ 編集モード: キャンバス上でドラッグして範囲選択")
            # キャンバスにイベントをバインド
            self._bind_selection_events(self.text_canvas)
            self._bind_selection_events(self.images_canvas)
        else:
            self.edit_btn.configure(fg_color="#6B7280", text="🖊️ 手動選択")
            self._set_status("編集モード終了")
            # イベントをアンバインド
            self._unbind_selection_events(self.text_canvas)
            self._unbind_selection_events(self.images_canvas)

    def _bind_selection_events(self, canvas):
        """選択イベントをバインド (comparison_matrix流用)"""
        canvas.bind("<ButtonPress-1>", lambda e: self._on_selection_start(e, canvas))
        canvas.bind("<B1-Motion>", lambda e: self._on_selection_drag(e, canvas))
        canvas.bind("<ButtonRelease-1>", lambda e: self._on_selection_end(e, canvas))
        # Motion/Leave は canvas作成時に既にバインド済み

    def _unbind_selection_events(self, canvas):
        """選択イベントをアンバインド (Motion/Leaveは保持)"""
        canvas.unbind("<ButtonPress-1>")
        canvas.unbind("<B1-Motion>")
        canvas.unbind("<ButtonRelease-1>")
        # Motion/Leave は保持（クロスヘアは常時表示）
        # クロスヘアは削除しない（編集モード終了後も座標表示は継続）

    # ============================================================
    # クロスヘア座標表示 (comparison_matrix から直接コピー)
    # ============================================================

    def _on_mouse_motion(self, event, canvas):
        """マウス移動時にクロスヘアと座標を表示 (comparison_matrix流用)"""
        if not self._crosshair_enabled:
            return
        
        # 画像がない場合はスキップ
        if not self._current_page_image:
            return
        
        # スクロール位置を考慮したキャンバス座標
        vx = canvas.canvasx(event.x)
        vy = canvas.canvasy(event.y)
        
        # Source座標を計算 (scale_factorを使用)
        scale_factor = 1.0
        if hasattr(canvas, '_pdf_image_info'):
            scale_factor = canvas._pdf_image_info.get('scale_factor', 1.0)
        
        sx = int(vx / scale_factor) if scale_factor > 0 else int(vx)
        sy = int(vy / scale_factor) if scale_factor > 0 else int(vy)
        
        # 古いクロスヘアを削除
        canvas.delete("crosshair")
        canvas.delete("coord_label")
        
        # スクロール領域を取得
        scrollregion = canvas.cget('scrollregion')
        if scrollregion:
            try:
                parts = scrollregion.split()
                max_x = float(parts[2]) if len(parts) >= 3 else canvas.winfo_width()
                max_y = float(parts[3]) if len(parts) >= 4 else canvas.winfo_height()
            except:
                max_x = canvas.winfo_width()
                max_y = canvas.winfo_height()
        else:
            max_x = canvas.winfo_width()
            max_y = canvas.winfo_height()
        
        # クロスヘア描画
        canvas.create_line(0, vy, max_x, vy, fill="#00FF00", width=1, dash=(2, 2), tags="crosshair")
        canvas.create_line(vx, 0, vx, max_y, fill="#00FF00", width=1, dash=(2, 2), tags="crosshair")
        
        # 座標ラベル
        source_type = "Text" if canvas == self.text_canvas else "Image"
        coord_text = f"{source_type} V({int(vx)},{int(vy)}) → S({sx},{sy})"
        
        # ラベル位置
        label_x = vx + 15
        label_y = vy - 15
        
        # 背景付きテキスト
        canvas.create_rectangle(
            label_x - 2, label_y - 10,
            label_x + len(coord_text) * 6 + 2, label_y + 12,
            fill="#1E1E1E", outline="#00FF00", tags="coord_label"
        )
        canvas.create_text(
            label_x, label_y,
            text=coord_text, fill="#00FF00", anchor="nw",
            font=("Consolas", 9), tags="coord_label"
        )
        
        self._last_crosshair_pos = (vx, vy)

    def _on_mouse_leave(self, event, canvas):
        """マウスがキャンバスから離れたらクロスヘアを消去 (comparison_matrix流用)"""
        canvas.delete("crosshair")
        canvas.delete("coord_label")
        self._last_crosshair_pos = None

    def _on_selection_start(self, event, canvas):
        """選択開始 (comparison_matrix流用)"""
        if not self._edit_mode:
            return
        
        # キャンバス座標に変換
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        self._selection_start = (x, y)
        
        # 既存の選択矩形を削除
        if self._selection_rect_id:
            canvas.delete(self._selection_rect_id)
        
        # 新しい選択矩形を作成
        self._selection_rect_id = canvas.create_rectangle(
            x, y, x, y,
            outline="#00FF00", width=2, dash=(4, 2),
            tags="selection_rect"
        )
        print(f"[Selection] Start at ({x}, {y})")

    def _on_selection_drag(self, event, canvas):
        """選択ドラッグ中 (comparison_matrix流用)"""
        if not self._edit_mode or not self._selection_start:
            return
        
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # 矩形を更新
        if self._selection_rect_id:
            canvas.coords(
                self._selection_rect_id,
                self._selection_start[0], self._selection_start[1],
                x, y
            )

    def _on_selection_end(self, event, canvas):
        """選択終了 → OCR → シート反映 (comparison_matrix流用)"""
        if not self._edit_mode or not self._selection_start:
            return
        
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # 選択範囲を取得
        x1, y1 = self._selection_start
        x2, y2 = x, y
        
        # 正規化（左上→右下）
        rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        
        # 最小サイズチェック
        if abs(x2 - x1) < 20 or abs(y2 - y1) < 20:
            print("[Selection] Too small, ignoring")
            if self._selection_rect_id:
                canvas.delete(self._selection_rect_id)
            self._selection_start = None
            return
        
        print(f"[Selection] End at rect: {rect}")
        
        # 選択矩形を確定表示に変更
        if self._selection_rect_id:
            canvas.itemconfig(self._selection_rect_id, outline="#FFFF00", dash=())
        
        self._selection_start = None
        
        # OCR実行 → シート反映
        self._extract_selection_to_sheet(canvas, rect)

    def _extract_selection_to_sheet(self, canvas, rect):
        """選択範囲からOCR → シート反映 (comparison_matrix流用)"""
        self._set_status("🔍 選択範囲をOCR処理中...")
        
        # 画像が存在するか確認
        if not self._current_page_image:
            self._set_status("⚠️ 画像が読み込まれていません")
            return
        
        # 座標変換情報を取得
        scale_factor = 1.0
        if hasattr(canvas, '_pdf_image_info'):
            scale_factor = canvas._pdf_image_info.get('scale_factor', 1.0)
        
        # 元画像座標に変換
        sx1 = int(rect[0] / scale_factor)
        sy1 = int(rect[1] / scale_factor)
        sx2 = int(rect[2] / scale_factor)
        sy2 = int(rect[3] / scale_factor)
        
        # クロップ
        try:
            cropped = self._current_page_image.crop((sx1, sy1, sx2, sy2))
            print(f"[Selection] Cropped: {cropped.size}")
        except Exception as e:
            print(f"[Selection] Crop failed: {e}")
            self._set_status(f"⚠️ クロップ失敗: {e}")
            return
        
        # バックグラウンドでOCR実行
        def do_ocr():
            try:
                # GeminiClient でOCR (comparison_matrix流用)
                from app.sdk.llm import GeminiClient
                
                client = GeminiClient(model="gemini-2.0-flash")
                if not client.model:
                    self.after(0, lambda: self._set_status("⚠️ Gemini初期化失敗"))
                    return
                
                prompt = """この画像に含まれるテキストを正確に抽出してください。

ルール:
1. 画像内のテキストをそのまま抽出（翻訳/解釈しない）
2. 改行は元のレイアウトを維持
3. 日本語・英語混在可
4. 説明文は不要、テキストのみ出力

出力:"""
                
                result = client.generate(prompt, images=[cropped])
                
                if result:
                    clean_text = result.strip()
                    print(f"[Selection OCR] ✅ {len(clean_text)} chars: {clean_text[:50]}...")
                    
                    # GUIスレッドでシート反映
                    self.after(0, lambda: self._add_selection_to_sheet(cropped, clean_text, rect))
                else:
                    self.after(0, lambda: self._set_status("⚠️ OCR結果が空"))
                    
            except Exception as e:
                print(f"[Selection OCR] ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self._set_status(f"⚠️ OCRエラー: {e}"))
        
        # バックグラウンド実行
        threading.Thread(target=do_ocr, daemon=True).start()

    def _add_selection_to_sheet(self, thumbnail_img, text, rect):
        """選択結果を素材シートに追加 (comparison_matrix流用)"""
        self._selection_counter += 1
        sel_id = f"SEL_{self._selection_counter:03d}"
        
        # 選択データを保存
        selection_data = {
            "id": sel_id,
            "text": text,
            "rect": rect,
            "thumbnail": thumbnail_img
        }
        self._selections.append(selection_data)
        
        # 素材シートに行を追加
        self._add_row_to_material_sheet(selection_data)
        
        self._set_status(f"✅ {sel_id} を素材シートに追加しました")
        print(f"[Selection] Added {sel_id}: {text[:30]}...")

    def _add_row_to_material_sheet(self, selection_data):
        """素材シートに行を追加 (comparison_matrix流用)"""
        if not hasattr(self, 'material_scroll_frame'):
            return
        
        row_frame = ctk.CTkFrame(
            self.material_scroll_frame,
            fg_color="#3A3A3A",
            height=60
        ) if CTK_AVAILABLE else tk.Frame(self.material_scroll_frame, bg="#3A3A3A", height=60)
        row_frame.pack(fill="x", padx=5, pady=2)
        row_frame.pack_propagate(False)
        
        # サムネイル
        try:
            thumb = selection_data["thumbnail"].copy()
            thumb.thumbnail((50, 50))
            photo = ImageTk.PhotoImage(thumb)
            self._image_refs.append(photo)
            
            thumb_label = ctk.CTkLabel(row_frame, image=photo, text="") if CTK_AVAILABLE else tk.Label(row_frame, image=photo)
            thumb_label.pack(side="left", padx=5)
        except:
            pass
        
        # ID
        id_label = ctk.CTkLabel(
            row_frame,
            text=selection_data["id"],
            font=("Meiryo", 10, "bold"),
            width=80
        ) if CTK_AVAILABLE else tk.Label(row_frame, text=selection_data["id"], font=("Meiryo", 10, "bold"), width=10)
        id_label.pack(side="left", padx=5)
        
        # テキスト
        text = selection_data["text"][:50]
        if len(selection_data["text"]) > 50:
            text += "..."
        text_label = ctk.CTkLabel(row_frame, text=text, anchor="w") if CTK_AVAILABLE else tk.Label(row_frame, text=text, anchor="w")
        text_label.pack(side="left", fill="x", expand=True, padx=5)


# スタンドアロン起動用
if __name__ == "__main__":
    if CTK_AVAILABLE:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
    
    # テスト起動
    root = ctk.CTk() if CTK_AVAILABLE else tk.Tk()
    root.withdraw()  # ルートは非表示
    
    app = StoryboardExtractor(root)
    app.mainloop()
