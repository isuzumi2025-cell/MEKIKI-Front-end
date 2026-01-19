"""
Advanced Comparison View - 高度な校正ワークスペース
AI-based page detection + Dynamic Clustering OCR + Editable Regions

Features:
- Overview Map (ページサムネイル)
- Dual-pane Page Detail View (Web/PDF並列表示)
- Editable regions with P-Seq-Sync codes
- Real-time text synchronization

Refactoring Plan (2026-01-13):
- B-004: 例外ハンドリング強化 ✅ 完了
- 将来: Mixin構造への段階的移行
  - comparison_mixins/display_mixin.py
  - comparison_mixins/ocr_mixin.py
  - comparison_mixins/edit_mixin.py
  - comparison_mixins/export_mixin.py
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
from app.pipeline.metadata_exporter import export_ocr_metadata


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

        # ★ 描画中フラグ（configureイベント干渉防止）
        self._display_in_progress: bool = False

        # FR-01: 画像表示モード ("cover" or "fit")
        self.display_mode: str = "cover"

        # 同期データ (初期化必須)
        self.sync_pairs: List = []
        
        # 別ウィンドウ参照 (初期化必須)
        self.comparison_window = None
        self.matrix_window = None
        
        # UI構築
        self._build_ui()
        
        # 初期データロード
        self.after(500, self._load_from_queue)

        # スマートリサイズ管理
        self._resize_job = None  # 統合リサイズジョブ
        self._last_canvas_size = {}  # キャンバスサイズキャッシュ {"web": (w,h), "pdf": (w,h)}
        self._image_cache = {}  # スケール済み画像キャッシュ {"web": {size: photo}, "pdf": {size: photo}}

    def _show_error(self, message: str, exception: Exception = None, show_traceback: bool = False):
        """統一エラー表示メソッド（B-004: 例外ハンドリング強化）"""
        # ステータスラベルに表示
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.configure(text=f"❌ {message}")

        # コンソールにログ出力
        print(f"[ERROR] {message}")
        if exception:
            print(f"  Details: {type(exception).__name__}: {exception}")

        # スタックトレース（デバッグ用）
        if show_traceback and exception:
            import traceback
            traceback.print_exc()

    def _show_warning(self, message: str):
        """統一警告表示メソッド"""
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.configure(text=f"⚠️ {message}")
        print(f"[WARNING] {message}")

    def _show_success(self, message: str):
        """統一成功表示メソッド"""
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.configure(text=f"✅ {message}")
        print(f"[SUCCESS] {message}")

    def _safe_status(self, text: str, force_update: bool = True):
        """安全なステータス更新 (UI + コンソール)"""
        try:
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.configure(text=text)
                if force_update:
                    self.update_idletasks()
        except Exception:
            pass
        print(f"[STATUS] {text}")

    def _build_ui(self):
        """UI構築"""
        # ヘッダー (タイトル削除 - サイドバーに機能集約 2026-01-12)
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # Sync Rate表示 (大きめに)
        self.sync_rate_display = ctk.CTkLabel(
            header,
            text="Sync: ---%",
            font=("Meiryo", 14, "bold"),
            text_color="#888888"
        )
        self.sync_rate_display.pack(side="left", padx=20)
        
        # ツールバー (サイドバーに移動したボタンは削除済み 2026-01-12)
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=10)
        
        # [MOVED TO SIDEBAR] OCR実行, Excel出力, 全文比較, 比較シート
        
        ctk.CTkButton(
            toolbar, text="🔗 Sync再計算", width=90, fg_color="#2196F3",
            command=self._recalculate_sync
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            toolbar, text="🧪 Simulate", width=80, fg_color="#673AB7",
            command=self._open_match_simulator
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            toolbar, text="✨ 類似検出", width=80, fg_color="#E91E63",
            command=lambda: self._open_region_editor('web')
        ).pack(side="left", padx=3)
        
        # 🗂️ メタデータ出力ボタン (Phase 2)
        ctk.CTkButton(
            toolbar, text="🗂️ メタ出力", width=80, fg_color="#FF9800",
            command=self._export_metadata
        ).pack(side="left", padx=3)
        
        # 編集モードボタン
        self.edit_mode_btn = ctk.CTkButton(
            toolbar, text="✏️ 編集", width=60, fg_color="#616161",
            command=self._toggle_edit_mode
        )
        self.edit_mode_btn.pack(side="left", padx=3)
        
        ctk.CTkButton(
            toolbar, text="⚖️ Matrix", width=70, fg_color="#673AB7",
            command=self._open_comparison_matrix
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            toolbar, text="↗️ 全画面", width=70, fg_color="#616161",
            command=self._open_fullscreen
        ).pack(side="left", padx=3)
        
        # === メインコンテンツ (上下分割) ===
        main_paned = tk.PanedWindow(self, orient="vertical", sashwidth=5, bg="#444444")
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 上部: Source Canvas（P1: 左パネル削除 → フル幅使用）
        top_frame = ctk.CTkFrame(main_paned, fg_color="#2B2B2B")
        main_paned.add(top_frame, height=400)
        
        # ★ P1: 左パネル削除 - center_panelのみでフル幅を使用
        # 中央パネル: Dual Page Detail (フル幅)
        center_panel = ctk.CTkFrame(top_frame, fg_color="#2D2D2D")
        center_panel.pack(fill="both", expand=True, padx=2, pady=2)
        
        self._build_center_panel(center_panel)
        
        # 右パネル: Sync Text Panel (削除済み - Phase 5 Issue 4)
        # right_panel = ctk.CTkFrame(top_frame, fg_color="#2D2D2D", width=280)
        # right_panel.pack(side="right", fill="y", padx=2, pady=2)
        # right_panel.pack_propagate(False)
        # self._build_right_panel(right_panel)
        
        # ダミー属性 (互換性のため)
        self.selected_info = ctk.CTkLabel(top_frame, text="")
        self.web_text_box = ctk.CTkTextbox(top_frame, height=1)
        self.pdf_text_box = ctk.CTkTextbox(top_frame, height=1)
        self.diff_text_box = ctk.CTkTextbox(top_frame, height=1)
        self.similarity_label = ctk.CTkLabel(top_frame, text="")
        self.edit_mode_var = ctk.BooleanVar(value=False)

        
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
        """左パネル: 軽量化済み（T1: サイトマップボタン・Area List削除）"""
        self.primary_source = "web"  # Default, synced with Source tab
        
        # ★ T1: 左パネルを空にする（将来の拡張用にコンテナのみ残す）
        placeholder_frame = ctk.CTkFrame(parent, fg_color="#2A2A2A", corner_radius=8)
        placeholder_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            placeholder_frame,
            text="📊 比較マトリクス\nハイブリッドOCR実行後に\n結果が表示されます",
            font=("Meiryo", 10),
            text_color="gray",
            justify="center"
        ).pack(expand=True, pady=50)
    
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
        
        # Dual View (Tabs) as per single-face request
        self.view_tabs = ctk.CTkTabview(parent, command=self._on_source_tab_change)
        self.view_tabs.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.view_tabs.add("Web Source")
        self.view_tabs.add("PDF Source")
        
        # Web Tab
        web_frame = self.view_tabs.tab("Web Source")
        
        web_header = ctk.CTkFrame(web_frame, fg_color="#383838", height=30)
        web_header.pack(fill="x")
        web_header.pack_propagate(False)
        
        ctk.CTkLabel(
            web_header, text="🌐 Web Source", font=("Meiryo", 10, "bold")
        ).pack(side="left", padx=10, pady=5)

        # FR-01: 表示モード切替ボタン
        self.display_mode_btn = ctk.CTkButton(
            web_header, text="[Cover]", width=60, height=22, fg_color="#555555",
            hover_color="#666666", command=self._toggle_display_mode
        )
        self.display_mode_btn.pack(side="right", padx=5, pady=4)

        ctk.CTkButton(
            web_header, text="🖊️編集", width=50, height=22, fg_color="#4CAF50",
            command=lambda: self._open_region_editor("web")
        ).pack(side="right", padx=5, pady=4)
        
        web_canvas_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        web_canvas_frame.pack(fill="both", expand=True)  # 余白なし
        
        self.web_canvas = tk.Canvas(web_canvas_frame, bg="#1E1E1E", highlightthickness=0)
        web_scrollbar = ttk.Scrollbar(web_canvas_frame, orient="vertical", command=self.web_canvas.yview)
        self.web_canvas.configure(yscrollcommand=web_scrollbar.set)
        web_scrollbar.pack(side="right", fill="y")
        self.web_canvas.pack(side="left", fill="both", expand=True)
        self.web_canvas.bind("<MouseWheel>", lambda e: self.web_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.web_canvas.bind("<Button-3>", lambda e: self._on_canvas_right_click(e, "web"))
        
        # PDF Tab
        pdf_frame = self.view_tabs.tab("PDF Source")
        
        pdf_header = ctk.CTkFrame(pdf_frame, fg_color="#383838", height=30)
        pdf_header.pack(fill="x")
        pdf_header.pack_propagate(False)
        
        ctk.CTkLabel(
            pdf_header, text="📄 PDF Source", font=("Meiryo", 10, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        ctk.CTkButton(
            pdf_header, text="🖊️編集", width=50, height=22, fg_color="#4CAF50",
            command=lambda: self._open_region_editor("pdf")
        ).pack(side="right", padx=10, pady=4)
        
        pdf_nav_frame = ctk.CTkFrame(pdf_header, fg_color="transparent")
        pdf_nav_frame.pack(side="right", padx=5)
        ctk.CTkButton(pdf_nav_frame, text="◀", width=25, height=22, command=self._prev_pdf_page).pack(side="left", padx=1)
        self.pdf_page_label = ctk.CTkLabel(pdf_nav_frame, text="1/1", font=("Meiryo", 9), width=40)
        self.pdf_page_label.pack(side="left", padx=2)
        ctk.CTkButton(pdf_nav_frame, text="▶", width=25, height=22, command=self._next_pdf_page).pack(side="left", padx=1)
        
        pdf_canvas_frame = ctk.CTkFrame(pdf_frame, fg_color="transparent")
        pdf_canvas_frame.pack(fill="both", expand=True)  # 余白なし
        
        self.pdf_canvas = tk.Canvas(pdf_canvas_frame, bg="#1E1E1E", highlightthickness=0)
        pdf_scrollbar = ttk.Scrollbar(pdf_canvas_frame, orient="vertical", command=self.pdf_canvas.yview)
        self.pdf_canvas.configure(yscrollcommand=pdf_scrollbar.set)
        pdf_scrollbar.pack(side="right", fill="y")
        self.pdf_canvas.pack(side="left", fill="both", expand=True)
        self.pdf_canvas.bind("<MouseWheel>", lambda e: self.pdf_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # スマートリサイズ：統合ハンドラにバインド
        self.web_canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e, "web"))
        self.pdf_canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e, "pdf"))

        
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
        """下部スプレッドシートパネル構築 (Component化)"""
        from app.gui.panels.spreadsheet_panel import SpreadsheetPanel
        self.spreadsheet_panel = SpreadsheetPanel(parent, on_row_select=self._on_spreadsheet_row_select)
        self.spreadsheet_panel.pack(fill="both", expand=True)
    
    def _on_spreadsheet_row_select(self, web_id: str, pdf_id: str, pair):
        """Spreadsheet行選択時: Source領域をハイライト"""
        print(f"[Source Sync] Highlighting: Web={web_id}, PDF={pdf_id}")

        # Web側の領域を探してハイライト
        web_region = None
        for r in self.web_regions:
            if r.area_code == web_id:
                web_region = r
                break

        # PDF側の領域を探してハイライト
        pdf_region = None
        for r in self.pdf_regions:
            if r.area_code == pdf_id:
                pdf_region = r
                break

        # Canvasでハイライト表示
        self._highlight_region_on_canvas(self.web_canvas, web_region, "#FF6F00")
        self._highlight_region_on_canvas(self.pdf_canvas, pdf_region, "#2196F3")
        
        # テキストボックスにも表示
        if web_region and hasattr(self, 'web_text_box'):
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", f"[{web_id}]\n{web_region.text}")
        
        if pdf_region and hasattr(self, 'pdf_text_box'):
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", f"[{pdf_id}]\n{pdf_region.text}")
    
    def _highlight_region_on_canvas(self, canvas, region, color: str):
        """Canvas上で指定領域をハイライト表示 + スクロール"""
        if not region or not hasattr(region, 'rect'):
            return

        # 既存のハイライトを削除
        canvas.delete("highlight")

        # 座標を取得
        x1, y1, x2, y2 = region.rect

        # ★ B3: CanvasTransform経由で座標変換
        from app.gui.sdk.coord_transform import get_canvas_transform
        transform = get_canvas_transform(canvas)
        sx1, sy1, sx2, sy2 = transform.src_rect_to_view(x1, y1, x2, y2)

        # ハイライト矩形を描画 (太い枠線 + 半透明背景)
        canvas.create_rectangle(
            sx1, sy1, sx2, sy2,
            outline=color, width=4,
            tags="highlight"
        )

        # 領域が見えるようにスクロール
        scrollregion = canvas.cget('scrollregion')
        if scrollregion:
            try:
                # scrollregionは "x1 y1 x2 y2" 形式の文字列
                parts = scrollregion.split()
                total_height = float(parts[3]) if len(parts) >= 4 else 1
                if total_height > 0:
                    # 領域の中央が見えるようにスクロール
                    center_y = (sy1 + sy2) / 2
                    scroll_pos = max(0, min(1, (center_y - 100) / total_height))
                    canvas.yview_moveto(scroll_pos)
            except Exception as e:
                print(f"[Scroll] Error: {e}")


    
    def _safe_window_exists(self, attr_name: str) -> bool:
        """ウィンドウ参照が有効か安全にチェック"""
        try:
            win = getattr(self, attr_name, None)
            return win is not None and win.winfo_exists()
        except Exception:
            # TclError など破棄済みウィンドウへのアクセス
            setattr(self, attr_name, None)  # 参照をクリア
            return False
    
    def _refresh_inline_spreadsheet(self):
        """スプレッドシートの表示を更新"""
        # sync_pairs が未初期化の場合は空リストで初期化
        if not hasattr(self, 'sync_pairs'):
            self.sync_pairs = []

        # DEBUG: Log the state before calling update_data
        web_img = getattr(self, 'web_image', None)
        pdf_img = getattr(self, 'pdf_image', None)
        print(f"[_refresh_inline_spreadsheet] web_image={web_img.size if web_img else 'None'}, pdf_image={pdf_img.size if pdf_img else 'None'}")
        print(f"[_refresh_inline_spreadsheet] sync_pairs={len(self.sync_pairs)}, web_regions={len(getattr(self, 'web_regions', []))}, pdf_regions={len(getattr(self, 'pdf_regions', []))}")

        if hasattr(self, 'spreadsheet_panel'):
            try:
                self.spreadsheet_panel.update_data(
                    self.sync_pairs,
                    self.web_regions,
                    self.pdf_regions,
                    web_img,
                    pdf_img
                )
            except Exception as e:
                print(f"[SpreadsheetPanel] Error: {e}")
                import traceback
                traceback.print_exc()
            
        # 別ウィンドウも同期 (安全なチェック)
        if self._safe_window_exists('comparison_window'):
            try:
                self.comparison_window.load_data(
                    self.web_regions, 
                    self.pdf_regions,
                    getattr(self, 'web_image', None),
                    getattr(self, 'pdf_image', None),
                    self.sync_pairs
                )
            except Exception as e:
                print(f"[SyncWindow] Error: {e}")
                
        # Matrixウィンドウも同期 (安全なチェック)
        if self._safe_window_exists('matrix_window'):
            try:
                w_txt = self.web_text_box.get("1.0", "end") if hasattr(self, 'web_text_box') else ""
                p_txt = self.pdf_text_box.get("1.0", "end") if hasattr(self, 'pdf_text_box') else ""
                
                self.matrix_window.set_web_data(getattr(self, 'web_image', None), w_txt)
                self.matrix_window.set_pdf_data(getattr(self, 'pdf_image', None), p_txt)
            except Exception as e:
                print(f"[SyncMatrix] Error: {e}")
    
    def _on_canvas_configure(self, event, source: str):
        """
        スマートリサイズハンドラ（統合版）
        - サイズ変化を検知して必要な場合のみ再描画
        - 300msのデバウンスでリサイズ完了を待機
        - キャッシュで同一サイズの再計算を回避
        """
        # 描画中はスキップ
        if getattr(self, '_display_in_progress', False):
            return

        # 最小サイズチェック
        if event.width < 50 or event.height < 50:
            return

        # サイズ変化チェック（10px以上の変化のみ処理）
        current_size = (event.width, event.height)
        last_size = self._last_canvas_size.get(source, (0, 0))
        if abs(current_size[0] - last_size[0]) < 10 and abs(current_size[1] - last_size[1]) < 10:
            return

        # 前回のジョブをキャンセル
        if self._resize_job:
            self.after_cancel(self._resize_job)

        # 300ms後に再描画（リサイズ完了を待機）
        def _smart_redisplay():
            self._resize_job = None
            self._execute_smart_resize()

        self._resize_job = self.after(300, _smart_redisplay)

    def _execute_smart_resize(self):
        """実際のリサイズ処理を実行"""
        try:
            self._display_in_progress = True
            redraw_needed = False

            # Web画像の更新チェック
            if hasattr(self, 'web_canvas') and self.web_image:
                canvas = self.web_canvas
                new_size = (canvas.winfo_width(), canvas.winfo_height())
                old_size = self._last_canvas_size.get("web", (0, 0))

                if new_size != old_size and new_size[0] > 50:
                    self._last_canvas_size["web"] = new_size
                    self._display_image_smart(canvas, self.web_image, "web")
                    redraw_needed = True

            # PDF画像の更新チェック
            if hasattr(self, 'pdf_canvas') and self.pdf_image:
                canvas = self.pdf_canvas
                new_size = (canvas.winfo_width(), canvas.winfo_height())
                old_size = self._last_canvas_size.get("pdf", (0, 0))

                if new_size != old_size and new_size[0] > 50:
                    self._last_canvas_size["pdf"] = new_size
                    self._display_image_smart(canvas, self.pdf_image, "pdf")
                    redraw_needed = True

            # 領域オーバーレイは1回だけ再描画
            if redraw_needed:
                self._redraw_regions()

        except Exception as e:
            print(f"[SmartResize] Error: {e}")
        finally:
            self._display_in_progress = False

    def _display_image_smart(self, canvas, image, source: str):
        """
        スマート画像表示（キャッシュ活用）
        - 同一サイズならキャッシュから取得
        - キャッシュは最大3エントリで自動クリーンアップ
        """
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            return

        # キャッシュキー生成（サイズ＋モード）
        cache_key = (canvas_width, canvas_height, self.display_mode)

        # キャッシュ確認
        if source not in self._image_cache:
            self._image_cache[source] = {}

        cache = self._image_cache[source]

        if cache_key in cache:
            # キャッシュヒット：PhotoImageを再利用
            cached = cache[cache_key]
            canvas.delete("image")
            canvas.create_image(-cached["offset_x"], -cached["offset_y"],
                              anchor="nw", image=cached["photo"], tags="image")
            canvas.tag_lower("image")
            canvas.image = cached["photo"]
            canvas.scale_x = cached["scale"]
            canvas.scale_y = cached["scale"]
            canvas.offset_x = cached["offset_x"]
            canvas.offset_y = cached["offset_y"]

            if self.display_mode == "cover":
                canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
            else:
                canvas.configure(scrollregion=(0, 0, cached["width"], cached["height"]))
            return

        # キャッシュミス：新規生成
        self._display_image(canvas, image)

        # キャッシュに保存（最大3エントリ）
        if len(cache) >= 3:
            oldest_key = next(iter(cache))
            del cache[oldest_key]

        cache[cache_key] = {
            "photo": canvas.image,
            "scale": canvas.scale_x,
            "offset_x": canvas.offset_x,
            "offset_y": canvas.offset_y,
            "width": int(image.width * canvas.scale_x),
            "height": int(image.height * canvas.scale_y)
        }

    def _clear_image_cache(self, source: str = None):
        """画像キャッシュをクリア（画像変更時に呼び出す）"""
        if source:
            self._image_cache[source] = {}
        else:
            self._image_cache = {}


    # ===== ページナビゲーション =====
    
    def _prev_page(self):
        """前ページ（Web）"""
        if hasattr(self, 'web_pages') and len(self.web_pages) > 1:
            # Webページモード
            idx = getattr(self, 'current_web_page_idx', 0)
            if idx > 0:
                self._select_web_page(idx - 1)
        elif self.current_page > 1:
            # ページ領域モード
            self.current_page -= 1
            self._display_current_page()
    
    def _next_page(self):
        """次ページ（Web）"""
        if hasattr(self, 'web_pages') and len(self.web_pages) > 1:
            # Webページモード
            idx = getattr(self, 'current_web_page_idx', 0)
            if idx < len(self.web_pages) - 1:
                self._select_web_page(idx + 1)
        elif self.current_page < len(getattr(self, 'page_regions', [])):
            # ページ領域モード
            self.current_page += 1
            self._display_current_page()
    
    def _display_current_page(self):
        """現在ページを表示（ページ領域モード）"""
        # ラベル更新
        total_pages = len(getattr(self, 'page_regions', [])) or 1
        self.page_label.configure(
            text=f"Page {self.current_page} / {total_pages}"
        )
        
        # ★ T2: ページ領域にスクロール
        if hasattr(self, 'page_regions') and self.page_regions:
            idx = self.current_page - 1
            if 0 <= idx < len(self.page_regions):
                y_start, y_end = self.page_regions[idx]
                # 対象キャンバスを取得
                target_canvas = self.web_canvas if self.primary_source == "web" else self.pdf_canvas
                target_image = self.web_image if self.primary_source == "web" else self.pdf_image
                
                if target_canvas and target_image:
                    # スケール取得
                    from app.gui.sdk.coord_transform import get_canvas_transform
                    transform = get_canvas_transform(target_canvas)
                    
                    # スクロール位置計算
                    scrollregion = target_canvas.cget('scrollregion')
                    if scrollregion:
                        parts = scrollregion.split()
                        total_height = float(parts[3]) if len(parts) >= 4 else 1
                        if total_height > 0:
                            _, vy_start = transform.src_to_view(0, y_start)
                            scroll_pos = max(0, min(1, vy_start / total_height))
                            target_canvas.yview_moveto(scroll_pos)
                            print(f"[_display_current_page] Scrolled to page {self.current_page}, y={y_start}")
    
    def _on_source_tab_change(self):
        """Sourceタブ切り替え時の処理（Overview廃止済み）"""
        current_tab = self.view_tabs.get()
        if current_tab == "Web Source":
            self.primary_source = "web"
            # Web画像を再表示
            if hasattr(self, 'web_image') and self.web_image and hasattr(self, 'web_canvas'):
                self.after(100, lambda: self._display_image(self.web_canvas, self.web_image))
        elif current_tab == "PDF Source":
            self.primary_source = "pdf"
            # PDF画像を再表示（複数回遅延呼び出しで確実に表示）
            if hasattr(self, 'pdf_image') and self.pdf_image and hasattr(self, 'pdf_canvas'):
                print(f"[_on_source_tab_change] Displaying PDF image: {self.pdf_image.size}")
                # 即座に1回目
                self._display_image(self.pdf_canvas, self.pdf_image)
                # 200ms後に2回目（レイアウト完了後）
                self.after(200, lambda: self._display_image(self.pdf_canvas, self.pdf_image))
                # 500ms後に3回目（確実に表示）
                self.after(500, lambda: self._display_image(self.pdf_canvas, self.pdf_image))
    
    def _open_sitemap_viewer(self):
        """サイトマップビューワーウィンドウを開く"""
        try:
            from app.gui.windows.sitemap_viewer import SitemapViewerWindow
            
            # ウェブページデータを渡して開く
            web_pages_data = getattr(self, 'web_pages', [])
            window = SitemapViewerWindow(
                self,
                pages=web_pages_data,
                title="サイトマップビューワー"
            )
            window.focus_force()
            print("[SitemapViewer] ウィンドウを開きました")
        except Exception as e:
            print(f"[SitemapViewer] エラー: {e}")
            self.status_label.configure(text=f"⚠️ サイトマップビューワーを開けません: {e}")
    
    def _prev_pdf_page(self):
        """前のPDFページ（★P2修正）"""
        print(f"[_prev_pdf_page] Called. groups={len(getattr(self, 'pdf_stitched_groups', []))}, current_idx={getattr(self, 'current_pdf_group_idx', -1)}")
        
        if hasattr(self, 'pdf_stitched_groups') and self.pdf_stitched_groups:
            if not hasattr(self, 'current_pdf_group_idx'):
                self.current_pdf_group_idx = 0
            if self.current_pdf_group_idx > 0:
                self.current_pdf_group_idx -= 1
                print(f"[_prev_pdf_page] Navigating to group {self.current_pdf_group_idx}")
                self._display_pdf_group()
            else:
                print(f"[_prev_pdf_page] Already at first group")
        elif hasattr(self, 'pdf_pages_list') and self.pdf_pages_list:
            idx = getattr(self, 'current_pdf_idx', 0)
            if idx > 0:
                self.current_pdf_idx = idx - 1
                self._display_single_pdf_page()
        else:
            print(f"[_prev_pdf_page] No PDF data available")
    
    def _next_pdf_page(self):
        """次のPDFページ（★P2修正）"""
        print(f"[_next_pdf_page] Called. groups={len(getattr(self, 'pdf_stitched_groups', []))}, current_idx={getattr(self, 'current_pdf_group_idx', -1)}")
        
        if hasattr(self, 'pdf_stitched_groups') and self.pdf_stitched_groups:
            if not hasattr(self, 'current_pdf_group_idx'):
                self.current_pdf_group_idx = 0
            if self.current_pdf_group_idx < len(self.pdf_stitched_groups) - 1:
                self.current_pdf_group_idx += 1
                print(f"[_next_pdf_page] Navigating to group {self.current_pdf_group_idx}")
                self._display_pdf_group()
            else:
                print(f"[_next_pdf_page] Already at last group")
        elif hasattr(self, 'pdf_pages_list') and self.pdf_pages_list:
            idx = getattr(self, 'current_pdf_idx', 0)
            if idx < len(self.pdf_pages_list) - 1:
                self.current_pdf_idx = idx + 1
                self._display_single_pdf_page()
        else:
            print(f"[_next_pdf_page] No PDF data available")
    
    def _display_single_pdf_page(self):
        """単一PDFページを表示（フォールバック用）"""
        if not hasattr(self, 'pdf_pages_list') or not self.pdf_pages_list:
            return
        idx = getattr(self, 'current_pdf_idx', 0)
        if 0 <= idx < len(self.pdf_pages_list):
            page = self.pdf_pages_list[idx]
            self.pdf_image = page.get('image')
            if self.pdf_image:
                self._clear_image_cache("pdf")
                self._display_image(self.pdf_canvas, self.pdf_image)
                self.pdf_page_label.configure(text=f"{idx+1}/{len(self.pdf_pages_list)}")
                print(f"[_display_single_pdf_page] Showing page {idx+1}")
                
                # ★ ページ切り替え時に既存のリージョン・テキストをクリア
                self.pdf_regions = []
                if hasattr(self, 'pdf_text_box'):
                    self.pdf_text_box.delete("1.0", "end")
                self._redraw_regions()
    
    def _display_pdf_group(self):
        """現在のPDFグループを表示"""
        if not hasattr(self, 'pdf_stitched_groups') or not self.pdf_stitched_groups:
            return
        
        idx = getattr(self, 'current_pdf_group_idx', 0)
        if 0 <= idx < len(self.pdf_stitched_groups):
            group = self.pdf_stitched_groups[idx]
            self.pdf_image = group['image']
            self._clear_image_cache("pdf")  # 新画像読み込み時はキャッシュクリア
            self._display_image(self.pdf_canvas, self.pdf_image)
            
            # 遅延再描画 (キャンバスがレイアウトされた後)
            self.after(200, lambda: self._display_image(self.pdf_canvas, self.pdf_image))
            
            # ラベル更新
            self.pdf_page_label.configure(
                text=f"{group['page_range']}/{len(getattr(self, 'pdf_pages_list', []))}"
            )
            
            # ★ ページ切り替え時に既存のリージョン・テキストをクリア
            self.pdf_regions = []
            if hasattr(self, 'pdf_text_box'):
                self.pdf_text_box.delete("1.0", "end")
            self._redraw_regions()
    
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
            self._clear_image_cache("web")  # 新画像読み込み時はキャッシュクリア
            print(f"[_load_from_queue] ⭐ Web画像ロード: size={self.web_image.size}, mode={self.web_image.mode}")
            self._display_image(self.web_canvas, self.web_image)
            
            # 遅延再描画 (キャンバスがレイアウトされた後)
            self.after(200, lambda: self._display_image(self.web_canvas, self.web_image))
            
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
                self._clear_image_cache("pdf")  # 新画像読み込み時はキャッシュクリア
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
        try:
            if not images:
                return Image.new('RGB', (100, 100), (30, 30, 30))

            # 有効な画像のみフィルタリング
            valid_images = [img for img in images if img and hasattr(img, 'width') and img.width > 0]
            if not valid_images:
                self._show_warning("有効な画像がありません")
                return Image.new('RGB', (100, 100), (30, 30, 30))

            # 最大幅に合わせる
            max_width = max(img.width for img in valid_images)
            total_height = sum(img.height for img in valid_images)

            # サイズ制限チェック（メモリ保護）
            if total_height > 100000:
                self._show_warning(f"画像が大きすぎます（高さ: {total_height}px）。最初の10ページのみ連結します。")
                valid_images = valid_images[:10]
                total_height = sum(img.height for img in valid_images)

            # 連結画像を作成
            stitched = Image.new('RGB', (max_width, total_height), (30, 30, 30))
            y_offset = 0

            for img in valid_images:
                # 幅を統一
                if img.width != max_width:
                    ratio = max_width / img.width
                    new_height = max(int(img.height * ratio), 1)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                stitched.paste(img, (0, y_offset))
                y_offset += img.height

            return stitched

        except MemoryError as e:
            self._show_error("メモリ不足: 画像サイズを縮小してください", e)
            return Image.new('RGB', (100, 100), (30, 30, 30))
        except Exception as e:
            self._show_error("画像連結エラー", e, show_traceback=True)
            return Image.new('RGB', (100, 100), (30, 30, 30))
    
    def _on_overview_select(self, idx: int, region: Optional[Tuple[int, int]]):
        """【OverviewPanel Callack】ページ選択時の処理"""
        print(f"[Overview] Selected Page {idx+1}")
        
        # 1. Multi-Page Mode (Web Crawl Results)
        if hasattr(self, 'web_pages') and len(self.web_pages) > 1:
            self._select_web_page(idx)
            return

        # 2. Single Page Region Mode
        if region:
            y1, y2 = region
            # スクロール制御 (Web/PDF連動)
            target_canvas = self.web_canvas if self.primary_source == "web" else self.pdf_canvas
            
            if hasattr(target_canvas, 'scale_y') and hasattr(self, 'web_image') and self.web_image:
                # 座標変換 (Image -> Canvas)
                # ScrollViewは 0.0 - 1.0
                full_h = self.web_image.height * target_canvas.scale_y
                if full_h > 0:
                    start_pos = (y1 * target_canvas.scale_y) / full_h
                    target_canvas.yview_moveto(start_pos)
                    
                    # Status Update
                    self.status_label.configure(text=f"📄 Page {idx+1} にジャンプしました")
                    
                    # Store current page index logic
                    self.current_page = idx + 1
                    if hasattr(self, 'page_label'):
                         self.page_label.configure(text=f"Page {idx+1} / {len(self.page_regions)}")

    def _generate_page_selector(self):
        """ページサムネイル更新 (OverviewPanelへ委譲)"""
        # Componentがなければスキップ
        if not hasattr(self, 'overview_panel'):
            return

        # 1. Multi-page Mode (e.g. Sitemap Crawl)
        if hasattr(self, 'web_pages') and len(self.web_pages) > 1:
            self.overview_panel.set_pages(self.web_pages)
            return

        # 2. Single Split Mode (OCR Page Detection)
        target_image = self.web_image if self.primary_source == "web" else self.pdf_image
        
        if target_image:
            # ページ領域がなければ全体を1ページとして扱う
            regions = self.page_regions if hasattr(self, 'page_regions') and self.page_regions else [(0, target_image.height)]
            self.overview_panel.set_regions(target_image, regions)
        else:
            # Clear or Placeholder
            pass
    
    def _select_web_page(self, idx: int):
        """Webページを選択"""
        if not hasattr(self, 'web_pages') or idx >= len(self.web_pages):
            return

        self.current_web_page_idx = idx
        self.web_image = self.web_pages[idx]['image']
        self._clear_image_cache("web")  # 新画像読み込み時はキャッシュクリア
        self._display_image(self.web_canvas, self.web_image)
        
        # 遅延再描画 (キャンバスがレイアウトされた後)
        self.after(200, lambda: self._display_image(self.web_canvas, self.web_image))
        
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
        try:
            # ★ 描画中フラグを設定（configureイベント干渉防止）
            self._display_in_progress = True

            if not image or not hasattr(image, 'width') or image.width == 0 or image.height == 0:
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

            # FR-01: キャンバス高さも取得
            canvas_height = canvas.winfo_height()
            if canvas_height <= 1:
                parent = canvas.master
                if parent:
                    canvas_height = parent.winfo_height()
            if canvas_height <= 1:
                canvas_height = max(self.winfo_height() - 200, 300)
            canvas_height = max(canvas_height, 300)

            print(f"[_display_image] canvas={canvas_width}x{canvas_height}, image={image.size}, mode={self.display_mode}")

            # FR-01: Cover/Fit モードに応じたスケーリング
            img_copy = image.copy()
            scale_x = canvas_width / img_copy.width
            scale_y = canvas_height / img_copy.height

            if self.display_mode == "cover":
                # Cover: キャンバスを埋める（大きい方のスケールを使用）
                scale_factor = max(scale_x, scale_y)
            else:
                # Fit: 全体表示（小さい方のスケールを使用）
                scale_factor = min(scale_x, scale_y)

            new_width = max(int(img_copy.width * scale_factor), 1)
            new_height = max(int(img_copy.height * scale_factor), 1)

            # サイズ制限（パフォーマンス保護）
            if new_height > 50000:
                scale_factor = 50000 / img_copy.height
                new_width = max(int(img_copy.width * scale_factor), 1)
                new_height = 50000

            img_copy = img_copy.resize((new_width, new_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img_copy)
            # 画像のみ削除 (regionタグは保持)
            canvas.delete("image")

            # ★ 修正: 画像は常に(0,0)に配置（スクロール可能にするため）
            # Cover時のオフセットは座標変換計算のみに使用
            offset_x = 0
            offset_y = 0
            if self.display_mode == "cover":
                # Cover時のオフセット計算（座標変換用）
                if new_width > canvas_width:
                    offset_x = (new_width - canvas_width) // 2
                if new_height > canvas_height:
                    offset_y = (new_height - canvas_height) // 2

            # ★ 画像を(0,0)に配置（スクロール可能）
            canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
            canvas.tag_lower("image")  # 画像を最背面に移動
            canvas.image = photo

            # ★ scrollregionを画像全体に設定（スクロール可能）
            canvas.configure(scrollregion=(0, 0, new_width, new_height))
            
            # ★ Cover時は中央にスクロール
            if self.display_mode == "cover" and new_height > canvas_height:
                center_fraction = offset_y / new_height
                canvas.yview_moveto(center_fraction)
            else:
                canvas.yview_moveto(0)
            canvas.xview_moveto(0)

            # ★ B2: CanvasTransformを保存（座標変換の唯一の真実）
            from app.gui.sdk.coord_transform import CanvasTransform
            canvas._coord_tf = CanvasTransform(
                scale_x=scale_factor,
                scale_y=scale_factor,
                offset_x=offset_x,
                offset_y=offset_y
            )
            
            # ★ 互換性維持: 旧来の属性も保存（段階的移行用）
            canvas.scale_x = scale_factor
            canvas.scale_y = scale_factor
            canvas.offset_x = offset_x
            canvas.offset_y = offset_y

            # ★ デバッグ: キャンバスアイテムを確認
            items = canvas.find_all()
            image_items = canvas.find_withtag("image")
            print(f"[_display_image] Canvas items: total={len(items)}, image_tags={len(image_items)}, transform={canvas._coord_tf}")

            # ★ 描画中フラグをクリア
            self._display_in_progress = False

        except MemoryError as e:
            self._display_in_progress = False
            self._show_error("メモリ不足: 画像が大きすぎます", e)
        except Exception as e:
            self._display_in_progress = False
            self._show_error("画像表示エラー", e, show_traceback=True)

    def _toggle_display_mode(self):
        """FR-01: Cover/Fit表示モード切替"""
        self.display_mode = "fit" if self.display_mode == "cover" else "cover"
        btn_text = "[Fit]" if self.display_mode == "fit" else "[Cover]"
        self.display_mode_btn.configure(text=btn_text)
        print(f"[Display Mode] Changed to: {self.display_mode}")

        # モード変更時は古いモードのキャッシュをクリア（不要なメモリ解放）
        self._clear_image_cache()

        # 画像を再表示
        if self.web_image:
            self._display_image(self.web_canvas, self.web_image)
        if self.pdf_image:
            self._display_image(self.pdf_canvas, self.pdf_image)

        # 領域オーバーレイを再描画
        self._redraw_regions()

    def _redraw_regions(self):
        """エリア矩形を再描画 (シンク番号で色分け)"""
        try:
            # ★ デバッグ出力
            print(f"[_redraw_regions] web_regions={len(self.web_regions)}, pdf_regions={len(self.pdf_regions)}")

            # シンク色パレット
            sync_colors = [
                "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#00BCD4",
                "#E91E63", "#CDDC39", "#FF5722", "#607D8B", "#795548"
            ]

            for canvas, regions, source in [
                (self.web_canvas, self.web_regions, "web"),
                (self.pdf_canvas, self.pdf_regions, "pdf")
            ]:
                if not canvas:
                    print(f"[_redraw_regions] {source} canvas is None, skipping")
                    continue

                # 古い矩形を削除
                canvas.delete("region")

                if not regions:
                    print(f"[_redraw_regions] {source} has no regions, skipping")
                    continue

                # ★ B3: CanvasTransformを使用（座標変換の一元化）
                from app.gui.sdk.coord_transform import get_canvas_transform
                transform = get_canvas_transform(canvas)
                
                print(f"[_redraw_regions] {source}: transform={transform}")

                for region in regions:
                    try:
                        # 座標検証
                        if not hasattr(region, 'rect') or len(region.rect) < 4:
                            continue

                        # ★ B3: Transform経由で座標変換
                        x1, y1, x2, y2 = transform.src_rect_to_view(
                            region.rect[0], region.rect[1],
                            region.rect[2], region.rect[3]
                        )

                        # 色設定 (シンク番号ベース)
                        if region == self.selected_region:
                            outline = "#FFFFFF"
                            width = 3
                        elif hasattr(region, 'sync_number') and region.sync_number is not None:
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
                        area_code = getattr(region, 'area_code', '')
                        if area_code:
                            canvas.create_text(
                                x1 + 5, y1 + 5,
                                text=area_code,
                                fill=outline,
                                anchor="nw",
                                font=("Consolas", 9, "bold"),
                                tags="region"
                            )
                    except Exception as e:
                        print(f"[WARNING] Region描画スキップ: {e}")
                        continue

                # ★ 描画後のキャンバスアイテム数を出力
                region_items = canvas.find_withtag("region")
                print(f"[_redraw_regions] {source}: {len(region_items)} region items drawn")

        except Exception as e:
            self._show_error("領域描画エラー", e, show_traceback=True)

    
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
            
            # ★ 前処理は一旦無効化（カラー広告ではグレースケール化がOCR精度を下げる）
            # TODO: カラー対応の前処理を実装
            engine = CloudOCREngine(preprocess=False)
            detector = PageBreakDetector()
            
            total_web_clusters = 0
            total_pdf_clusters = 0
            
            # Web OCR
            if self.web_image:
                clusters, raw_words = engine.extract_text(self.web_image)
                self.web_raw_words = raw_words  # Store for Template Propagation
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
                self.pdf_raw_words = pdf_raw # Store
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
            
            # ★ 描画前に画像を再表示してscale_x/scale_yを確実に設定
            if self.web_image:
                self._display_image(self.web_canvas, self.web_image)
            if self.pdf_image:
                self._display_image(self.pdf_canvas, self.pdf_image)
            
            # 描画
            self._redraw_regions()
            
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
            
            # ★ OCR直後にSpreadsheetも更新 (sync_pairsなしでもWeb/PDF regionsを表示)
            self._refresh_inline_spreadsheet()
            
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
            # ★ Genius Engine Integration
            from app.core.engine.semantic_matcher import SemanticMatcher
            
            self.status_label.configure(text="🧠 Genius Sync 実行中...")
            self.update()
            
            engine = SemanticMatcher()
            # ハイブリッド最適化を実行 (RegionsはIn-place更新される)
            self.sync_pairs = engine.optimize_and_anchor(
                self.web_regions, 
                self.pdf_regions, 
                self.sync_pairs
            )
            
            print("[AutoSync] Genius Engine execution completed.")

            
            # 4. 最終描画
            self._redraw_regions_with_sync()
            
            # 5. UI成分の手動更新 (Silent Sync対応)
            total_web = len(self.web_regions)
            # 類似度はVisual(Region)を正とする (★ threshold_low=0.25)
            match_count = sum(1 for r in self.web_regions if hasattr(r, 'similarity') and r.similarity >= 0.25)
            
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
            # Spreadsheet Body
            # sync_pairsはalready updated through engine.optimize_and_anchor
            
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
        """ページサムネイルを生成 (Legacy Wrapper) -> OverviewPanelを使用"""
        self._generate_page_selector()
    
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
            self.status_label.configure(text="🔄 パラグラフマッチング計算中...")
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
            
            # マッチング実行 (★ デフォルト値を使用: 0.40/0.25)
            matcher = ParagraphMatcher()
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
            
            # ★ SDK統一: CanvasTransform経由で座標変換
            from app.gui.sdk.coord_transform import get_canvas_transform
            transform = get_canvas_transform(canvas)
            
            for region in regions:
                # ★ SDK: Source→View変換
                x1, y1, x2, y2 = transform.src_rect_to_view(
                    region.rect[0], region.rect[1],
                    region.rect[2], region.rect[3]
                )
                
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
        
        # ウィンドウ作成 (comparison_window として参照)
        self.comparison_window = ComparisonSpreadsheetWindow(
            self.parent_app,
            on_row_select=on_row_select
        )
        
        # データ渡す
        sync_pairs = getattr(self, 'sync_pairs', [])
        self.comparison_window.load_data(
            self.web_regions,
            self.pdf_regions,
            self.web_image,
            self.pdf_image,
            sync_pairs
        )
        
        self.comparison_window.focus()
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
            
            from app.gui.sdk.coord_transform import get_canvas_transform
            transform = get_canvas_transform(canvas)
            
            # 元座標で移動量を計算
            dx_orig = dx / transform.scale_x
            dy_orig = dy / transform.scale_y
            
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
            from app.gui.sdk.coord_transform import get_canvas_transform
            transform = get_canvas_transform(canvas)
            
            # キャンバス座標 → 元画像座標
            vx1 = min(self.selection_box[0], self.selection_box[2])
            vy1 = min(self.selection_box[1], self.selection_box[3])
            vx2 = max(self.selection_box[0], self.selection_box[2])
            vy2 = max(self.selection_box[1], self.selection_box[3])
            
            x1, y1 = transform.view_to_src(vx1, vy1)
            x2, y2 = transform.view_to_src(vx2, vy2)
            
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
        
        from app.gui.sdk.coord_transform import get_canvas_transform
        transform = get_canvas_transform(canvas)
        
        for region in regions:
            # Source -> View
            rx1, ry1, rx2, ry2 = transform.src_rect_to_view(
                region.rect[0], region.rect[1], region.rect[2], region.rect[3]
            )
            
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
        vx1, vy1, vx2, vy2 = rect  # View座標
        
        # ★ T3: View座標→Source座標に変換
        from app.gui.sdk.coord_transform import get_canvas_transform
        canvas = self.web_canvas if source == "web" else self.pdf_canvas
        transform = get_canvas_transform(canvas)
        
        sx1, sy1 = transform.view_to_src(int(vx1), int(vy1))
        sx2, sy2 = transform.view_to_src(int(vx2), int(vy2))
        selection_rect = (sx1, sy1, sx2, sy2)
        
        print(f"[_extract_text_from_region] View: {rect} -> Source: {selection_rect}")
        
        # 対象のパラグラフリスト
        paragraphs = self.web_regions if source == "web" else self.pdf_regions
        
        extracted_parts = []
        
        for para in paragraphs:
            px1, py1, px2, py2 = para.rect  # Source座標
            
            # 選択範囲と重なるかチェック（Source座標同士で比較）
            if self._rects_overlap(selection_rect, (px1, py1, px2, py2)):
                extracted_parts.append(para.text)
        
        print(f"[_extract_text_from_region] Matched {len(extracted_parts)} paragraphs")
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
        """Web/PDFどちらかの領域エディタを開く (Combined Editor)"""
        if not self.web_image and not self.pdf_image:
           self.status_label.configure(text="⚠️ 画像が読み込まれていません")
           return
           
        from app.gui.windows.region_editor import open_region_editor

        # Prepare Data
        web_regions_data = [r.to_dict() for r in self.web_regions]
        pdf_regions_data = [r.to_dict() for r in self.pdf_regions]
        
        # LLM Callback
        def llm_cb(param1, param2): # (web_text, pdf_text)
            if not getattr(self, 'llm_client', None):
                try:
                    from app.core.llm_client import LLMClient
                    self.llm_client = LLMClient()
                except: return "❌ LLM Init Failed"
                
            if not self.llm_client or not self.llm_client.model:
                 return "⚠️ GEMINI_API_KEY Missing"

            prompt = f"""
Compare the following two text segments semantically for content proofing.
Ignore minor OCR errors, whitespace, or punctuation differences.

Text A (Web Source):
{param1}

Text B (PDF Source):
{param2}

Please provide:
1. Similarity Score (0-100%)
2. Key discrepancies
3. Verdict: MATCH or MISMATCH
"""
            return self.llm_client.generate_content(prompt) or "Error in generation"

        # Open Unified Editor
        RegionEditor = open_region_editor(
            self,
            self.web_image,
            self.pdf_image,
            web_regions_data,
            pdf_regions_data,
            active_source=source_type,
            callback=self._on_region_update,
            propagate_callback=self._propagate_from_editor,
            llm_callback=llm_cb
        )
        
        self.status_label.configure(text=f"🖊️ Unified Editor ({source_type.upper()}) Opened")

    
    
    def _open_match_simulator(self):
        """シミュレータボタン (Unified Editorを開く)"""
        self._open_region_editor("web")
        return
        
        # Dead Code below
        from app.gui.windows.match_simulator import MatchSimulatorWindow
        
        # スプレッドシートの選択行を取得
        ids = self.spreadsheet_panel.get_selected_ids() 
        
        ids = ids or getattr(self, "selected_pair_ids", None) # Fallback if stored elsewhere
        
        web_r = None
        pdf_r = None
        
        if ids:
            web_id, pdf_id = ids
            # Find regions
            # self.web_regions is list of EditableRegion
            for r in self.web_regions:
                if r.area_code == web_id: web_r = r; break
            for r in self.pdf_regions:
                if r.area_code == pdf_id: pdf_r = r; break
        else:
            # Fallback to active regions (last clicked on canvas)
            # Need to track active regions?
            # self.selected_region is current one.
            pass
            
        if not web_r or not pdf_r:
            self.status_label.configure(text="⚠️ Spreadsheetで行を選択してください")
            return
            
        # Crop Images
        try:
            # Web
            wx1, wy1, wx2, wy2 = map(int, web_r.rect)
            if self.web_image:
                 web_crop = self.web_image.crop((wx1, wy1, wx2, wy2))
            else: web_crop = Image.new("RGB", (100,100), "gray")
            
            # PDF
            px1, py1, px2, py2 = map(int, pdf_r.rect)
            if self.pdf_image:
                 pdf_crop = self.pdf_image.crop((px1, py1, px2, py2))
            else: pdf_crop = Image.new("RGB", (100,100), "gray")
            
            # Real LLM Callback
            def llm_check(t1, t2):
                if not getattr(self, 'llm_client', None):
                    # Try to init if missing
                    try:
                        from app.core.llm_client import LLMClient
                        self.llm_client = LLMClient()
                    except:
                        return "❌ LLM Client Init Failed"

                if not self.llm_client or not self.llm_client.model:
                    return "⚠️ GEMINI_API_KEY Not Found"

                prompt = f"""
Compare the following two text segments semantically for content proofing.
Ignore minor OCR errors, whitespace, or punctuation differences.

Text A (Web Source):
{t1}

Text B (PDF Source):
{t2}

Please provide:
1. distinct Semantic Similarity Score (0-100%)
2. List of meaningful discrepancies (ignore formatting)
3. Verdict: MATCH or MISMATCH
"""
                return self.llm_client.generate_content(prompt)
            
            # Save Callback
            def on_save_sync(new_web_text, new_pdf_text):
                print(f"[Simulator] Save Sync Requested")
                if web_r:
                    web_r.text = new_web_text
                if pdf_r:
                    pdf_r.text = new_pdf_text
                
                # Update UI
                self._recalculate_sync()
                self.spreadsheet_panel._refresh_rows()
                self.status_label.configure(text="✅ シミュレータからデータを更新しました")

            sim_win = MatchSimulatorWindow(
                self,
                web_crop, pdf_crop,
                web_r.text, pdf_r.text,
                on_llm_request=llm_check,
                on_save_callback=on_save_sync
            )
            sim_win.focus()
            
        except Exception as e:
            print(f"Simulator Error: {e}")
            self.status_label.configure(text=f"❌ シミュレータ起動エラー: {e}")
            import traceback
            traceback.print_exc()

    def _propagate_from_editor(self, template: dict, source: str) -> list:
        """エディタからの類似検出リクエスト"""
        try:
            from app.core.structure_propagator import StructurePropagator
            src = source.lower()
            target_raw = getattr(self, f'{src}_raw_words', [])
            image = getattr(self, f'{src}_image', None)
            
            if not target_raw or not image:
                print(f"[Propagate] No raw data for {source}")
                return []
                
            propagator = StructurePropagator()
            page_size = (image.width, image.height)
            
            print(f"[Propagate] Template: {template['rect']} on {source}. Raw Words: {len(target_raw)}")
            target_clusters = getattr(self, f'{src}_paragraphs', [])
            
            # Pass image and clusters for Hybrid Matching
            new_data = propagator.propagate(template, target_raw, page_size, image=image, clusters=target_clusters)
            print(f"[Propagate] Propagator returned {len(new_data)} regions")

            # Convert to Region Dicts with Text
            regions = []
            for item in new_data:
                rect = item['rect']
                x1, y1, x2, y2 = rect
                texts = []
                margin = 5 # Relaxed margin
                
                # Simple containment text extraction
                # Sort roughly by Y then X
                # But simple iteration is fine if we just join.
                # Ideally: sort words by position
                
                captured_words = []
                for w in target_raw:
                     wx1, wy1, wx2, wy2 = w['rect']
                     cx = (wx1+wx2)/2
                     cy = (wy1+wy2)/2
                     if (x1 - margin) <= cx <= (x2 + margin) and (y1 - margin) <= cy <= (y2 + margin):
                         captured_words.append(w)
                
                # Sort captured words: primarily Y (lines), then X
                captured_words.sort(key=lambda w: (w['rect'][1] // 20, w['rect'][0]))
                
                texts = [w['text'] for w in captured_words]
                combined_text = "".join(texts)
                
                regions.append({
                    'rect': rect,
                    'text': combined_text,
                    'color': '#4CAF50'
                })
            
            return regions
            
        except Exception as e:
            print(f"[Propagate] Error: {e}")
            import traceback
            traceback.print_exc()
            return []

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
    
    # [REMOVED] 高度クラスターマッチング - Sync再計算と重複のため削除 (2026-01-12)
    # メソッド _run_advanced_cluster_matching は _recalculate_sync を呼ぶだけだったため不要

    
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

    def _open_comparison_spreadsheet(self):
        """詳細比較スプレッドシート(画面2)を開く"""
        try:
            from app.gui.windows.comparison_spreadsheet import ComparisonSpreadsheetWindow
            
            if hasattr(self, 'comparison_window') and self.comparison_window.winfo_exists():
                self.comparison_window.lift()
                self.comparison_window.focus()
                return

            self.comparison_window = ComparisonSpreadsheetWindow(self)
            self.comparison_window.load_data(
                self.web_regions, 
                self.pdf_regions,
                getattr(self, 'web_image', None),
                getattr(self, 'pdf_image', None),
                self.sync_pairs
            )
            self.comparison_window.focus()
            
        except Exception as e:
            print(f"Error opening spreadsheet: {e}")
            import traceback
            traceback.print_exc()

    def _on_canvas_right_click(self, event, source):
        """右クリックメニュー"""
        try:
            canvas = event.widget
            menu = tk.Menu(self, tearoff=0, bg="#2D2D2D", fg="white", activebackground="#4CAF50")
            
            y_screen = canvas.canvasy(event.y)
            if hasattr(canvas, 'scale_y') and canvas.scale_y > 0:
                y_img = int(y_screen / canvas.scale_y)
                menu.add_command(label=f"ここにページ区切りを設定 (Y={y_img})", command=lambda: self._split_page_at_cursor(y_img, source))
                
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"Right click menu error: {e}")

    def _split_page_at_cursor(self, y_pos, source):
        """指定位置でページ分割"""
        print(f"[PageSplit] Splitting at Y={y_pos}")
        target_img = self.web_image if source == "web" else self.pdf_image
        if not target_img: return
        
        # Init regions if empty
        if not hasattr(self, 'page_regions') or not self.page_regions:
            self.page_regions = [(0, target_img.height)]
            
        new_regions = []
        split_done = False
        
        for (start, end) in self.page_regions:
            if start < y_pos < end:
                new_regions.append((start, y_pos))
                new_regions.append((y_pos, end))
                split_done = True
            else:
                new_regions.append((start, end))
        
        if not split_done:
            pass

        self.page_regions = new_regions
        # ★ A1: Overview廃止のため_update_overview_panel呼び出しを削除
        self.status_label.configure(text=f"✂️ ページ区切りを追加しました (Y={y_pos})")

    def _on_propagate_click(self):
        """選択中の領域をテンプレートとして、類似領域を自動検出"""
        if not self.selected_region:
            self.status_label.configure(text="⚠️ テンプレートにする領域を選択してください")
            return
            
        source = self.selected_region.source
        target_raw = None
        target_image = None
        
        if source == "web":
            target_raw = getattr(self, 'web_raw_words', [])
            target_image = self.web_image
        elif source == "pdf":
            target_raw = getattr(self, 'pdf_raw_words', [])
            target_image = self.pdf_image
            
        if not target_raw:
             self.status_label.configure(text="⚠️ OCR詳細データがありません")
             return

        from app.core.structure_propagator import StructurePropagator
        from app.gui.windows.advanced_comparison_view import EditableRegion
        
        self.status_label.configure(text=f"✨ {source.upper()} 類似パターン検出中...")
        self.update()
        
        try:
            propagator = StructurePropagator()
            
            # テンプレート情報
            template = {
                "rect": self.selected_region.rect,
                "text": self.selected_region.text
            }
            
            page_size = (target_image.width, target_image.height)
            new_regions_data = propagator.propagate(
                template, 
                target_raw, 
                page_size,
                image=target_image
            )
            
            if not new_regions_data:
                self.status_label.configure(text="⚠️ 類似パターンが見つかりませんでした")
                return
            
            # 結果リスト作成
            new_regions = []
            for i, data in enumerate(new_regions_data):
                # テキスト抽出
                rect = data['rect']
                x1, y1, x2, y2 = rect
                texts = []
                for w in target_raw:
                    wx1, wy1, wx2, wy2 = w['rect']
                    cx = (wx1 + wx2) / 2
                    cy = (wy1 + wy2) / 2
                    if x1 <= cx <= x2 and y1 <= cy <= y2:
                        texts.append(w['text'])
                
                extracted_text = "".join(texts)
                
                # Area Code Prefix
                prefix = "WEB" if source == "web" else "PDF"
                
                r = EditableRegion(
                   id=i+1,
                   rect=rect,
                   text=extracted_text, 
                   area_code=f"{prefix}-{i+1:02d}", 
                   sync_number=None,
                   similarity=1.0,
                   source=source
                )
                new_regions.append(r)
            
            # 更新適用
            if source == "web":
                self.web_regions = new_regions
            else:
                self.pdf_regions = new_regions
            
            self._update_area_list()
            self._redraw_regions()
            self.status_label.configure(text=f"✨ {len(new_regions)}箇所のエリアを正規化しました")
                
        except Exception as e:
             import traceback
             traceback.print_exc()
             self.status_label.configure(text=f"❌ 検出エラー: {e}")
    def _open_comparison_matrix(self):
        """比較マトリクスウィンドウを開く"""
        try:
            from app.gui.windows.comparison_matrix import ComparisonMatrixWindow
            
            # 安全なウィンドウ存在チェック
            if self._safe_window_exists('matrix_window'):
                self.matrix_window.lift()
                self.matrix_window.focus()
                return

            self.matrix_window = ComparisonMatrixWindow(self)
            
            # データを渡す
            web_txt = self.web_text_box.get("1.0", "end") if hasattr(self, 'web_text_box') else ""
            pdf_txt = self.pdf_text_box.get("1.0", "end") if hasattr(self, 'pdf_text_box') else ""
            
            self.matrix_window.set_web_data(getattr(self, 'web_image', None), web_txt)
            self.matrix_window.set_pdf_data(getattr(self, 'pdf_image', None), pdf_txt)
            
            self.matrix_window.focus()
            
        except Exception as e:
            print(f"Error opening matrix: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.configure(text=f"❌ マトリクスエラー: {e}")

    def _export_metadata(self):
        """OCRメタデータをCSV/Excelに出力 (Phase 2)"""
        try:
            # クラスターデータを収集 - 正しい変数名を使用
            web_clusters = self.web_clusters if hasattr(self, 'web_clusters') else []
            pdf_clusters = self.pdf_clusters if hasattr(self, 'pdf_clusters') else []
            
            # web_regions/pdf_regionsも確認（EditableRegion形式の場合）
            if not web_clusters and hasattr(self, 'web_regions') and self.web_regions:
                for r in self.web_regions:
                    web_clusters.append({
                        'rect': r.rect if hasattr(r, 'rect') else [0, 0, 0, 0],
                        'text': r.text if hasattr(r, 'text') else '',
                        'page': getattr(r, 'page', 1)
                    })
            
            if not pdf_clusters and hasattr(self, 'pdf_regions') and self.pdf_regions:
                for r in self.pdf_regions:
                    pdf_clusters.append({
                        'rect': r.rect if hasattr(r, 'rect') else [0, 0, 0, 0],
                        'text': r.text if hasattr(r, 'text') else '',
                        'page': getattr(r, 'page', 1)
                    })
            
            if not web_clusters and not pdf_clusters:
                self.status_label.configure(text="⚠️ エクスポートするデータがありません。OCRを実行してください。")
                return
            
            # エクスポート実行
            result = export_ocr_metadata(web_clusters, pdf_clusters, "./exports")
            
            msg = f"✅ メタデータ出力完了: Web {len(web_clusters)}件, PDF {len(pdf_clusters)}件"
            if 'csv' in result:
                msg += f" → {result['csv']}"
            
            self.status_label.configure(text=msg)
            print(f"[MetadataExport] {msg}")
            
        except Exception as e:
            print(f"Error exporting metadata: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.configure(text=f"❌ メタデータ出力エラー: {e}")

    def _run_ocr_analysis(self):
        """Gemini Hybrid OCRを実行し、結果をUIに反映"""
        if not getattr(self, 'web_image', None) and not getattr(self, 'pdf_image', None):
             self._safe_status("⚠️ 画像が読み込まれていません")
             return

        self._safe_status("🔥 Gemini Hybrid OCR実行中... 完了までしばらくお待ちください")

        try:
            from app.core.hybrid_ocr import HybridOCREngine
            engine = HybridOCREngine()
            
            # Web OCR
            if getattr(self, 'web_image', None):
                 self._safe_status("🔥 Gemini Hybrid OCR: Web画像を解析中...")
                 res_web = engine.detect_document_text(self.web_image)
                 self.web_regions = self._process_ocr_result(res_web, "web")
                 self._safe_status(f"✅ Web OCR完了: {len(self.web_regions)}リージョン検出")
            
            # PDF OCR
            if getattr(self, 'pdf_image', None):
                 self._safe_status("🔥 Gemini Hybrid OCR: PDF画像を解析中...")
                 res_pdf = engine.detect_document_text(self.pdf_image)
                 self.pdf_regions = self._process_ocr_result(res_pdf, "pdf")
                 self._safe_status(f"✅ PDF OCR完了: {len(self.pdf_regions)}リージョン検出")

            self._safe_status("🔄 パラグラフマッチング計算中...")

            # Update ID & Sync
            self._recalculate_sync()
            
            # Update Panels
            self._update_area_list()
            self._redraw_regions()
            self._refresh_inline_spreadsheet() # This updates the sheet thumbnails
            
            count_web = len(self.web_regions)
            count_pdf = len(self.pdf_regions)
            self._safe_status(f"✅ OCR完了: Web {count_web}件 / PDF {count_pdf}件")

        except Exception as e:
            self._safe_status(f"❌ OCRエラー: {e}")
            print(f"OCR Failed: {e}")
            import traceback
            traceback.print_exc()

    def _process_ocr_result(self, result, source):
        """OCR結果をEditableRegionに変換"""
        regions = []
        if not result or 'blocks' not in result:
            return regions
            
        blocks = result['blocks']
        
        # Sort blocks: Y (primary), X (secondary)
        blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))
        
        prefix = source.upper()
        
        from app.gui.windows.advanced_comparison_view import EditableRegion

        for i, block in enumerate(blocks):
             rect = block['bbox'] # [x0, y0, x1, y1]
             text = block['text']
             
             if not text or not text.strip(): continue
             
             r = EditableRegion(
                 id=i+1,
                 rect=rect,
                 text=text,
                 area_code=f"{prefix}-{i+1:02d}", # Unique ID (WEB-01, etc.)
                 sync_number=None,
                 similarity=0.0,
                 source=source
             )
             regions.append(r)
        return regions

    def _run_text_comparison(self):
        """Phase 4: 全文比較を実行してSpreadsheetPanelに結果を反映"""
        self._safe_status("🔍 全文比較実行中...")
        
        try:
            # メタデータが出力されているか確認
            from pathlib import Path
            exports_dir = Path('./exports')
            csv_files = sorted(exports_dir.glob('metadata_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True)
            
            if not csv_files:
                # メタデータがなければ先に出力
                self._export_metadata()
                csv_files = sorted(exports_dir.glob('metadata_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True)
            
            if not csv_files:
                self._safe_status("⚠️ メタデータCSVがありません。OCRを実行してください。")
                return
            
            # テキスト比較実行
            from app.pipeline.text_comparator import run_text_comparison
            results = run_text_comparison()
            
            if not results:
                self._safe_status("⚠️ マッチするパラグラフが見つかりませんでした")
                return
            
            # 結果をステータスに表示
            match_count = len(results)
            top_match = results[0] if results else {}
            
            msg = f"✅ 全文比較完了: {match_count}件のマッチ"
            if top_match:
                msg += f" (最長: {top_match.get('common_len', 0)}文字)"
            
            self._safe_status(msg)
            
            # Excel出力完了を通知
            comparison_files = sorted(exports_dir.glob('comparison_*.xlsx'), key=lambda x: x.stat().st_mtime, reverse=True)
            if comparison_files:
                print(f"[TextComparison] Excel: {comparison_files[0]}")
            
        except Exception as e:
            print(f"Error in text comparison: {e}")
            import traceback
            traceback.print_exc()
            self._safe_status(f"❌ 全文比較エラー: {e}")
