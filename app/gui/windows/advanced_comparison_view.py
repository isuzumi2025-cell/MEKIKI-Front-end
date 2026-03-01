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
import re
from dataclasses import dataclass
from app.pipeline.metadata_exporter import export_ocr_metadata
from app.utils.image_cache import LRUImageCache
from app.gui.sdk.scroll_sync import ScrollSyncManager

# SelectionMixin 統合 (SDK Phase 2)
try:
    from app.gui.windows.comparison_mixins.selection_mixin import SelectionMixin
    _HAS_SELECTION_MIXIN = True
except ImportError:
    _HAS_SELECTION_MIXIN = False
    class SelectionMixin:
        """Fallback stub"""
        pass

# EditMixin 統合 (Phase 1.5)
try:
    from app.gui.windows.comparison_mixins.edit_mixin import EditMixin
    _HAS_EDIT_MIXIN = True
except ImportError:
    _HAS_EDIT_MIXIN = False
    class EditMixin:
        """Fallback stub"""
        pass

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
    
    # ★ Phase 44: ページID (Web: ページ番号, PDF: -1 = スティッチ)
    page_id: int = -1  # -1 = ページ情報なし（スティッチモード）
    coord_system: str = "local"  # local=page-relative, global=stitched
    stitched_y_offset: int = 0
    
    # キャンバス上でのID
    canvas_rect_id: Optional[int] = None
    canvas_text_id: Optional[int] = None
    
    # ★ Phase 1.6 Fix: to_dict メソッド追加
    def to_dict(self) -> Dict:
        """辞書に変換"""
        return {
            "id": self.id,
            "rect": self.rect,
            "text": self.text,
            "area_code": self.area_code,
            "sync_number": self.sync_number,
            "similarity": self.similarity,
            "source": self.source,
            "page_id": self.page_id,
            "coord_system": self.coord_system,
            "stitched_y_offset": self.stitched_y_offset,
            "canvas_rect_id": self.canvas_rect_id,
            "canvas_text_id": self.canvas_text_id,
        }


class AdvancedComparisonView(EditMixin, SelectionMixin, ctk.CTkFrame):
    """
    高度な校正ワークスペース
    埋め込みフレーム版 (比較マトリクスを置き換え)
    
    Mixins:
    - SelectionMixin: 範囲選択 (Quick/Fullモード、即座シート反映)
    - EditMixin: 手動編集 (ドラッグ移動、リサイズ、リアルタイム更新)
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
        
        # ★ ByCursor Fix: ページリストの初期化
        self.web_pages_list: List = []
        self.pdf_pages_list: List = []
        self.web_pages: List = []
        self.pdf_pages: List = []
        self.current_pdf_idx: int = 0
        
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
        self._is_fullscreen: bool = False

        # FR-01: 画像表示モード ("cover" or "fit")
        self.display_mode: str = "cover"

        # Source-specific display mode state
        self.display_mode_by_source: Dict[str, str] = {
            "web": "cover",
            "pdf": "fit",
        }

        # Rendering quality guards for dense pages
        self.min_region_area_by_source: Dict[str, int] = {"web": 64, "pdf": 300}
        self.max_regions_per_view_by_source: Dict[str, int] = {"web": 240, "pdf": 240}
        # Display policy: PDF shows selected/matched first by default
        self.region_display_mode_by_source: Dict[str, str] = {"web": "all", "pdf": "all"}
        self.show_unmatched_area_labels_by_source: Dict[str, bool] = {"web": True, "pdf": True}
        self.pdf_region_merge_gap_px: int = 28
        self.pdf_region_merge_x_overlap_ratio: float = 0.35
        self.pdf_max_regions_per_page: int = 240
        self.pdf_card_merge_max_area_ratio: float = 0.28
        self.pdf_card_merge_min_keep_ratio: float = 0.45

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
        
        # ★ キャッシュ用変数 (Stitched Images)
        self._web_stitch_cache = None
        self._pdf_stitch_cache = None

        # LRU画像キャッシュ（業務配布対応: 高速化 + メモリ効率化）
        self._image_cache_web = LRUImageCache(max_size=20, max_memory_mb=250)
        self._image_cache_pdf = LRUImageCache(max_size=20, max_memory_mb=250)
        
        # ★ B5: Crosshair Sanity Check
        self._crosshair_enabled = False  # クロスヘア表示フラグ
        self._last_crosshair_pos = None  # 最後のクロスヘア位置

        # Region diagnostics store (per source) for reproducible drift analysis.
        self._last_region_diagnostics: Dict[str, Dict] = {}
        self._overlay_log_sample_limit: int = 3

        # ★ SDK Phase 2: SelectionMixin 初期化
        if _HAS_SELECTION_MIXIN and hasattr(self, '_init_selection_manager'):
            self._init_selection_manager()
        
        # ★ Phase 1.5: EditMixin 初期化
        if _HAS_EDIT_MIXIN and hasattr(self, '_init_edit_mixin'):
            self._init_edit_mixin()
        
        # ★ 遅延イベント再バインド（ウィジェット完全表示後に確実にバインド）
        self.after(1000, self._bind_canvas_events)

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
    def _safe_after(self, delay_ms: int, callback: Callable):
        """Ignore stale after callbacks when widgets are already destroyed."""
        def _wrapped():
            try:
                if not self.winfo_exists():
                    return
                callback()
            except tk.TclError as e:
                if "invalid command name" in str(e):
                    print(f"[UI] Skip stale callback: {e}")
                    return
                print(f"[UI] TclError in callback: {e}")
            except Exception as e:
                print(f"[UI] callback error: {e}")

        try:
            if not self.winfo_exists():
                return None
            return self.after(delay_ms, _wrapped)
        except Exception:
            return None

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
            command=self._find_similar_gemini
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
        # FR-01: display mode toggle button (Web)
        self.web_display_mode_btn = ctk.CTkButton(
            web_header, text="[Web:Cover]", width=90, height=22, fg_color="#555555",
            hover_color="#666666", command=lambda: self._toggle_display_mode("web")
        )
        self.web_display_mode_btn.pack(side="right", padx=5, pady=4)
        # backward compatibility alias
        self.display_mode_btn = self.web_display_mode_btn

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

        self.pdf_display_mode_btn = ctk.CTkButton(
            pdf_header, text="[PDF:Fit]", width=90, height=22, fg_color="#555555",
            hover_color="#666666", command=lambda: self._toggle_display_mode("pdf")
        )
        self.pdf_display_mode_btn.pack(side="right", padx=5, pady=4)
        
        pdf_nav_frame = ctk.CTkFrame(pdf_header, fg_color="transparent")
        pdf_nav_frame.pack(side="right", padx=5)
        ctk.CTkButton(pdf_nav_frame, text="◀", width=25, height=22, command=self._prev_pdf_page).pack(side="left", padx=1)
        self.pdf_page_label = ctk.CTkLabel(pdf_nav_frame, text="Page 1 / 1", font=("Meiryo", 9), width=90)
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

        # スクロール同期マネージャー（業務配布対応: UX向上）
        self._scroll_sync_manager = ScrollSyncManager(
            self.web_canvas,
            self.pdf_canvas,
            debounce_ms=50,
            on_sync=lambda msg: print(f"  🔗 {msg}")
        )
        # デフォルトでON
        self._scroll_sync_manager.enable()
        print("✅ Scroll sync enabled by default")

        # ★★★ Phase 1.6: SimpleSelectionHandler で置き換え ★★★
        # 複雑なMixin統合を廃止し、シンプルで確実な新ハンドラを使用
        try:
            from app.sdk.selection.simple_handler import SimpleSelectionHandler
            
            # PDF用ハンドラ (image_getter で動的に画像取得)
            self._pdf_selection_handler = SimpleSelectionHandler(
                canvas=self.pdf_canvas,
                image=self.pdf_image,  # 初期値（None可）
                source="pdf",
                on_selection_complete=self._on_simple_selection_complete,
                on_selection_deleted=self._on_simple_selection_deleted,
                image_getter=lambda: self.pdf_image  # ★ 動的に現在の画像を取得
            )
            
            # Web用ハンドラ
            self._web_selection_handler = SimpleSelectionHandler(
                canvas=self.web_canvas,
                image=self.web_image,
                source="web",
                on_selection_complete=self._on_simple_selection_complete,
                on_selection_deleted=self._on_simple_selection_deleted,
                image_getter=lambda: self.web_image
            )
            
            print("✅ SimpleSelectionHandler initialized for PDF and Web")
            # Ctrl+Shift+Delete → 全手動選択クリア
            self.bind_all("<Control-Shift-Delete>", self._clear_all_manual_selections)
            print("✅ Ctrl+Shift+Delete bound to clear all manual selections")
        except Exception as e:
            print(f"⚠️ SimpleSelectionHandler failed: {e}")
            # フォールバック: 旧イベントバインディング
            for canvas in [self.web_canvas, self.pdf_canvas]:
                canvas.bind("<ButtonPress-1>", self._on_canvas_click)
                canvas.bind("<B1-Motion>", self._on_canvas_drag)
                canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
            print("✅ Fallback: Old canvas events bound")
        
        # Crosshair (Motion/Leave)
        for canvas in [self.web_canvas, self.pdf_canvas]:
            canvas.bind("<Motion>", self._on_mouse_motion)
            canvas.bind("<Leave>", self._on_mouse_leave)
    
    def _bind_canvas_events(self):
        """キャンバスイベントを再バインド（タブ切替時に必要）"""
        # ★ SimpleSelectionHandler が有効な場合は上書きしない
        if hasattr(self, '_pdf_selection_handler') and self._pdf_selection_handler:
            print("[EventBind] ⚠️ Skipping rebind - SimpleSelectionHandler active")
            return
        
        for canvas in [self.web_canvas, self.pdf_canvas]:
            # 既存のバインドをクリアして再バインド
            canvas.bind("<ButtonPress-1>", self._on_canvas_click)
            canvas.bind("<B1-Motion>", self._on_canvas_drag)
            canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
            canvas.bind("<Motion>", self._on_mouse_motion)
            canvas.bind("<Leave>", self._on_mouse_leave)
        print("[EventBind] Canvas events rebound (fallback mode)")
    
    def _on_source_tab_change(self):
        """タブ切替時のコールバック"""
        current_tab = self.view_tabs.get()
        print(f"[TabChange] Switched to: {current_tab}")
    
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
        
        # ★ Similar/Match検索コールバック登録
        self.spreadsheet_panel.set_on_similar_search(self._handle_similar_search)
        self.spreadsheet_panel.set_on_match_search(self._handle_match_search)
    
    def _normalize_region_lookup_key(self, key: str) -> str:
        key = str(key or "").strip()
        if not key:
            return ""
        # normalize separators/case to stabilize row->region lookup
        key = key.replace("_", "-").replace(" ", "")
        return key.upper()

    def _build_region_lookup_map(self, regions):
        result = {}
        for r in (regions or []):
            area_code = getattr(r, "area_code", None)
            if not area_code:
                continue
            norm = self._normalize_region_lookup_key(area_code)
            if norm:
                result[norm] = r
        return result

    def _on_spreadsheet_row_select(self, web_id: str, pdf_id: str, pair):
        """Spreadsheet row select: page-switch then highlight on both canvases."""
        print(f"[Source Sync] Highlighting: Web={web_id}, PDF={pdf_id}")

        web_len = len(self.web_regions) if self.web_regions else 0
        pdf_len = len(self.pdf_regions) if self.pdf_regions else 0

        if not hasattr(self, "_web_region_map") or self._web_region_map is None or getattr(self, "_web_region_cache_len", 0) != web_len:
            self._web_region_map = self._build_region_lookup_map(self.web_regions)
            self._web_region_cache_len = web_len
        if not hasattr(self, "_pdf_region_map") or self._pdf_region_map is None or getattr(self, "_pdf_region_cache_len", 0) != pdf_len:
            self._pdf_region_map = self._build_region_lookup_map(self.pdf_regions)
            self._pdf_region_cache_len = pdf_len

        web_region = self._web_region_map.get(self._normalize_region_lookup_key(web_id))
        pdf_region = self._pdf_region_map.get(self._normalize_region_lookup_key(pdf_id))

        if not web_region:
            print(f"[Source Sync] 笞・・Web region not found: {web_id} (available={len(self._web_region_map)})")
        if not pdf_region:
            print(f"[Source Sync] 笞・・PDF region not found: {pdf_id} (available={len(self._pdf_region_map)})")

        page_changed = False
        if web_region:
            page_changed = self._switch_canvas_to_region_page("web", web_region) or page_changed
        if pdf_region:
            page_changed = self._switch_canvas_to_region_page("pdf", pdf_region) or page_changed
        if page_changed:
            self._redraw_regions()

        self._highlight_region_on_canvas(self.web_canvas, web_region, "#FF6F00")
        self._highlight_region_on_canvas(self.pdf_canvas, pdf_region, "#2196F3")

        if web_region and hasattr(self, "web_text_box"):
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", f"[{web_id}]\n{web_region.text}")

        if pdf_region and hasattr(self, "pdf_text_box"):
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", f"[{pdf_id}]\n{pdf_region.text}")

    def _switch_canvas_to_region_page(self, source: str, region) -> bool:
        """Switch the source canvas to region.page_id when needed."""
        if not region:
            return False

        page_id = self._infer_region_page_id(region, source)
        if not page_id or page_id < 1:
            return False

        pages = self._get_pages_for_source(source)
        if not pages or page_id > len(pages):
            return False

        current_page = self._get_current_page_for_source(source)
        if current_page == page_id:
            return False

        page = pages[page_id - 1]
        if not isinstance(page, dict):
            return False

        page_image = page.get("image")
        if page_image is None:
            return False

        if source == "web":
            self.current_web_page_idx = page_id - 1
            self.current_page = page_id
            self.web_image = page_image
            self._clear_image_cache("web")
            self._display_image(self.web_canvas, self.web_image)
            if hasattr(self, "page_label") and self.page_label.winfo_exists():
                self.page_label.configure(text=f"Page {page_id} / {len(pages)}")
            print(f"[Source Sync] Switched web canvas to page {page_id}")
            return True

        self.current_pdf_idx = page_id - 1
        self.current_pdf_page_idx = page_id - 1
        self.current_pdf_page = page_id
        self.pdf_image = page_image
        self._clear_image_cache("pdf")
        self._display_image(self.pdf_canvas, self.pdf_image)
        if hasattr(self, "pdf_page_label") and self.pdf_page_label.winfo_exists():
            self.pdf_page_label.configure(text=f"Page {page_id} / {len(pages)}")
        print(f"[Source Sync] Switched pdf canvas to page {page_id}")
        return True


    def _highlight_region_on_canvas(self, canvas, region, color: str):
        """Canvas上で指定領域をハイライト表示 + スクロール
        
        CanvasTransform + page-aware rect正規化を使用
        """
        if not region or not hasattr(region, 'rect'):
            return
        
        # ★ Widget存在確認（Tkinterエラー防止）
        try:
            if not canvas or not canvas.winfo_exists():
                print("[Highlight] Canvas does not exist, skipping")
                return
        except Exception:
            return

        # 既存のハイライトを削除
        canvas.delete("highlight")

        source = None
        if canvas == getattr(self, "web_canvas", None):
            source = "web"
        elif canvas == getattr(self, "pdf_canvas", None):
            source = "pdf"

        rect = list(region.rect)
        if source:
            rect = self._normalize_region_rect_for_current_view(region, source)
        if len(rect) < 4:
            return

        from app.gui.sdk.coord_transform import get_canvas_transform
        transform = get_canvas_transform(canvas)
        sx1, sy1, sx2, sy2 = transform.src_rect_to_view(rect[0], rect[1], rect[2], rect[3])
        
        print(
            f"[Highlight] rect=({rect[0]},{rect[1]},{rect[2]},{rect[3]}) "
            f"-> view=({sx1},{sy1},{sx2},{sy2})"
        )

        # ハイライト矩形を描画 (太い枠線)
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

    def _highlight_bbox_on_canvas(self, canvas, bbox, color: str):
        """Canvas上で指定bboxをハイライト表示 + スクロール
        
        ★ bbox版: [x1, y1, x2, y2] リスト/タプルを直接受け取る
        ★ オンデマンドスケール計算: canvas.scale_xが未設定の場合、動的に算出
        """
        if not bbox:
            print(f"[Highlight] SKIP: bbox is None")
            return
        
        # ★ Widget存在確認（Tkinterエラー防止）
        try:
            if not canvas or not canvas.winfo_exists():
                print("[Highlight] Canvas does not exist, skipping")
                return
        except Exception:
            return

        # 既存のハイライトを削除
        canvas.delete("highlight")

        # 座標を取得
        x1, y1, x2, y2 = bbox

        # ★ オンデマンドでスケール計算
        scale_x = getattr(canvas, 'scale_x', None)
        scale_y = getattr(canvas, 'scale_y', None)
        
        if scale_x is None or scale_y is None:
            # scale未設定 → scrollregionと元画像から計算
            try:
                # 元画像サイズを取得
                if canvas == self.web_canvas and hasattr(self, 'web_image') and self.web_image:
                    orig_w, orig_h = self.web_image.size
                elif canvas == self.pdf_canvas and hasattr(self, 'pdf_image') and self.pdf_image:
                    orig_w, orig_h = self.pdf_image.size
                else:
                    orig_w, orig_h = 1, 1
                
                # scrollregionから表示サイズを取得
                scrollregion = canvas.cget('scrollregion')
                if scrollregion:
                    parts = scrollregion.split()
                    if len(parts) >= 4:
                        display_w = float(parts[2])
                        display_h = float(parts[3])
                        scale_x = display_w / orig_w if orig_w > 0 else 1.0
                        scale_y = display_h / orig_h if orig_h > 0 else 1.0
                    else:
                        scale_x, scale_y = 1.0, 1.0
                else:
                    scale_x, scale_y = 1.0, 1.0
                    
                print(f"[Highlight] On-demand scale: orig=({orig_w}x{orig_h}), scale=({scale_x:.4f},{scale_y:.4f})")
            except Exception as e:
                print(f"[Highlight] Scale calc error: {e}")
                scale_x, scale_y = 1.0, 1.0

        # スケール適用
        sx1, sy1 = int(x1 * scale_x), int(y1 * scale_y)
        sx2, sy2 = int(x2 * scale_x), int(y2 * scale_y)
        
        print(f"[Highlight] bbox=({x1},{y1},{x2},{y2}) → view=({sx1},{sy1},{sx2},{sy2}) scale=({scale_x:.3f},{scale_y:.3f})")

        # ハイライト矩形を描画 (太い枠線)
        canvas.create_rectangle(
            sx1, sy1, sx2, sy2,
            outline=color, width=4,
            tags="highlight"
        )

        # 領域が見えるようにスクロール
        scrollregion = canvas.cget('scrollregion')
        if scrollregion:
            try:
                parts = scrollregion.split()
                total_height = float(parts[3]) if len(parts) >= 4 else 1
                if total_height > 0:
                    center_y = (sy1 + sy2) / 2
                    scroll_pos = max(0, min(1, (center_y - 100) / total_height))
                    canvas.yview_moveto(scroll_pos)
            except Exception as e:
                print(f"[Scroll] Error: {e}")

    def _highlight_with_page_conversion(self, canvas, region, color: str, pages: list, page_switch_func):
        """ページ相対座標でハイライト表示
        
        ★ Phase 44統合: page_idを直接使用（Y座標計算不要）
        - region.rect は既にページ相対座標
        - region.page_id でページを直接特定
        
        Args:
            canvas: 描画対象Canvas
            region: ハイライト対象のregion (rect, page_id属性を持つ)
            color: ハイライト色
            pages: ページ情報リスト [{'image': PIL.Image, ...}, ...]
            page_switch_func: 未使用（互換性のため残す）
        """
        if not region or not hasattr(region, 'rect') or not pages:
            print(f"[PageConvert] Skip: region={region is not None}, pages={len(pages) if pages else 0}")
            return
        
        # ★ Widget存在確認（Tkinterエラー防止）
        try:
            if not canvas or not canvas.winfo_exists():
                print("[PageConvert] Canvas does not exist, skipping")
                return
        except Exception:
            return
        
        x1, y1, x2, y2 = region.rect
        print(f"[PageConvert] rect (page-relative): [{x1}, {y1}, {x2}, {y2}]")
        
        # ★ Phase 44: page_idを直接使用（Y座標計算不要）
        page_id = getattr(region, 'page_id', 1)
        target_page = page_id - 1 if page_id > 0 else 0  # 1-indexed → 0-indexed
        
        print(f"[PageConvert] Using page_id={page_id}, target_page={target_page}")
        
        # ★ 現在のページと異なる場合のみ画像を切り替え
        current_page = getattr(self, 'current_page', 1)
        if page_id != current_page and target_page < len(pages):
            page_image = pages[target_page].get('image')
            if page_image:
                self._display_image(canvas, page_image)
                self.current_page = page_id
                print(f"[PageConvert] Switched to page {page_id}: {page_image.size}")
        else:
            print(f"[PageConvert] Already on page {current_page}, no switch needed")
        
        # 少し遅延してからハイライト描画（ページ表示完了を待つ）
        def delayed_highlight():
            # Widget存在確認
            try:
                if not canvas or not canvas.winfo_exists():
                    return
            except Exception:
                return
            
            # 既存のハイライトを削除
            canvas.delete("highlight")
            
            # ★ SUCCESS版: 直接scale_x/scale_yを使用
            scale_x = getattr(canvas, 'scale_x', 1.0)
            scale_y = getattr(canvas, 'scale_y', 1.0)
            
            sx1, sy1 = int(x1 * scale_x), int(y1 * scale_y)
            sx2, sy2 = int(x2 * scale_x), int(y2 * scale_y)
            
            print(f"[PageConvert] View coords: [{sx1}, {sy1}, {sx2}, {sy2}] scale=({scale_x:.3f},{scale_y:.3f})")
            
            # ハイライト矩形を描画
            canvas.create_rectangle(
                sx1, sy1, sx2, sy2,
                outline=color, width=4,
                tags="highlight"
            )
            
            # スクロール
            scrollregion = canvas.cget('scrollregion')
            if scrollregion:
                try:
                    parts = scrollregion.split()
                    total_height = float(parts[3]) if len(parts) >= 4 else 1
                    if total_height > 0:
                        center_y = (sy1 + sy2) / 2
                        scroll_pos = max(0, min(1, (center_y - 100) / total_height))
                        canvas.yview_moveto(scroll_pos)
                except Exception as e:
                    print(f"[PageConvert] Scroll error: {e}")
        
        # 100ms遅延でハイライト（ページ表示後）
        self._safe_after(100, delayed_highlight)


    def _highlight_bbox_on_canvas(self, canvas, bbox, color: str):
        """Canvas上で指定bboxをハイライト表示 + スクロール
        
        ★ 合理的アプローチ: オンデマンドでスケール計算
        - 元画像サイズとキャンバス表示サイズから動的に算出
        - 事前保存値に依存しない（同期ズレを防止）
        """
        if not bbox:
            print(f"[Highlight] SKIP: bbox is None")
            return

        # 既存のハイライトを削除
        canvas.delete("highlight")

        # 座標を取得
        x1, y1, x2, y2 = bbox
        print(f"[Highlight] INPUT bbox=({x1}, {y1}, {x2}, {y2})")

        # ★ 合理的アプローチ: キャンバス表示画像から動的にスケール計算
        try:
            # 1. 元画像サイズを取得（Web/PDFで判別）
            if canvas == self.web_canvas and hasattr(self, 'web_image') and self.web_image:
                orig_w, orig_h = self.web_image.size
            elif canvas == self.pdf_canvas and hasattr(self, 'pdf_image') and self.pdf_image:
                orig_w, orig_h = self.pdf_image.size
            else:
                print(f"[Highlight] WARN: No original image reference")
                orig_w, orig_h = 1, 1
            
            # 2. キャンバス上の表示画像サイズを取得
            if hasattr(canvas, 'image') and canvas.image:
                display_w = canvas.image.width()
                display_h = canvas.image.height()
            else:
                print(f"[Highlight] WARN: No displayed image")
                display_w, display_h = orig_w, orig_h
            
            # 3. オンデマンドでスケール計算
            scale_x = display_w / orig_w if orig_w > 0 else 1.0
            scale_y = display_h / orig_h if orig_h > 0 else 1.0
            
            print(f"[Highlight] orig=({orig_w}x{orig_h}), display=({display_w}x{display_h}), scale=({scale_x:.4f}, {scale_y:.4f})")
            
            # 4. 座標変換（オフセットなし - 画像は(0,0)配置）
            sx1 = x1 * scale_x
            sy1 = y1 * scale_y
            sx2 = x2 * scale_x
            sy2 = y2 * scale_y
            
        except Exception as e:
            print(f"[Highlight] ERROR calculating scale: {e}")
            sx1, sy1, sx2, sy2 = x1, y1, x2, y2
        
        print(f"[Highlight] canvas_rect=({sx1:.1f}, {sy1:.1f}, {sx2:.1f}, {sy2:.1f})")

        # ハイライト矩形を描画 (太い枠線 + 点線)
        canvas.create_rectangle(
            sx1, sy1, sx2, sy2,
            outline=color, width=4, dash=(8, 4),
            tags="highlight"
        )

        # 領域が見えるようにスクロール
        scrollregion = canvas.cget('scrollregion')
        if scrollregion:
            try:
                parts = scrollregion.split()
                total_height = float(parts[3]) if len(parts) >= 4 else 1
                if total_height > 0:
                    center_y = (sy1 + sy2) / 2
                    scroll_pos = max(0, min(1, (center_y - 100) / total_height))
                    canvas.yview_moveto(scroll_pos)
                    print(f"[Highlight] Scrolled to {scroll_pos:.2f}")
            except Exception as e:
                print(f"[Scroll] Error: {e}")

    def _handle_similar_search(self, pair):
        """類似検索: 同一ソース内でレイアウト類似領域を検出（StructurePropagator使用）"""
        print(f"\n{'='*50}")
        print(f"🔍 類似検索開始 (レイアウトベース): {pair.pdf_id}")
        print(f"{'='*50}")
        
        # ソース判定（PDF側を優先）
        source = "pdf"
        source_rect = getattr(pair, 'pdf_bbox', None)
        source_text = getattr(pair, 'pdf_text', '') or ''
        
        # rect情報を取得
        if not source_rect:
            for r in self.pdf_regions:
                if r.area_code == pair.pdf_id:
                    source_rect = r.rect
                    source_text = r.text
                    break
        
        if not source_rect:
            print("⚠️ 類似検索: ソース領域が見つかりません")
            self._safe_status("⚠️ 類似検索: ソース領域が見つかりません")
            return
        
        print(f"📐 テンプレート: rect={source_rect}, text={source_text[:50]}...")
        self._safe_status("🔍 レイアウト類似検索実行中...")
        
        try:
            from app.core.structure_propagator import StructurePropagator
            
            # raw_words と clusters を取得
            raw_words = getattr(self, 'pdf_raw_words', [])
            image = getattr(self, 'pdf_image', None)
            clusters = getattr(self, 'pdf_paragraphs', [])
            
            # raw_wordsがない場合はpdf_regionsから構築
            if not raw_words and self.pdf_regions:
                raw_words = [
                    {"rect": r.rect, "text": r.text}
                    for r in self.pdf_regions
                ]
            
            if not image:
                print("⚠️ 類似検索: 画像がありません")
                self._safe_status("⚠️ 類似検索: 画像がありません。先にOCRを実行してください")
                return
            
            # テンプレート情報
            template = {
                "rect": source_rect,
                "text": source_text
            }
            
            # StructurePropagator で類似領域検出
            propagator = StructurePropagator()
            page_size = (image.width, image.height)
            
            new_regions = propagator.propagate(
                template, raw_words, page_size,
                image=image, clusters=clusters
            )
            
            if new_regions:
                print(f"✅ 類似検索結果: {len(new_regions)}件のレイアウトパターン")
                
                # ★ 新機能: 検出領域をパラグラフリストに追加
                new_paragraph_objects = []
                
                for i, region_data in enumerate(new_regions):
                    rect = region_data.get('rect', source_rect)
                    score = region_data.get('score', 0)
                    anchor = region_data.get('anchor_word', '')
                    
                    # テキスト抽出（優先順位: region_data > pdf_regions > clusters > raw_words）
                    extracted_text = region_data.get('text', '')
                    
                    # ★ 修正: pdf_regions (元のOCR結果) から抽出
                    if not extracted_text and hasattr(self, 'pdf_regions'):
                        x1, y1, x2, y2 = rect
                        for existing_region in self.pdf_regions:
                            if hasattr(existing_region, 'rect'):
                                ex1, ey1, ex2, ey2 = existing_region.rect
                                # 矩形の重なり判定（IoU）
                                x_overlap = min(x2, ex2) - max(x1, ex1)
                                y_overlap = min(y2, ey2) - max(y1, ey1)
                                if x_overlap > 0 and y_overlap > 0:
                                    # 重なり面積の割合を計算
                                    overlap_area = x_overlap * y_overlap
                                    rect_area = (x2 - x1) * (y2 - y1)
                                    if rect_area > 0 and (overlap_area / rect_area) > 0.5:
                                        # 50%以上重なっていたら採用
                                        extracted_text = existing_region.text
                                        print(f"[DEBUG] Text extracted from existing region: {existing_region.area_code}")
                                        break
                    
                    # clustersから抽出を試みる
                    if not extracted_text and clusters:
                        x1, y1, x2, y2 = rect
                        for c in clusters:
                            c_rect = c.get('rect') if isinstance(c, dict) else getattr(c, 'rect', None)
                            if c_rect:
                                cx1, cy1, cx2, cy2 = c_rect
                                # 矩形の重なり判定
                                x_overlap = min(x2, cx2) - max(x1, cx1)
                                y_overlap = min(y2, cy2) - max(y1, cy1)
                                if x_overlap > 0 and y_overlap > 0:
                                    c_text = c.get('text', '') if isinstance(c, dict) else getattr(c, 'text', '')
                                    extracted_text += c_text
                    
                    # raw_wordsから抽出を試みる（最終手段）
                    if not extracted_text and raw_words and len(raw_words) > 1:
                        print(f"[DEBUG] Extracting from raw_words (total: {len(raw_words)})")
                        x1, y1, x2, y2 = rect
                        words_in_region = []
                        for w in raw_words:
                            if isinstance(w, dict):
                                wx1, wy1, wx2, wy2 = w.get('rect', [0,0,0,0])
                                cx = (wx1 + wx2) / 2
                                cy = (wy1 + wy2) / 2
                                if x1 <= cx <= x2 and y1 <= cy <= y2:
                                    words_in_region.append(w.get('text', ''))
                        extracted_text = ''.join(words_in_region)
                    
                    if extracted_text:
                        print(f"[DEBUG] ✓ Extracted text length: {len(extracted_text)}")
                    else:
                        print(f"[DEBUG] ✗ No text extracted for region {rect}")
                    
                    # EditableRegionオブジェクトを作成
                    area_code = f"PDF-SIM-{i+1:02d}"
                    
                    new_region = EditableRegion(
                        id=len(self.pdf_regions) + i + 1,
                        rect=rect,
                        text=extracted_text or f"[No Text - {anchor}]",  # 空の場合はアンカー情報を使用
                        area_code=area_code,
                        sync_number=None,
                        similarity=0.0,
                        source=source
                    )
                    new_region.sync_color = "#FFEB3B"  # 黄色（類似検出由来）
                    new_paragraph_objects.append(new_region)
                    
                    print(f"   📌 #{i+1}: {area_code}, rect={rect}, score={score:.2f}, text='{extracted_text[:50] if extracted_text else '[EMPTY]'}...'")
                    
                    # キャンバスにハイライト
                    self._highlight_rect_on_canvas(self.pdf_canvas, rect, "#FFEB3B")
                
                # パラグラフリストに追加
                if source == "pdf":
                    self.pdf_regions.extend(new_paragraph_objects)
                    print(f"📝 PDF領域リストに{len(new_paragraph_objects)}件追加 (合計: {len(self.pdf_regions)}件)")
                else:
                    self.web_regions.extend(new_paragraph_objects)
                    print(f"📝 Web領域リストに{len(new_paragraph_objects)}件追加 (合計: {len(self.web_regions)}件)")
                
                # ★ Sync再計算
                print("🔄 Sync再計算中...")
                self._safe_status("🔄 類似レイアウトからパラグラフ生成中...")
                self._recalculate_sync()
                
                # ★ スプレッドシート更新
                self._refresh_inline_spreadsheet()
                
                # 領域再描画
                self._redraw_regions()
                
                self._safe_status(
                    f"✅ 類似検索完了: {len(new_regions)}件検出 → パラグラフ追加 → Sync再計算完了"
                )
            else:
                print("ℹ️ 類似検索: 類似レイアウトなし")
                self._safe_status("ℹ️ 類似レイアウトが見つかりませんでした")
                
                
        except Exception as e:
            print(f"❌ 類似検索エラー: {e}")
            import traceback
            traceback.print_exc()
            self._safe_status(f"❌ 類似検索エラー: {e}")



    
    def _handle_match_search(self, pair):
        """マッチ検索: 対向ソース（PDF→Web）で同じ文言を含むパラグラフを検出（GeminiAutoMatcher使用）"""
        print(f"\n{'='*50}")
        print(f"🎯 マッチ検索開始 (テキストベース): {pair.pdf_id}")
        print(f"{'='*50}")
        
        # PDFソースのテキストを取得
        source_text = getattr(pair, 'pdf_text', '') or ''
        source_id = pair.pdf_id
        if not source_text:
            for r in self.pdf_regions:
                if r.area_code == pair.pdf_id:
                    source_text = r.text
                    break
        
        if not source_text:
            print("⚠️ マッチ検索: ソーステキストが見つかりません")
            self._safe_status("⚠️ マッチ検索: ソーステキストが見つかりません")
            return
        
        print(f"📝 PDF検索元: [{source_id}] ({len(source_text)}文字)")
        print(f"   テキスト: {source_text[:80]}...")
        self._safe_status(f"🎯 マッチ検索中: '{source_text[:30]}...' → Web側")
        
        try:
            from app.sdk.similarity import GeminiAutoMatcher
            
            # デバッグ: Web領域の数を確認
            print(f"[DEBUG] Total web_regions: {len(self.web_regions)}")
            print(f"[DEBUG] web_regions with text: {len([r for r in self.web_regions if r.text and r.text.strip()])}")
            
            # Web領域を候補としてフォーマット
            candidates = []
            for r in self.web_regions:
                if r.text and r.text.strip():
                    candidates.append({
                        "id": r.area_code,
                        "text": r.text,
                        "rect": r.rect
                    })
                    print(f"[DEBUG] Web candidate: {r.area_code}, text_len={len(r.text)}")
            
            if not candidates:
                print("⚠️ マッチ検索: Web側に領域がありません")
                print(f"[DEBUG] self.web_regions = {self.web_regions}")
                self._safe_status("⚠️ マッチ検索: Web側に領域がありません。先にAI分析を実行してください")
                return
            
            print(f"🔎 Web側候補: {len(candidates)}件")
            
            # GeminiAutoMatcher でマッチング
            matcher = GeminiAutoMatcher()
            results = matcher.find_matching_paragraphs(
                source_text, candidates, threshold=0.4, top_k=5
            )
            
            if results:
                print(f"✅ マッチ検索結果: {len(results)}件")
                
                # 最も類似度の高い結果
                best_match = results[0]
                print(f"   🎯 Best Match: [{best_match.paragraph_id}] {best_match.similarity_score:.0%}")
                print(f"      PDF: '{source_text[:40]}...'")
                print(f"      Web: '{best_match.paragraph_text[:40]}...'")
                
                for r in results:
                    print(f"   📌 [{r.paragraph_id}]: {r.similarity_score:.0%}")
                    
                    # Web側でハイライト表示
                    for region in self.web_regions:
                        if region.area_code == r.paragraph_id:
                            # 最良=緑/太枠、他=黄色
                            color = "#00FF00" if r == best_match else "#FFEB3B"
                            self._highlight_region_on_canvas(self.web_canvas, region, color)
                            break
                
                # テキストボックスにも反映（詳細表示）
                if hasattr(self, 'web_text_box') and best_match:
                    self.web_text_box.delete("1.0", "end")
                    detail = f"🎯 マッチ結果: {best_match.similarity_score:.0%}\n"
                    detail += f"━━━━━━━━━━━━━━━━━━━━\n"
                    detail += f"📄 PDF [{source_id}]:\n{source_text[:200]}\n\n"
                    detail += f"🌐 Web [{best_match.paragraph_id}]:\n{best_match.paragraph_text[:200]}"
                    self.web_text_box.insert("1.0", detail)
                
                # ステータス：何に対する何のマッチかを明示
                self._safe_status(
                    f"✅ PDF [{source_id}] → Web [{best_match.paragraph_id}]: "
                    f"{best_match.similarity_score:.0%}マッチ"
                )
            else:
                print("ℹ️ マッチ検索: マッチなし")
                self._safe_status(f"ℹ️ '{source_text[:20]}...' に類似するWebパラグラフなし")
                
        except ImportError as e:
            # GeminiAutoMatcher がない場合はEmbeddingSimilarSearchにフォールバック
            print(f"⚠️ GeminiAutoMatcher not found, falling back to EmbeddingSimilarSearch")
            self._handle_match_search_fallback(pair, source_text)
        except Exception as e:
            print(f"❌ マッチ検索エラー: {e}")
            import traceback
            traceback.print_exc()
            self._safe_status(f"❌ マッチ検索エラー: {e}")
    
    def _handle_match_search_fallback(self, pair, source_text):
        """マッチ検索フォールバック: EmbeddingSimilarSearch使用"""
        try:
            from app.sdk.similarity import EmbeddingSimilarSearch
            
            search = EmbeddingSimilarSearch(threshold=0.5)
            candidates = [
                {"id": r.area_code, "text": r.text, "rect": r.rect}
                for r in self.web_regions if r.text and r.text.strip()
            ]
            
            if not candidates:
                self._safe_status("⚠️ Web側に領域がありません")
                return
            
            results = search.find_similar(source_text, candidates, top_k=3)
            
            if results:
                best = results[0]
                for r in results:
                    for region in self.web_regions:
                        if region.area_code == r.candidate_id:
                            color = "#00FF00" if r == best else "#FFEB3B"
                            self._highlight_region_on_canvas(self.web_canvas, region, color)
                            break
                self._safe_status(f"✅ マッチ検索完了: {best.similarity_score:.0%}")
            else:
                self._safe_status("ℹ️ 類似パラグラフなし")
        except Exception as e:
            self._safe_status(f"❌ フォールバックエラー: {e}")
    
    def _highlight_rect_on_canvas(self, canvas, rect, color="#FFEB3B"):
        """Draw highlight for a raw rect with page-safe normalization."""
        try:
            if not canvas or not rect or len(rect) < 4:
                return

            source = "web" if canvas == getattr(self, "web_canvas", None) else "pdf" if canvas == getattr(self, "pdf_canvas", None) else "web"
            x1, y1, x2, y2 = [int(v) for v in rect]
            normalized = [x1, y1, x2, y2]

            if source == "pdf":
                page_id = int(getattr(self, "current_pdf_idx", 0) or 0) + 1
                page_h = self._get_page_height_for_source("pdf", page_id)
                # if this rect looks global, convert to local for current page
                if page_h > 0 and y2 > page_h + 2:
                    y_off = self._get_page_y_offset_for_source("pdf", page_id)
                    normalized = [x1, y1 - y_off, x2, y2 - y_off]
                clipped = self._clip_rect_to_page(normalized, "pdf", page_id)
                if clipped is None:
                    return
                normalized = clipped

            from app.gui.sdk.coord_transform import get_canvas_transform
            transform = get_canvas_transform(canvas)
            sx1, sy1, sx2, sy2 = transform.src_rect_to_view(normalized[0], normalized[1], normalized[2], normalized[3])

            canvas.create_rectangle(
                sx1, sy1, sx2, sy2,
                outline=color, width=3,
                tags="similar_highlight"
            )
        except Exception as e:
            print(f"[_highlight_rect_on_canvas] Error: {e}")

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
        
        # ★ PAGE-AWARE FIX: ページリストを渡す（ステッチではなく）
        # region.page_idで正しいページ画像を選択
        web_pages_list = getattr(self, 'web_pages', None)
        pdf_pages_list = getattr(self, 'pdf_pages_list', None)  # Fix: pdf_pages_list -> pdf_pages
        
        # フォールバック用にステッチ画像も渡す (キャッシュを使用)
        web_stitch = self._web_stitch_cache
        pdf_stitch = self._pdf_stitch_cache
        
        # キャッシュがない場合は生成 (安全策)
        if not web_stitch and hasattr(self, 'web_pages') and self.web_pages:
             print("[_refresh] ⚠️ Web Stitch Cache Missing, regenerating...")
             web_stitch = self._stitch_pages_vertically([p['image'] for p in self.web_pages])
             self._web_stitch_cache = web_stitch
             
        if not pdf_stitch and hasattr(self, 'pdf_stitched_groups') and self.pdf_stitched_groups:
             # Group mode fallback
             pdf_stitch = self.pdf_stitched_groups[getattr(self, 'current_pdf_group_idx', 0)]['image']
        elif not pdf_stitch and hasattr(self, 'pdf_pages_list') and self.pdf_pages_list:
             print("[_refresh] ⚠️ PDF Stitch Cache Missing, regenerating...")
             pdf_stitch = self._stitch_pages_vertically([p['image'] for p in self.pdf_pages_list])
             self._pdf_stitch_cache = pdf_stitch
        
        print(f"[_refresh_inline_spreadsheet] web_pages={len(web_pages_list) if web_pages_list else 0}, pdf_pages={len(pdf_pages_list) if pdf_pages_list else 0}")
        print(f"[_refresh_inline_spreadsheet] sync_pairs={len(self.sync_pairs)}, web_regions={len(getattr(self, 'web_regions', []))}, pdf_regions={len(getattr(self, 'pdf_regions', []))}")

        if hasattr(self, 'spreadsheet_panel'):
            try:
                self.spreadsheet_panel.update_data(
                    self.sync_pairs,
                    self.web_regions,
                    self.pdf_regions,
                    web_stitch,  # フォールバック用
                    pdf_stitch,   # フォールバック用
                    web_pages_list, # ★ Page-Aware Data
                    pdf_pages_list  # ★ Page-Aware Data
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
        スマートリサイズハンドラ（最適化版）
        - サイズ変化を検知して必要な場合のみ再描画
        - 150msのデバウンスでリサイズ完了を待機（300ms→150msに短縮）
        - キャッシュで同一サイズの再計算を回避
        """
        # 描画中はスキップ
        if getattr(self, '_display_in_progress', False):
            return

        # 最小サイズチェック
        if event.width < 50 or event.height < 50:
            return

        # サイズ変化チェック（5px以上の変化のみ処理 - 10px→5pxに緩和）
        current_size = (event.width, event.height)
        last_size = self._last_canvas_size.get(source, (0, 0))
        if abs(current_size[0] - last_size[0]) < 5 and abs(current_size[1] - last_size[1]) < 5:
            return

        # 前回のジョブをキャンセル
        if self._resize_job:
            self.after_cancel(self._resize_job)

        # 150ms後に再描画（リサイズ完了を待機 - レスポンス性向上）
        def _smart_redisplay():
            self._resize_job = None
            self._execute_smart_resize()

        self._resize_job = self.after(150, _smart_redisplay)

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

        # キャッシュ選択（Web/PDF）
        cache = self._image_cache_web if source == "web" else self._image_cache_pdf

        # キャッシュキー生成（サイズ + source別モード + 画像ハッシュ）
        image_hash = id(image)  # PIL ImageのIDをハッシュとして使用
        mode = self.display_mode_by_source.get(source, "cover" if source == "web" else "fit")
        cache_key = (canvas_width, canvas_height, mode, image_hash)

        # キャッシュ確認
        cached_entry = cache.get(cache_key)

        if cached_entry:
            # キャッシュヒット：PhotoImageを再利用（LRU）
            try:
                vy = canvas.yview()
                vx = canvas.xview()
                saved_y = vy[0] if vy else 0.0
                saved_x = vx[0] if vx else 0.0
            except Exception:
                saved_y, saved_x = 0.0, 0.0

            canvas.delete("image")

            photo = cached_entry.photo
            draw_x = int(-(cached_entry.offset_x or 0))
            draw_y = int(-(cached_entry.offset_y or 0))
            canvas.create_image(draw_x, draw_y, anchor="nw", image=photo, tags="image")
            canvas.tag_lower("image")
            canvas.image = photo

            from app.gui.sdk.coord_transform import CanvasTransform
            canvas._coord_tf = CanvasTransform(
                scale_x=cached_entry.scale,
                scale_y=cached_entry.scale,
                offset_x=cached_entry.offset_x,
                offset_y=cached_entry.offset_y
            )

            region_w = max(canvas_width, draw_x + cached_entry.width)
            region_h = max(canvas_height, draw_y + cached_entry.height)
            canvas.configure(scrollregion=(0, 0, region_w, region_h))
            try:
                canvas.yview_moveto(saved_y)
                canvas.xview_moveto(saved_x)
            except Exception:
                pass

            # キャッシュ統計をログ出力（デバッグ用）
            stats = cache.get_stats()
            if stats['hits'] % 10 == 0:  # 10ヒットごとに統計表示
                print(f"📊 {source.upper()} Cache: {stats['hit_rate']:.1%} hit rate "
                      f"({stats['size']}/{stats['max_size']} entries, "
                      f"{stats['memory_mb']:.1f}MB)")

            # B5 fix: キャッシュヒット後もリージョンを再描画する
            # （_execute_smart_resize 経由でない直接呼び出し時にリージョンが消えるのを防ぐ）
            if hasattr(self, 'web_regions') and hasattr(self, 'pdf_regions'):
                if self.web_regions or self.pdf_regions:
                    self._redraw_regions()
            return

        # キャッシュミス：新規生成
        self._display_image(canvas, image)

        # LRUキャッシュに保存
        cache.put(
            key=cache_key,
            photo=canvas.image,
            pil_image=image,  # PIL Imageも保持
            scale=canvas.scale_x,
            offset_x=canvas.offset_x,
            offset_y=canvas.offset_y,
            width=int(image.width * canvas.scale_x),
            height=int(image.height * canvas.scale_y)
        )

    def _clear_image_cache(self, source: str = None):
        """画像キャッシュをクリア（画像変更時に呼び出す）"""
        if source == "web":
            self._image_cache_web.clear()
            print("🗑️ Web image cache cleared")
        elif source == "pdf":
            self._image_cache_pdf.clear()
            print("🗑️ PDF image cache cleared")
        else:
            # 両方クリア
            self._image_cache_web.clear()
            self._image_cache_pdf.clear()
            print("🗑️ All image caches cleared")


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
        """Keep source tab display and controls consistent."""
        current_tab = self.view_tabs.get()

        if current_tab == "Web Source":
            self.primary_source = "web"
            if getattr(self, "web_image", None) and hasattr(self, "web_canvas"):
                self.after(80, lambda: self._display_image(self.web_canvas, self.web_image))

            total_web = len(getattr(self, "web_pages", []) or [])
            if total_web <= 0:
                total_web = len(getattr(self, "page_regions", []) or [])
            total_web = total_web if total_web > 0 else 1
            cur_web = int(getattr(self, "current_page", 1) or 1)
            if hasattr(self, "page_label") and self.page_label.winfo_exists():
                self.page_label.configure(text=f"Page {cur_web} / {total_web}")

        elif current_tab == "PDF Source":
            self.primary_source = "pdf"
            pdf_pages = getattr(self, "pdf_pages_list", None) or getattr(self, "pdf_pages", None) or []
            if pdf_pages and hasattr(self, "pdf_canvas"):
                cur_idx = int(getattr(self, "current_pdf_idx", 0) or 0)
                if cur_idx < 0 or cur_idx >= len(pdf_pages):
                    self.current_pdf_idx = 0
                self._display_single_pdf_page()
                self.after(180, self._display_single_pdf_page)
            elif getattr(self, "pdf_image", None) and hasattr(self, "pdf_canvas"):
                self._display_image(self.pdf_canvas, self.pdf_image)
                self.after(180, lambda: self._display_image(self.pdf_canvas, self.pdf_image))

            total_pdf = len(pdf_pages) if len(pdf_pages) > 0 else 1
            cur_pdf = int(getattr(self, "current_pdf_idx", 0) or 0) + 1
            if cur_pdf < 1:
                cur_pdf = 1
            if hasattr(self, "page_label") and self.page_label.winfo_exists():
                self.page_label.configure(text=f"Page {cur_pdf} / {total_pdf}")
            if hasattr(self, "pdf_page_label") and self.pdf_page_label.winfo_exists():
                self.pdf_page_label.configure(text=f"Page {cur_pdf} / {total_pdf}")

        self._update_display_mode_buttons()

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
        elif hasattr(self, 'pdf_pages') and self.pdf_pages:
            idx = getattr(self, 'current_pdf_idx', 0)
            if idx < len(self.pdf_pages) - 1:
                self.current_pdf_idx = idx + 1
                self._display_single_pdf_page()
        else:
            print(f"[_next_pdf_page] PDFデータが利用できません")
    
    def _display_single_pdf_page(self):
        """Display one PDF page."""
        pdf_pages = getattr(self, "pdf_pages_list", None) or getattr(self, "pdf_pages", None) or []
        if not pdf_pages:
            return
        idx = getattr(self, "current_pdf_idx", 0)
        if 0 <= idx < len(pdf_pages):
            page = pdf_pages[idx]
            self.pdf_image = page.get("image")
            if self.pdf_image:
                self._clear_image_cache("pdf")
                self._display_image(self.pdf_canvas, self.pdf_image)
                self.pdf_page_label.configure(text=f"Page {idx+1} / {len(pdf_pages)}")
                print(f"[_display_single_pdf_page] Showing page {idx+1}")

                # Keep global data; only clear visible text box.
                if hasattr(self, "pdf_text_box"):
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
                text=f"{group['page_range']}/{len(getattr(self, 'pdf_pages', []))}"
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
            
        # ★ ByCursor Fix: web_pages_listを同期
        self.web_pages_list = self.web_pages
            
        # ★ Webステッチ画像をキャッシュ (初回のみ)
        if self.web_pages:
            print("[Cache] Generating Web Stitch Cache...")
            self._web_stitch_cache = self._stitch_pages_vertically([p['image'] for p in self.web_pages])
            print(f"[Cache] Web Stitch Generated: {self._web_stitch_cache.size}")
    
    def _load_pdf_data(self):
        """PDFデータをロード - 全ページを収集"""
        self.pdf_pages = []  # List of dicts with image, title
        
        # UnifiedAppにselected_pdf_pagesがあるかチェック (メイン)
        if hasattr(self.parent_app, 'selected_pdf_pages') and self.parent_app.selected_pdf_pages:
            print(f"📄 PDF読み込み: {len(self.parent_app.selected_pdf_pages)}ページ検出")
            for i, img in enumerate(self.parent_app.selected_pdf_pages):
                self.pdf_pages.append({
                    'image': img,
                    'title': f'PDF ページ {i+1}'
                })
        
        # selected_pdf_pagesが空の場合はcomparison_queueから取得
        if not self.pdf_pages and hasattr(self.parent_app, 'comparison_queue'):
            pdf_items = [item for item in self.parent_app.comparison_queue if item.get('type') == 'pdf']
            print(f"📄 Queue からPDF読み込み: {len(pdf_items)}ページ")
            
            for item in pdf_items:
                img_b64 = item.get('image_base64')
                if img_b64:
                    try:
                        img_data = base64.b64decode(img_b64)
                        img = Image.open(io.BytesIO(img_data))
                        self.pdf_pages.append({
                            'image': img,
                            'title': item.get('title', f"PDF ページ {len(self.pdf_pages)+1}")
                        })
                    except Exception as e:
                        print(f"PDF画像読み込みエラー: {e}")
        
        # ★ PDFステッチ画像をキャッシュ (初回のみ)
        if self.pdf_pages:
            print("[Cache] Generating PDF Stitch Cache...")
            self._pdf_stitch_cache = self._stitch_pages_vertically([p['image'] for p in self.pdf_pages])
            print(f"[Cache] PDF Stitch Generated: {self._pdf_stitch_cache.size}")
        
        print(f"📄 PDF合計: {len(self.pdf_pages)}ページ")
        
        # ★ ByCursor Fix: pdf_pages_listを同期
        self.pdf_pages_list = self.pdf_pages
        
        # 10ページごとに縦連結した画像を作成
        # ★ Stitch-Localism Migration: Disable Stitching to enforce Single Page View for Accuracy
        # if self.pdf_pages_list:
        #     self.pdf_stitched_groups = []  # 10ページごとのグループ
        #     pages_per_group = 10
        #     
        #     for group_idx in range(0, len(self.pdf_pages_list), pages_per_group):
        #         group_pages = self.pdf_pages_list[group_idx:group_idx + pages_per_group]
        #         stitched_img = self._stitch_pages_vertically([p['image'] for p in group_pages])
        #         self.pdf_stitched_groups.append({
        #             'image': stitched_img,
        #             'page_range': f"{group_idx + 1}-{min(group_idx + pages_per_group, len(self.pdf_pages_list))}"
        #         })
        
        # 強制的にSingle Page Modeにするため、stitched_groupsは空にする
        self.pdf_stitched_groups = []
        
        # 最初のページを表示
        if self.pdf_pages_list:
            self.current_pdf_idx = 0
            self._display_single_pdf_page()
            
        self.status_label.configure(
            text=f"✅ Web: {len(getattr(self, 'web_pages', []))}p | PDF: {len(self.pdf_pages_list)}p (Single Page Mode)"
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
        
        # ★ Phase 44: リージョンはクリアせず、page_id でフィルタして再描画
        # self.web_regions = []  # ← 削除：全リージョンを保持
        self.current_page = idx + 1  # ★ 現在ページを更新
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
            canvas.update_idletasks()

            # Save scroll position before redraw (restore after to avoid flicker)
            try:
                vy = canvas.yview()
                vx = canvas.xview()
                saved_y = vy[0] if vy else 0.0
                saved_x = vx[0] if vx else 0.0
            except Exception:
                saved_y, saved_x = 0.0, 0.0

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
            # タブ非表示時は高さが極端に小さい値になるため、ウィンドウ高さから推定
            if canvas_height <= 300:
                window_height = self.winfo_height()
                if window_height > 600:
                    estimated_height = window_height - 200
                    canvas_height = max(estimated_height, 400)
                    print(f"[_display_image] Using window height: {window_height} -> canvas_height: {canvas_height}")
            if canvas_height <= 1:
                parent = canvas.master
                if parent:
                    canvas_height = parent.winfo_height()
            if canvas_height <= 1:
                canvas_height = max(self.winfo_height() - 200, 300)
            canvas_height = max(canvas_height, 300)

            canvas_source = "web" if canvas == self.web_canvas else "pdf" if canvas == self.pdf_canvas else "unknown"
            effective_mode = self._resolve_display_mode(canvas_source, image.size, (canvas_width, canvas_height))
            print(f"[_display_image] canvas={canvas_width}x{canvas_height}, image={image.size}, mode={effective_mode}")

            # FR-01: scale by selected mode
            img_copy = image.copy()
            scale_x = canvas_width / img_copy.width
            scale_y = canvas_height / img_copy.height

            if effective_mode == "cover":
                scale_factor = max(scale_x, scale_y)
            elif effective_mode == "fit":
                # Width-priority fit for source panes: keep x contract stable and scroll vertically.
                scale_factor = scale_x
            else:
                scale_factor = min(scale_x, scale_y)

            # For PDF fit mode, honor exact fit scale to keep page/overlay contracts consistent.
            # (minimum-scale forcing can visually desync image-size expectation from [PDF:Fit]).
            if canvas_source == "pdf" and effective_mode != "fit" and scale_factor < 0.28:
                print(f"[_display_image] PDF scale too small ({scale_factor:.3f}), applying minimum scale 0.28")
                scale_factor = 0.28

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

            # Fit mode is centered to reduce one-sided black area and click confusion.
            draw_x = 0
            draw_y = 0
            if effective_mode == "fit":
                if new_width < canvas_width:
                    draw_x = int((canvas_width - new_width) // 2)
                # Keep top-aligned for deterministic y offsets across pages.
                draw_y = 0

            canvas.create_image(draw_x, draw_y, anchor="nw", image=photo, tags="image")
            canvas.tag_lower("image")
            canvas.image = photo

            # Keep scrollregion covering both viewport and rendered image.
            region_w = max(canvas_width, draw_x + new_width)
            region_h = max(canvas_height, draw_y + new_height)
            canvas.configure(scrollregion=(0, 0, region_w, region_h))

            # Restore scroll position if we had one (avoid forced reset)
            try:
                canvas.yview_moveto(saved_y)
                canvas.xview_moveto(saved_x)
            except Exception:
                pass

            # CanvasTransform uses src * scale - offset, so centered draw needs negative offsets.
            offset_x = -draw_x
            offset_y = -draw_y
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
            canvas.source_width = image.width
            canvas.source_height = image.height

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

    def _toggle_display_mode(self, source: Optional[str] = None):
        """FR-01: Cover/Fit/Smart mode toggle by source."""
        src = (source or str(getattr(self, "primary_source", "web") or "web")).lower()
        if src not in ("web", "pdf"):
            src = "web"

        modes = ["cover", "fit", "smart"]
        current = self.display_mode_by_source.get(src, "cover" if src == "web" else "fit")
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 0
        next_mode = modes[(idx + 1) % len(modes)]
        self.display_mode_by_source[src] = next_mode

        # backward compatibility field
        self.display_mode = self.display_mode_by_source.get("web", "cover")

        self._update_display_mode_buttons()
        self._clear_image_cache(src)

        if src == "web" and getattr(self, "web_image", None):
            self._display_image(self.web_canvas, self.web_image)
        elif src == "pdf" and getattr(self, "pdf_image", None):
            self._display_image(self.pdf_canvas, self.pdf_image)

        self._redraw_regions()

    def _update_display_mode_buttons(self):
        """Update Web/PDF display mode button labels."""
        web_mode = self.display_mode_by_source.get("web", "cover")
        pdf_mode = self.display_mode_by_source.get("pdf", "fit")

        if hasattr(self, "web_display_mode_btn") and self.web_display_mode_btn:
            self.web_display_mode_btn.configure(text=f"[Web:{web_mode.capitalize()}]")

        if hasattr(self, "pdf_display_mode_btn") and self.pdf_display_mode_btn:
            self.pdf_display_mode_btn.configure(text=f"[PDF:{pdf_mode.capitalize()}]")

    def _resolve_display_mode(self, source: str, image_size: Tuple[int, int], viewport_size: Tuple[int, int]) -> str:
        """Resolve effective mode for mixed-size sources on one window."""
        src = str(source or "web").lower()
        mode = self.display_mode_by_source.get(src, "cover" if src == "web" else "fit")
        if mode != "smart":
            return mode

        iw, ih = image_size
        vw, vh = viewport_size
        if iw <= 0 or ih <= 0 or vw <= 0 or vh <= 0:
            return "fit"

        tall_ratio = ih / max(iw, 1)
        viewport_ratio = vh / max(vw, 1)

        # Avoid tiny rendering for very tall web screenshots.
        if src == "web":
            return "cover" if tall_ratio > max(2.4, viewport_ratio * 2.0) else "fit"

        # PDF keeps fit for stable readability/coordinates.
        return "fit"

    def _toggle_scroll_sync(self):
        """スクロール同期のON/OFF切り替え（業務配布対応）"""
        if hasattr(self, '_scroll_sync_manager'):
            state = self._scroll_sync_manager.toggle()
            status = "🔗 同期ON" if state else "🔓 同期OFF"

            # ステータス表示（あれば）
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.configure(text=f"スクロール同期: {status}")

            print(f"  {status}")
            return state
        else:
            print("⚠️ Scroll sync manager not initialized")
            return False

    def _get_pages_for_source(self, source: str):
        if source == "web":
            pages = getattr(self, "web_pages_list", None) or getattr(self, "web_pages", None)
        else:
            pages = getattr(self, "pdf_pages_list", None) or getattr(self, "pdf_pages", None)
        return pages or []

    def _get_current_page_for_source(self, source: str) -> int:
        if source == "web":
            return int(getattr(self, "current_page", 1) or 1)
        if hasattr(self, "current_pdf_idx"):
            return int(getattr(self, "current_pdf_idx", 0) or 0) + 1
        return int(getattr(self, "current_page", 1) or 1)

    def _get_page_height_for_source(self, source: str, page_id: Optional[int]) -> int:
        if not page_id or page_id < 1:
            return 0
        pages = self._get_pages_for_source(source)
        if page_id > len(pages):
            return 0
        try:
            item = pages[page_id - 1]
            if isinstance(item, dict):
                img = item.get("image")
                return int(getattr(img, "height", 0) or 0)
        except Exception:
            pass
        return 0

    def _get_page_width_for_source(self, source: str, page_id: Optional[int]) -> int:
        if not page_id or page_id < 1:
            return 0
        pages = self._get_pages_for_source(source)
        if page_id > len(pages):
            return 0
        try:
            item = pages[page_id - 1]
            if isinstance(item, dict):
                img = item.get("image")
                return int(getattr(img, "width", 0) or 0)
        except Exception:
            pass
        return 0

    def _clip_rect_to_page(self, rect, source: str, page_id: Optional[int]):
        if not rect or len(rect) < 4:
            return None
        page_w = self._get_page_width_for_source(source, page_id)
        page_h = self._get_page_height_for_source(source, page_id)
        if page_w <= 0 or page_h <= 0:
            return [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]

        x1 = max(0, min(int(rect[0]), page_w - 1))
        y1 = max(0, min(int(rect[1]), page_h - 1))
        x2 = max(0, min(int(rect[2]), page_w))
        y2 = max(0, min(int(rect[3]), page_h))

        if x2 <= x1 + 1 or y2 <= y1 + 1:
            return None
        return [x1, y1, x2, y2]

    def _get_page_y_offset_for_source(self, source: str, page_id: Optional[int]) -> int:
        if not page_id or page_id <= 1:
            return 0
        pages = self._get_pages_for_source(source)
        if not pages:
            return 0

        y_offset = 0
        limit = min(page_id - 1, len(pages))
        for idx in range(limit):
            item = pages[idx]
            if not isinstance(item, dict):
                continue
            img = item.get("image")
            y_offset += int(getattr(img, "height", 0) or 0)
        return y_offset

    def _infer_region_page_id(self, region, source: str) -> Optional[int]:
        page_id = getattr(region, "page_id", None)
        if isinstance(page_id, int) and page_id > 0:
            return page_id

        area_code = str(getattr(region, "area_code", "") or "")

        if source == "web":
            for pat in (r"^P(\d+)-", r"^W(\d+)-"):
                match = re.search(pat, area_code)
                if match:
                    try:
                        return int(match.group(1))
                    except Exception:
                        pass
            return None

        # PDF: avoid parsing plain "P-001" as page number (it is often sequence-only).
        for pat in (r"^P(\d+)-\d+", r"^PDF-P(\d+)-"):
            match = re.search(pat, area_code)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    pass

        # fallback: infer from stitched offset if available
        try:
            y_off = int(getattr(region, "stitched_y_offset", 0) or 0)
            pages = self._get_pages_for_source("pdf")
            if y_off > 0 and pages:
                accum = 0
                for idx, item in enumerate(pages, start=1):
                    img = item.get("image") if isinstance(item, dict) else None
                    h = int(getattr(img, "height", 0) or 0)
                    if accum == y_off:
                        return idx
                    accum += h
        except Exception:
            pass

        # In paged PDF mode, unknown page regions must stay unknown.
        # Returning current page here leaks cross-page/unknown regions into view.
        return None

    def _get_region_coord_system(self, region) -> str:
        coord = str(getattr(region, "coord_system", "") or "").lower()
        if coord in ("local", "global"):
            return coord

        if int(getattr(region, "stitched_y_offset", 0) or 0) > 0:
            return "global"

        # Legacy heuristic: if bbox exceeds page height, treat as stitched/global.
        source = str(getattr(region, "source", "") or "").lower() or "web"
        page_id = self._infer_region_page_id(region, source)
        page_h = self._get_page_height_for_source(source, page_id)
        rect = list(getattr(region, "rect", [0, 0, 0, 0]) or [0, 0, 0, 0])
        if page_h > 0 and len(rect) >= 4 and rect[3] > page_h + 2:
            return "global"

        return "local"

    def _normalize_region_rect_for_current_view(self, region, source: str):
        rect = list(getattr(region, "rect", [0, 0, 0, 0]) or [0, 0, 0, 0])
        if len(rect) < 4:
            return rect

        page_id = self._infer_region_page_id(region, source)
        stitched_attr = int(getattr(region, "stitched_y_offset", 0) or 0)
        stitched_calc = self._get_page_y_offset_for_source(source, page_id)
        coord_system = self._get_region_coord_system(region)

        # In stitched PDF view, draw in global coordinates.
        if source == "pdf" and getattr(self, "pdf_stitched_groups", None):
            if coord_system == "local":
                for y_off in (stitched_attr, stitched_calc):
                    if y_off > 0:
                        global_rect = [rect[0], rect[1] + y_off, rect[2], rect[3] + y_off]
                        if global_rect[2] > global_rect[0] and global_rect[3] > global_rect[1]:
                            return global_rect
            return rect

        # In page view, local coordinates are canonical and must be clipped.
        if coord_system == "local":
            clipped = self._clip_rect_to_page(rect, source, page_id)
            return clipped if clipped is not None else [0, 0, 0, 0]

        # global -> local conversion using possible offsets.
        candidates = []
        for y_off in (stitched_attr, stitched_calc):
            if y_off > 0 and y_off not in candidates:
                candidates.append(y_off)

        for y_off in candidates:
            local_rect = [rect[0], rect[1] - y_off, rect[2], rect[3] - y_off]
            if local_rect[2] <= local_rect[0] or local_rect[3] <= local_rect[1]:
                continue
            clipped = self._clip_rect_to_page(local_rect, source, page_id)
            if clipped is not None:
                return clipped

        # If conversion fails in paged PDF mode, drop the region from drawing.
        if source == "pdf":
            return [0, 0, 0, 0]

        return rect

    def _filter_regions_for_current_view(self, regions, source: str):
        if not regions:
            return []

        if source == "pdf" and getattr(self, "pdf_stitched_groups", None):
            return list(regions)

        pages = self._get_pages_for_source(source)
        current_page = self._get_current_page_for_source(source)
        if not pages:
            return list(regions)

        filtered = []
        for region in regions:
            page_id = self._infer_region_page_id(region, source)
            if page_id is None or page_id < 1:
                # In paged mode, unknown page regions are hidden to avoid cross-page clutter.
                continue
            if page_id == current_page:
                filtered.append(region)
        return filtered

    def _redraw_regions(self):
        """Redraw regions with page-aware filtering and rect normalization."""
        try:
            print(f"[_redraw_regions] web_regions={len(self.web_regions)}, pdf_regions={len(self.pdf_regions)}")

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

                canvas.delete("region")
                if not regions:
                    print(f"[_redraw_regions] {source} has no regions, skipping")
                    if source == "pdf":
                        print("[PDF_OVERLAY] skip: no regions")
                    continue

                filtered_regions = self._filter_regions_for_current_view(regions, source)
                normalized_regions = self._get_normalized_regions_for_source(source, canvas=canvas)
                current_page = self._get_current_page_for_source(source)
                print(
                    f"[_redraw_regions] {source}: page={current_page}, "
                    f"filtered={len(filtered_regions)}/{len(regions)}, normalized={len(normalized_regions)}"
                )
                if source == "pdf":
                    # Provenance log: where current overlays originate from.
                    sample = []
                    for r, _ in normalized_regions[:5]:
                        sample.append({
                            "area_code": str(getattr(r, "area_code", "") or ""),
                            "page_id": int(self._infer_region_page_id(r, "pdf") or 0),
                            "sync_number": getattr(r, "sync_number", None),
                        })
                    print(f"[PDF_OVERLAY] origin_sample={sample}")
                diag = self._get_region_diagnostics(source)
                if diag:
                    print(f"[_redraw_regions] {source} hidden_reasons={diag.get('hidden_reasons', {})} page_drift_px={diag.get('page_drift_px', {})}")

                if source == "pdf":
                    counts = (diag or {}).get("counts", {})
                    print(
                        f"[PDF_OVERLAY] page={current_page} total={counts.get('total', len(regions))} "
                        f"filtered={counts.get('filtered', len(filtered_regions))} drawn={counts.get('drawn', len(normalized_regions))}"
                    )

                from app.gui.sdk.coord_transform import get_canvas_transform
                transform = get_canvas_transform(canvas)
                sample_logged = 0
                sample_limit = max(1, int(getattr(self, "_overlay_log_sample_limit", 3)))

                for region, rect in normalized_regions:
                    try:
                        x1, y1, x2, y2 = transform.src_rect_to_view(
                            rect[0], rect[1], rect[2], rect[3]
                        )

                        if region == self.selected_region:
                            outline = "#FFFFFF"
                            width = 3
                        elif hasattr(region, 'sync_number') and region.sync_number is not None:
                            outline = sync_colors[region.sync_number % len(sync_colors)]
                            width = 2
                        else:
                            # Improve visibility for unmatched PDF overlays on dense pages.
                            if source == "pdf":
                                outline = "#00E5FF"
                                width = 2
                            else:
                                outline = "#808080"
                                width = 1

                        canvas.create_rectangle(
                            x1, y1, x2, y2,
                            outline=outline, width=width,
                            tags="region"
                        )

                        if source == "pdf" and sample_logged < sample_limit:
                            drift_px = self._round_trip_error_for_rect(transform, rect)
                            print(
                                f"[PDF_OVERLAY] sample#{sample_logged + 1} area={getattr(region, 'area_code', '?')} "
                                f"src={rect} view={[int(x1), int(y1), int(x2), int(y2)]} drift_px={drift_px:.3f}"
                            )
                            sample_logged += 1

                        area_code = getattr(region, 'area_code', '')
                        show_unmatched_labels = (getattr(self, "show_unmatched_area_labels_by_source", {}) or {}).get(source, True)
                        is_matched_or_selected = (region == self.selected_region) or (getattr(region, "sync_number", None) is not None)
                        if area_code and (show_unmatched_labels or is_matched_or_selected):
                            canvas.create_text(
                                x1 + 5, y1 + 5,
                                text=area_code,
                                fill=outline,
                                anchor="nw",
                                font=("Consolas", 9, "bold"),
                                tags="region"
                            )
                    except Exception as e:
                        print(f"[WARNING] Region draw skip: {e}")
                        continue

                region_items = canvas.find_withtag("region")
                print(f"[_redraw_regions] {source}: {len(region_items)} region items drawn")

        except Exception as e:
            self._show_error("Region redraw error", e, show_traceback=True)

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
            match_count = self._count_matches(self.sync_pairs, threshold=0.25)
            
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


                

    
    def _count_matches(self, pairs, threshold: float = 0.25) -> int:
        """Single-source match count for Advanced view stats."""
        return sum(1 for p in (pairs or []) if float(getattr(p, "similarity", 0.0) or 0.0) >= threshold)

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
        # ★ 安全チェック: area_listが存在しない場合はスキップ
        if not hasattr(self, 'area_list') or not self.area_list:
            print("[_update_area_list] Skipped: area_list not initialized")
            return
            
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
        """WebとPDFのSync率を再計算 (SDK版)"""
        if not self.web_regions and not self.pdf_regions:
            self.status_label.configure(text="⚠️ OCRを先に実行してください")
            return
        
        if update_ui:
            self.status_label.configure(text="🔄 パラグラフマッチング計算中...")
            self.update()
        
        try:
            # ★ 新SDK版 ParagraphMatcher を使用
            from app.sdk.similarity.paragraph_matcher import ParagraphMatcher
            
            matcher = ParagraphMatcher(threshold=0.25)
            sync_pairs = matcher.match(self.web_regions, self.pdf_regions)
            
            # 保存
            self.sync_pairs = sync_pairs
            
            # 領域のsimilarity と sync_color をsync_pairsから更新
            sync_map_web = {sp.web_id: sp for sp in sync_pairs if sp.web_id}
            sync_map_pdf = {sp.pdf_id: sp for sp in sync_pairs if sp.pdf_id}
            
            for region in self.web_regions:
                sp = sync_map_web.get(region.area_code)
                if sp:
                    region.similarity = sp.similarity
                    # ★ 新機能: sync_colorをコピー
                    if hasattr(sp, 'sync_color'):
                        region.sync_color = sp.sync_color
            
            for region in self.pdf_regions:
                sp = sync_map_pdf.get(region.area_code)
                if sp:
                    region.similarity = sp.similarity
                    if hasattr(sp, 'sync_color'):
                        region.sync_color = sp.sync_color
            
            # 描画更新 (update_ui=Trueの場合のみ)
            if update_ui:
                self._redraw_regions_with_sync()
            
                # ★ 改善: 全体Sync率計算 
                # 旧: マッチ済みペアの平均類似度
                # 新: (マッチ文字数 / 総文字数) で計算
                total_web_chars = sum(len(r.text) for r in self.web_regions if r.text)
                total_pdf_chars = sum(len(r.text) for r in self.pdf_regions if r.text)
                total_chars = total_web_chars + total_pdf_chars
                
                matched_chars = 0
                for sp in sync_pairs:
                    if sp.similarity > 0 and sp.web_text and sp.pdf_text:
                        # 類似度 × 文字数で加重計算
                        avg_len = (len(sp.web_text) + len(sp.pdf_text)) / 2
                        matched_chars += avg_len * sp.similarity * 2  # 両方にあるので×2
                
                overall_percent = (matched_chars / total_chars * 100) if total_chars > 0 else 0
                
                color = "#4CAF50" if overall_percent >= 70 else "#FF9800" if overall_percent >= 40 else "#F44336"
                self.sync_rate_label.configure(text=f"Sync Rate: {overall_percent:.1f}%", text_color=color)
                self.sync_rate_display.configure(text=f"Sync: {overall_percent:.1f}%")
                
                # ステータス更新 (閾値も調整)
                high_count = sum(1 for sp in sync_pairs if sp.similarity >= 0.70)
                mid_count = sum(1 for sp in sync_pairs if 0.40 <= sp.similarity < 0.70)
                low_count = sum(1 for sp in sync_pairs if 0 < sp.similarity < 0.40)
                unmatched = sum(1 for sp in sync_pairs if sp.similarity == 0)
                
                self.status_label.configure(
                    text=f"✅ Sync完了: 🟢{high_count} 🟡{mid_count} 🟠{low_count} ⚪{unmatched}"
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
        """Redraw matched regions with normalized pipeline and diagnostics."""
        for canvas, _, source in [
            (self.web_canvas, self.web_regions, "web"),
            (self.pdf_canvas, self.pdf_regions, "pdf")
        ]:
            if not canvas:
                continue

            canvas.delete("region")

            from app.gui.sdk.coord_transform import get_canvas_transform
            transform = get_canvas_transform(canvas)

            normalized_regions = self._get_normalized_regions_for_source(source, canvas=canvas)
            for region, rect in normalized_regions:
                if len(rect) < 4:
                    continue

                x1, y1, x2, y2 = transform.src_rect_to_view(
                    rect[0], rect[1], rect[2], rect[3]
                )

                outline = getattr(region, 'sync_color', '#F44336')
                width = 3 if region == self.selected_region else 2

                canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline=outline, width=width,
                    tags="region"
                )

                show_unmatched_labels = (getattr(self, "show_unmatched_area_labels_by_source", {}) or {}).get(source, True)
                is_matched_or_selected = (region == self.selected_region) or (getattr(region, "sync_number", None) is not None)
                similarity_str = (
                    f"{region.similarity * 100:.0f}%"
                    if hasattr(region, 'similarity') and region.similarity > 0
                    else ""
                )
                label = f"{getattr(region, 'area_code', '')} {similarity_str}".strip()
                if label and (show_unmatched_labels or is_matched_or_selected):
                    canvas.create_text(
                        x1 + 5, y1 + 5,
                        text=label,
                        fill=outline,
                        anchor="nw",
                        font=("Meiryo", 8, "bold"),
                        tags="region"
                    )

            diag = self._get_region_diagnostics(source)
            if diag:
                print(f"[_redraw_regions_with_sync] {source} hidden_reasons={diag.get('hidden_reasons', {})} page_drift_px={diag.get('page_drift_px', {})}")

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
        """Toggle fullscreen/maximize on current window and reflow canvases."""
        root = self.winfo_toplevel()

        full = bool(getattr(self, "_is_fullscreen", False))
        target_full = not full

        try:
            root.attributes("-fullscreen", target_full)
        except Exception:
            try:
                root.state("zoomed" if target_full else "normal")
            except Exception as e:
                print(f"[Fullscreen] toggle failed: {e}")
                return

        self._is_fullscreen = target_full

        if hasattr(self, "fullscreen_btn") and self.fullscreen_btn:
            try:
                self.fullscreen_btn.configure(text="ExitFS" if target_full else "Fullscreen")
            except Exception:
                pass

        def _refresh():
            try:
                self._last_canvas_size["web"] = (0, 0)
                self._last_canvas_size["pdf"] = (0, 0)
                self._clear_image_cache("web")
                self._clear_image_cache("pdf")
                if getattr(self, "web_image", None):
                    self._display_image(self.web_canvas, self.web_image)
                if getattr(self, "pdf_image", None):
                    self._display_image(self.pdf_canvas, self.pdf_image)
                self._redraw_regions()
            except Exception as e:
                print(f"[Fullscreen] refresh warning: {e}")

        self.after(80, _refresh)
        self.after(220, _refresh)

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
        """Find the first region under the given canvas coordinates."""
        source = "web" if canvas == self.web_canvas else "pdf"
        regions = self.web_regions if source == "web" else self.pdf_regions

        from app.gui.sdk.coord_transform import get_canvas_transform
        transform = get_canvas_transform(canvas)

        filtered_regions = self._filter_regions_for_current_view(regions, source)
        for region in filtered_regions:
            rect = self._normalize_region_rect_for_current_view(region, source)
            if len(rect) < 4:
                continue

            rx1, ry1, rx2, ry2 = transform.src_rect_to_view(
                rect[0], rect[1], rect[2], rect[3]
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
    
    def _passes_region_quality_gate(self, region, rect, source: str) -> bool:
        """Filter tiny/low-signal regions to keep overlays readable."""
        if not rect or len(rect) < 4:
            return False

        x1, y1, x2, y2 = [int(v) for v in rect]
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        area = w * h

        min_area_map = getattr(self, "min_region_area_by_source", {}) or {}
        min_area = int(min_area_map.get(source, 0) or 0)
        if min_area > 0 and area < min_area:
            return False

        if source == "pdf":
            # Decorative tiny strips/no-text boxes are frequent in PDF pages.
            txt = str(getattr(region, "text", "") or "").strip()
            if area < max(min_area, 400) and len(txt) < 1:
                return False

        return True

    def _limit_regions_for_view(self, items, source: str):
        """Cap rendered regions to avoid unreadable overlay density."""
        max_map = getattr(self, "max_regions_per_view_by_source", {}) or {}
        max_count = int(max_map.get(source, 0) or 0)
        if max_count <= 0 or len(items) <= max_count:
            return items
        return items[:max_count]

    def _prioritize_regions_for_display(self, items, source: str):
        """Apply per-source display policy (e.g., matched-first for PDF)."""
        mode_map = getattr(self, "region_display_mode_by_source", {}) or {}
        mode = str(mode_map.get(source, "all") or "all").lower()

        if source != "pdf" or mode != "matched" or not items:
            return items

        selected = getattr(self, "selected_region", None)
        selected_items = [(r, rect) for (r, rect) in items if selected is not None and r == selected]
        matched_items = [
            (r, rect) for (r, rect) in items
            if getattr(r, "sync_number", None) is not None and (selected is None or r != selected)
        ]

        if selected_items or matched_items:
            prioritized = selected_items + matched_items
            return self._limit_regions_for_view(prioritized, source)

        return items


    def _round_trip_error_for_rect(self, transform, rect) -> float:
        """Estimate source-space drift for a rect via round-trip error."""
        try:
            x1, y1, x2, y2 = [int(v) for v in rect]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            points = [(x1, y1), (x2, y2), (cx, cy)]
            max_err = 0.0
            for sx, sy in points:
                ex, ey = transform.round_trip_error(sx, sy)
                max_err = max(max_err, float(ex), float(ey))
            return max_err
        except Exception:
            return 0.0

    def _get_region_diagnostics(self, source: str):
        store = getattr(self, "_last_region_diagnostics", {}) or {}
        return store.get(source)



    def _get_normalized_regions_for_source(self, source: str, canvas=None):
        """Return current-view regions with normalized/clipped rects and diagnostics."""
        regions = self.web_regions if source == "web" else self.pdf_regions
        filtered = self._filter_regions_for_current_view(regions, source)

        hidden_reasons = {
            "page_filter_or_unknown": max(0, len(regions) - len(filtered)),
            "invalid_or_unconvertible": 0,
            "quality_gate": 0,
            "density_limit": 0,
            "display_mode": 0,
        }

        normalized = []
        for region in filtered:
            rect = self._normalize_region_rect_for_current_view(region, source)
            if not rect or len(rect) < 4:
                hidden_reasons["invalid_or_unconvertible"] += 1
                continue
            if int(rect[2]) <= int(rect[0]) or int(rect[3]) <= int(rect[1]):
                hidden_reasons["invalid_or_unconvertible"] += 1
                continue
            if not self._passes_region_quality_gate(region, rect, source):
                hidden_reasons["quality_gate"] += 1
                continue
            normalized.append((region, [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]))

        limited = self._limit_regions_for_view(normalized, source)
        hidden_reasons["density_limit"] += max(0, len(normalized) - len(limited))
        prioritized = self._prioritize_regions_for_display(limited, source)
        hidden_reasons["display_mode"] += max(0, len(limited) - len(prioritized))

        # Adaptive fallback for dense PDF pages: avoid near-empty overlays caused by strict matched mode.
        if source == "pdf":
            filtered_count = len(filtered)
            drawn_count = len(prioritized)
            if filtered_count >= 120 and drawn_count < 15 and len(limited) >= 30:
                fallback_count = min(max(30, drawn_count), min(120, len(limited)))
                prioritized = limited[:fallback_count]
                hidden_reasons["display_mode"] = max(0, len(limited) - len(prioritized))
                hidden_reasons["display_mode_fallback"] = 1
                print(
                    f"[PDF_OVERLAY] fallback: filtered={filtered_count} "
                    f"drawn_before={drawn_count} drawn_after={len(prioritized)}"
                )

        page_stats = {}
        try:
            from app.gui.sdk.coord_transform import get_canvas_transform
            target_canvas = canvas
            if target_canvas is None:
                target_canvas = self.web_canvas if source == "web" else self.pdf_canvas
            transform = get_canvas_transform(target_canvas)
            for region, rect in prioritized:
                page_id = int(self._infer_region_page_id(region, source) or 0)
                drift_px = self._round_trip_error_for_rect(transform, rect)
                bucket = page_stats.setdefault(page_id, {"count": 0, "max_drift_px": 0.0, "sum_drift_px": 0.0})
                bucket["count"] += 1
                bucket["sum_drift_px"] += drift_px
                if drift_px > bucket["max_drift_px"]:
                    bucket["max_drift_px"] = drift_px
            for bucket in page_stats.values():
                c = max(1, int(bucket.get("count", 1)))
                bucket["avg_drift_px"] = round(float(bucket.get("sum_drift_px", 0.0)) / c, 3)
                bucket["max_drift_px"] = round(float(bucket.get("max_drift_px", 0.0)), 3)
                bucket.pop("sum_drift_px", None)
        except Exception:
            pass

        diag = {
            "source": source,
            "page": self._get_current_page_for_source(source),
            "counts": {
                "total": len(regions),
                "filtered": len(filtered),
                "normalized": len(normalized),
                "limited": len(limited),
                "drawn": len(prioritized),
            },
            "hidden_reasons": hidden_reasons,
            "page_drift_px": page_stats,
        }
        store = getattr(self, "_last_region_diagnostics", None)
        if isinstance(store, dict):
            store[source] = diag

        return prioritized


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
                show_unmatched_labels = (getattr(self, "show_unmatched_area_labels_by_source", {}) or {}).get(source, True)
                is_matched_or_selected = (region == self.selected_region) or (getattr(region, "sync_number", None) is not None)
                if show_unmatched_labels or is_matched_or_selected:
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
    # SimpleSelectionHandler Callbacks - Phase 1.6 Ultra Professional
    # ============================================================

    def _allocate_unique_selection_area_code(self, preferred_code: Optional[str] = None) -> str:
        """Allocate a unique SEL_XXX area code across regions and sync pairs."""
        import re

        used = set()
        for r in (getattr(self, "web_regions", []) or []):
            code = str(getattr(r, "area_code", "") or "").strip()
            if code:
                used.add(code)
        for r in (getattr(self, "pdf_regions", []) or []):
            code = str(getattr(r, "area_code", "") or "").strip()
            if code:
                used.add(code)
        for p in (getattr(self, "sync_pairs", []) or []):
            wid = str(getattr(p, "web_id", "") or "").strip()
            pid = str(getattr(p, "pdf_id", "") or "").strip()
            if wid:
                used.add(wid)
            if pid:
                used.add(pid)

        sel_num_pattern = re.compile(r"^SEL[_-](\d{3})$")
        counter = int(getattr(self, "_selection_area_counter", 0) or 0)

        preferred = str(preferred_code or "").strip()
        m = sel_num_pattern.match(preferred)
        if preferred and m and preferred not in used:
            num = int(m.group(1))
            self._selection_area_counter = max(counter, num)
            return f"SEL_{num:03d}"

        if m:
            counter = max(counter, int(m.group(1)))

        while True:
            counter += 1
            candidate = f"SEL_{counter:03d}"
            if candidate not in used:
                self._selection_area_counter = counter
                return candidate

    
    def _on_simple_selection_complete(self, result):
        """Selection complete callback from SimpleSelectionHandler."""
        print(f"\n{'='*60}")
        print(f"[Callback] _on_simple_selection_complete")
        print(f"[Callback] area_code: {result.area_code}")
        print(f"[Callback] text: {result.text[:50]}..." if len(result.text) > 50 else f"[Callback] text: {result.text}")
        print(f"{'='*60}")

        try:
            result.area_code = self._allocate_unique_selection_area_code(getattr(result, "area_code", None))

            local_rect = list(result.rect)
            final_rect = list(local_rect)
            page_id = -1
            stitched_y_offset = 0
            coord_system = "global"

            if result.source == "web":
                page_id = int(getattr(self, 'current_page', 1) or 1)
                stitched_y_offset = self._get_page_y_offset_for_source("web", page_id)
                if stitched_y_offset == 0:
                    web_offsets = getattr(self, "web_page_offsets", None)
                    if isinstance(web_offsets, list) and 0 <= (page_id - 1) < len(web_offsets):
                        stitched_y_offset = int(web_offsets[page_id - 1] or 0)
                final_rect = [
                    int(local_rect[0]),
                    int(local_rect[1] + stitched_y_offset),
                    int(local_rect[2]),
                    int(local_rect[3] + stitched_y_offset),
                ]
            elif result.source == "pdf":
                page_id = int(getattr(self, 'current_pdf_page', 0) or (getattr(self, 'current_pdf_idx', 0) + 1))
                if page_id < 1:
                    page_id = -1
                stitched_y_offset = self._get_page_y_offset_for_source("pdf", page_id if page_id > 0 else None)
                if stitched_y_offset == 0 and page_id > 0:
                    pdf_offsets = getattr(self, "pdf_page_offsets", None)
                    if isinstance(pdf_offsets, list) and 0 <= (page_id - 1) < len(pdf_offsets):
                        stitched_y_offset = int(pdf_offsets[page_id - 1] or 0)
                if page_id > 0:
                    final_rect = [
                        int(local_rect[0]),
                        int(local_rect[1] + stitched_y_offset),
                        int(local_rect[2]),
                        int(local_rect[3] + stitched_y_offset),
                    ]

            new_region = EditableRegion(
                id=len(self.web_regions) + len(self.pdf_regions) + 1,
                rect=final_rect,
                text=result.text,
                area_code=result.area_code,
                sync_number=None,
                similarity=0.0,
                source=result.source,
                page_id=page_id,
                coord_system=coord_system,
                stitched_y_offset=stitched_y_offset,
            )

            if result.source == "web":
                self.web_regions.append(new_region)
            else:
                self.pdf_regions.append(new_region)

            from app.core.paragraph_matcher import SyncPair
            rect_list = list(final_rect)

            if result.source == "web":
                new_pair = SyncPair(
                    web_id=result.area_code,
                    pdf_id="",
                    similarity=0.0,
                    color="#FF9800",
                    web_bbox=rect_list,
                    pdf_bbox=None,
                    web_text=result.text,
                    pdf_text="",
                )
            else:
                new_pair = SyncPair(
                    web_id="",
                    pdf_id=result.area_code,
                    similarity=0.0,
                    color="#FF9800",
                    web_bbox=None,
                    pdf_bbox=rect_list,
                    web_text="",
                    pdf_text=result.text,
                )

            self.sync_pairs.append(new_pair)
            self._refresh_inline_spreadsheet()
            self._redraw_regions()  # ★ 新規選択をバッジ付きで描画
            if result.text and "[TEXT_EXTRACT_FAILED" not in result.text:
                self.status_label.configure(text=f"Text extraction OK: {len(result.text)} chars")
            else:
                self.status_label.configure(text="Text extraction failed - manual edit available")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Callback] Error: {e}")
            self.status_label.configure(text=f"Error: {e}")

    def _on_simple_selection_deleted(self, area_code: str):
        """
        SimpleSelectionHandler からの選択削除コールバック
        
        Args:
            area_code: 削除された領域のエリアコード
        """
        print(f"[Callback] _on_simple_selection_deleted: {area_code}")
        
        try:
            # regions から削除
            self.web_regions = [r for r in self.web_regions if r.area_code != area_code]
            self.pdf_regions = [r for r in self.pdf_regions if r.area_code != area_code]
            
            # sync_pairs から削除
            self.sync_pairs = [p for p in self.sync_pairs 
                              if p.web_id != area_code and p.pdf_id != area_code]
            
            # シート更新
            self._refresh_inline_spreadsheet()
            self._redraw_regions()  # ★ キャンバス矩形を再描画

            self.status_label.configure(text=f"🗑️ {area_code} を削除しました")
            print(f"[Callback] ✅ Region deleted: {area_code}")

        except Exception as e:
            print(f"[Callback] ❌ Delete error: {e}")

    def _clear_all_manual_selections(self, _event=None):
        """全手動選択を消去し、OCR結果のみに戻す (Ctrl+Shift+Delete)"""
        try:
            if hasattr(self, '_web_selection_handler') and self._web_selection_handler:
                self._web_selection_handler.clear_all()
            if hasattr(self, '_pdf_selection_handler') and self._pdf_selection_handler:
                self._pdf_selection_handler.clear_all()

            self.web_regions = [r for r in self.web_regions
                                if not str(getattr(r, 'area_code', '')).startswith('SEL')]
            self.pdf_regions = [r for r in self.pdf_regions
                                if not str(getattr(r, 'area_code', '')).startswith('SEL')]
            self.sync_pairs = [p for p in self.sync_pairs
                               if not str(getattr(p, 'web_id', '')).startswith('SEL')
                               and not str(getattr(p, 'pdf_id', '')).startswith('SEL')]

            self._refresh_inline_spreadsheet()
            self._redraw_regions()
            self.status_label.configure(text="全手動選択をクリアしました")
            print("[ClearAll] ✅ All manual selections cleared")
        except Exception as e:
            print(f"[ClearAll] ❌ Error: {e}")

    # ============================================================
    # Canvas Drag Selection - 画像上で矩形選択→テキスト抽出 (Legacy)
    # ============================================================

    
    def _on_canvas_click(self, event):
        """キャンバスクリック - 選択開始 (SelectionMixin統合版)"""
        print(f"[DEBUG] _on_canvas_click called at ({event.x}, {event.y})")  # デバッグログ
        canvas = event.widget
        
        # スクロール位置を考慮した実座標
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # ★ SelectionMixin連携: 即座シート反映対応
        if _HAS_SELECTION_MIXIN and hasattr(self, '_on_selection_start'):
            source = "web" if canvas == self.web_canvas else "pdf"
            self._on_selection_start(event, canvas, source)
        
        # 選択開始点を記録
        self._selection_start = (x, y)
        self._selection_canvas = canvas
        self._selection_source = "web" if canvas == self.web_canvas else "pdf"
        
        # 既存の選択矩形を削除
        canvas.delete("selection_rect")
    
    def _on_canvas_drag(self, event):
        """キャンバスドラッグ - 選択範囲描画 (SelectionMixin統合版)"""
        if not hasattr(self, '_selection_start') or self._selection_start is None:
            return
        
        canvas = event.widget
        if canvas != self._selection_canvas:
            return
        
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # ★ SelectionMixin連携
        if _HAS_SELECTION_MIXIN and hasattr(self, '_on_selection_drag'):
            self._on_selection_drag(event, canvas)
        
        x1, y1 = self._selection_start
        
        # 選択矩形を描画
        canvas.delete("selection_rect")
        canvas.create_rectangle(
            x1, y1, x, y,
            outline="#00FF00", width=2, dash=(4, 2),
            tags="selection_rect"
        )
    
    def _on_canvas_release(self, event):
        """キャンバスリリース - 選択完了→テキスト抽出 (SelectionMixin統合版)"""
        import sys
        print(f"\n{'★'*30}")
        print(f"[RELEASE] _on_canvas_release CALLED!")
        print(f"{'★'*30}")
        sys.stdout.flush()
        
        if not hasattr(self, '_selection_start') or self._selection_start is None:
            print("[RELEASE] ❌ No selection start, returning EARLY")
            sys.stdout.flush()
            return
        
        canvas = event.widget
        if canvas != self._selection_canvas:
            return
        
        # ★★★ Phase 1.6 FIX: SelectionMixin をバイパス ★★★
        # SelectionMixin は古いSDK (SelectionManager) を使い、Gemini OCRを使わない
        # 直接 Gemini Vision OCR パスを実行する
        # if _HAS_SELECTION_MIXIN and hasattr(self, '_on_selection_end'):
        #     image_source = self.web_image if self._selection_source == "web" else self.pdf_image
        #     self._on_selection_end(event, canvas, self._selection_source)
        print("[RELEASE] ✅ SelectionMixin bypassed, using direct Gemini OCR path")
        
        x2 = canvas.canvasx(event.x)
        y2 = canvas.canvasy(event.y)
        x1, y1 = self._selection_start

        # Normalize view rect (top-left to bottom-right)
        view_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            self._selection_start = None
            return

        # Convert from canvas(view) to source coordinates
        from app.gui.sdk.coord_transform import get_canvas_transform
        transform = get_canvas_transform(canvas)
        sx1, sy1 = transform.view_to_src(int(view_rect[0]), int(view_rect[1]))
        sx2, sy2 = transform.view_to_src(int(view_rect[2]), int(view_rect[3]))
        source_rect = (min(sx1, sx2), min(sy1, sy2), max(sx1, sx2), max(sy1, sy2))

        # Convert source local rect to source global rect for sheet/sync
        local_rect = [int(source_rect[0]), int(source_rect[1]), int(source_rect[2]), int(source_rect[3])]
        final_rect = list(local_rect)
        page_id = -1
        stitched_y_offset = 0
        coord_system = "global"

        if self._selection_source == "web":
            page_id = int(getattr(self, "current_page", 1) or 1)
            stitched_y_offset = self._get_page_y_offset_for_source("web", page_id)
            if stitched_y_offset == 0:
                web_offsets = getattr(self, "web_page_offsets", None)
                if isinstance(web_offsets, list) and 0 <= (page_id - 1) < len(web_offsets):
                    stitched_y_offset = int(web_offsets[page_id - 1] or 0)
            final_rect = [
                int(local_rect[0]),
                int(local_rect[1] + stitched_y_offset),
                int(local_rect[2]),
                int(local_rect[3] + stitched_y_offset),
            ]
        elif self._selection_source == "pdf":
            page_id = int(getattr(self, "current_pdf_page", 0) or (getattr(self, "current_pdf_idx", 0) + 1))
            if page_id < 1:
                page_id = -1
            stitched_y_offset = self._get_page_y_offset_for_source("pdf", page_id if page_id > 0 else None)
            if stitched_y_offset == 0 and page_id > 0:
                pdf_offsets = getattr(self, "pdf_page_offsets", None)
                if isinstance(pdf_offsets, list) and 0 <= (page_id - 1) < len(pdf_offsets):
                    stitched_y_offset = int(pdf_offsets[page_id - 1] or 0)
            if page_id > 0:
                final_rect = [
                    int(local_rect[0]),
                    int(local_rect[1] + stitched_y_offset),
                    int(local_rect[2]),
                    int(local_rect[3] + stitched_y_offset),
                ]

        self.status_label.configure(text=f"剥 Gemini Vision OCR 螳溯｡御ｸｭ...")
        self.update()

        # Extract text using page-local source coordinates
        extracted_text = self._extract_text_from_region(source_rect, self._selection_source)
        
        # ★ HYPER-DIAGNOSTIC: テキスト抽出結果を詳細ログ
        print(f"\n{'='*60}")
        print(f"[HYPER-DEBUG] _on_canvas_release テキスト抽出完了")
        print(f"[HYPER-DEBUG] view_rect: {view_rect}\n[HYPER-DEBUG] source_rect: {source_rect}\n[HYPER-DEBUG] final_rect: {final_rect}")
        print(f"[HYPER-DEBUG] source: {self._selection_source}")
        print(f"[HYPER-DEBUG] extracted_text type: {type(extracted_text)}")
        print(f"[HYPER-DEBUG] extracted_text value: {repr(extracted_text[:200] if extracted_text else 'None')}")
        print(f"[HYPER-DEBUG] extracted_text length: {len(extracted_text) if extracted_text else 0}")
        print(f"{'='*60}\n")
        
        # ★ None/空チェック
        if extracted_text is None:
            extracted_text = ""
        
        # テキストボックスに表示
        if self._selection_source == "web":
            self.web_text_box.configure(state="normal")
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", extracted_text)
        else:
            self.pdf_text_box.configure(state="normal")
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", extracted_text)
        
        # ★ Phase 1.6 Fix: テキスト抽出成功/失敗に関わらず、常に領域を作成
        # これによりサムネイルは常に表示される
        display_text = extracted_text.strip() if extracted_text else "[テキスト抽出失敗 - 手動入力可]"
        
        new_region = EditableRegion(
            id=len(self.web_regions) + len(self.pdf_regions) + 1,
            rect=list(final_rect),
            text=display_text,
            area_code=f"SEL_{len(self.web_regions) + len(self.pdf_regions) + 1:03d}",
            sync_number=None,
            similarity=0.0,
            source=self._selection_source,
            page_id=page_id,
            coord_system=coord_system,
            stitched_y_offset=stitched_y_offset,
        )
        
        if self._selection_source == "web":
            self.web_regions.append(new_region)
        else:
            self.pdf_regions.append(new_region)
        
        print(f"✅ New region added: {new_region.area_code}, text_len={len(display_text)}")
        
        # ★ Phase 1.6 Fix: 新しい選択用のSyncPairを作成してシートに表示
        # SpreadsheetPanelはsync_pairsからデータを読み込むため、
        # SyncPairを作成しないと手動選択がシートに反映されない
        from app.core.paragraph_matcher import SyncPair
        
        if self._selection_source == "web":
            # Web選択: web_id設定、pdf_idは空（対向マッチング待ち）
            new_sync_pair = SyncPair(
                web_id=new_region.area_code,
                pdf_id="",  # 対向マッチング後に更新される
                similarity=0.0,
                color="#FF9800",  # オレンジ（未マッチ）
                web_bbox=new_region.rect,
                pdf_bbox=None,
                web_text=display_text,
                pdf_text=None
            )
        else:
            # PDF選択: pdf_id設定、web_idは空
            new_sync_pair = SyncPair(
                web_id="",  # 対向マッチング後に更新される
                pdf_id=new_region.area_code,
                similarity=0.0,
                color="#FF9800",  # オレンジ（未マッチ）
                web_bbox=None,
                pdf_bbox=new_region.rect,
                web_text=None,
                pdf_text=display_text
            )
        
        self.sync_pairs.append(new_sync_pair)
        print(f"\n{'='*60}")
        print(f"[HYPER-DEBUG] SyncPair created and added")
        print(f"[HYPER-DEBUG] area_code: {new_region.area_code}")
        print(f"[HYPER-DEBUG] web_id: {new_sync_pair.web_id}")
        print(f"[HYPER-DEBUG] pdf_id: {new_sync_pair.pdf_id}")
        print(f"[HYPER-DEBUG] web_text: {repr(new_sync_pair.web_text[:100] if new_sync_pair.web_text else 'None')}")
        print(f"[HYPER-DEBUG] pdf_text: {repr(new_sync_pair.pdf_text[:100] if new_sync_pair.pdf_text else 'None')}")
        print(f"[HYPER-DEBUG] web_bbox: {new_sync_pair.web_bbox}")
        print(f"[HYPER-DEBUG] pdf_bbox: {new_sync_pair.pdf_bbox}")
        print(f"[HYPER-DEBUG] sync_pairs count: {len(self.sync_pairs)}")
        print(f"{'='*60}\n")
        
        # ★ スプレッドシートを即座に更新
        if hasattr(self, '_refresh_inline_spreadsheet'):
            self._refresh_inline_spreadsheet()
        
        # ★ Phase 1.6: Gemini自動マッチング - 対向ソースから類似パラグラフ検出
        if extracted_text.strip():
            self._run_auto_matching(extracted_text, new_region)
        
        # 選択完了 - 成功/警告表示
        if extracted_text.strip():
            canvas.itemconfig("selection_rect", outline="#4CAF50", dash=())
            self.status_label.configure(text=f"✅ {self._selection_source.upper()}から{len(extracted_text)}文字抽出 - 対向検索中...")
        else:
            canvas.itemconfig("selection_rect", outline="#FF9800", dash=())
            self.status_label.configure(text=f"⚠️ テキスト抽出失敗 - シートには追加済み (サムネイル表示)")
        
        self._selection_start = None
    
    def _run_auto_matching(self, query_text: str, source_region):
        """★ Phase 1.6: 対向ソースから類似パラグラフを自動検出"""
        import threading
        
        # 対向ソースのパラグラフを取得
        opposite_source = "pdf" if source_region.source == "web" else "web"
        target_paragraphs = self.pdf_regions if opposite_source == "pdf" else self.web_regions
        
        if not target_paragraphs:
            self.status_label.configure(text=f"⚠️ {opposite_source.upper()}に類似テキストが見つかりませんでした")
            return
        
        # パラグラフをdict形式に変換
        target_dicts = [
            {"id": p.id, "text": p.text, "rect": p.rect}
            for p in target_paragraphs
        ]
        
        def _match_callback(results):
            """マッチング結果のコールバック"""
            if results:
                best = results[0]
                print(f"[AutoMatch] Best match: {best.paragraph_text[:50]}... (score: {best.similarity_score:.2f})")
                
                # 対向テキストボックスにマッチ結果を表示
                self._safe_after(0, lambda: self._apply_auto_match_result(source_region, best, opposite_source))
            else:
                self._safe_after(
                    0,
                    lambda: self._safe_status(
                        f"笞・・{opposite_source.upper()}縺ｫ鬘樔ｼｼ繝・く繧ｹ繝医′隕九▽縺九ｊ縺ｾ縺帙ｓ縺ｧ縺励◆",
                        force_update=False
                    ),
                )
        
        # 非同期でマッチング実行
        try:
            from app.sdk.similarity import GeminiAutoMatcher
            matcher = GeminiAutoMatcher()
            matcher.find_matching_async(query_text, target_dicts, _match_callback)
        except Exception as e:
            print(f"[AutoMatch] Error: {e}")
            self.status_label.configure(text=f"⚠️ 自動マッチング失敗: {e}")
    
    def _apply_auto_match_result(self, source_region, match_result, opposite_source: str):
        """自動マッチング結果をUIに反映"""
        # 対向テキストボックスに表示
        if opposite_source == "pdf":
            self.pdf_text_box.configure(state="normal")
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", match_result.paragraph_text)
        else:
            self.web_text_box.configure(state="normal")
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", match_result.paragraph_text)
        
        # スコアを更新
        source_region.similarity = match_result.similarity_score
        
        # ★ Phase 1.6: 既存SyncPairを更新して対向マッチ情報を反映
        # source_region.area_code に一致するSyncPairを探して更新
        for sync_pair in self.sync_pairs:
            # Web → PDF マッチング
            if source_region.source == "web" and sync_pair.web_id == source_region.area_code:
                # PDF側の情報を追加
                matched_region = self._find_region_by_id(match_result.paragraph_id, "pdf")
                if matched_region:
                    sync_pair.pdf_id = matched_region.area_code
                    sync_pair.pdf_bbox = matched_region.rect
                    sync_pair.pdf_text = match_result.paragraph_text
                else:
                    # フォールバック: match_resultから直接設定
                    sync_pair.pdf_id = f"MATCH_{len(self.pdf_regions) + 1:03d}"
                    sync_pair.pdf_bbox = match_result.paragraph_rect if hasattr(match_result, 'paragraph_rect') else None
                    sync_pair.pdf_text = match_result.paragraph_text
                sync_pair.similarity = match_result.similarity_score
                sync_pair.color = self._get_sync_color(match_result.similarity_score)
                print(f"✅ SyncPair updated: {sync_pair.web_id} ↔ {sync_pair.pdf_id} ({int(match_result.similarity_score * 100)}%)")
                break
            # PDF → Web マッチング
            elif source_region.source == "pdf" and sync_pair.pdf_id == source_region.area_code:
                # Web側の情報を追加
                matched_region = self._find_region_by_id(match_result.paragraph_id, "web")
                if matched_region:
                    sync_pair.web_id = matched_region.area_code
                    sync_pair.web_bbox = matched_region.rect
                    sync_pair.web_text = match_result.paragraph_text
                else:
                    sync_pair.web_id = f"MATCH_{len(self.web_regions) + 1:03d}"
                    sync_pair.web_bbox = match_result.paragraph_rect if hasattr(match_result, 'paragraph_rect') else None
                    sync_pair.web_text = match_result.paragraph_text
                sync_pair.similarity = match_result.similarity_score
                sync_pair.color = self._get_sync_color(match_result.similarity_score)
                print(f"✅ SyncPair updated: {sync_pair.web_id} ↔ {sync_pair.pdf_id} ({int(match_result.similarity_score * 100)}%)")
                break
        
        # ステータス更新
        score_percent = int(match_result.similarity_score * 100)
        self.status_label.configure(
            text=f"✅ 類似テキスト検出: {score_percent}% マッチ ({opposite_source.upper()})"
        )
        
        # シート更新
        if hasattr(self, '_refresh_inline_spreadsheet'):
            self._refresh_inline_spreadsheet()
    
    def _find_region_by_id(self, region_id, source: str):
        """IDに一致するリージョンを検索"""
        regions = self.web_regions if source == "web" else self.pdf_regions
        for r in regions:
            # IDが数値または文字列で一致するか確認
            if r.id == region_id or str(r.id) == str(region_id):
                return r
            if hasattr(r, 'area_code') and r.area_code == region_id:
                return r
        return None
    
    def _get_sync_color(self, similarity: float) -> str:
        """類似度に応じた色を返す"""
        if similarity >= 0.5:
            return "#4CAF50"  # 緑 (高マッチ)
        elif similarity >= 0.3:
            return "#FF9800"  # オレンジ (中マッチ)
        else:
            return "#F44336"  # 赤 (低マッチ)
    
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
        
        # ★ Phase 1.6 精度優先: Gemini Vision OCR を最優先
        # Gemini 2.0/2.5/3.0 は日本語OCR精度が最高 (95%+)
        print(f"[_extract_text_from_region] 精度優先: Gemini Vision OCR を最初に試行...")
        
        extracted_text = self._extract_text_with_gemini_ocr(selection_rect, source)
        if extracted_text:
            print(f"[_extract_text_from_region] ✅ Gemini Vision OCR 成功: {len(extracted_text)} chars")
            return extracted_text
        
        print(f"[_extract_text_from_region] Gemini失敗、既存regionsからフォールバック...")
        
        # フォールバック: 既存の regions からマッチング
        paragraphs = self.web_regions if source == "web" else self.pdf_regions
        
        # ★ HYPER-DEBUG: パラグラフ数を詳細ログ
        print(f"[HYPER-DEBUG] _extract_text_from_region (fallback):")
        print(f"[HYPER-DEBUG]   source: {source}")
        print(f"[HYPER-DEBUG]   paragraphs count: {len(paragraphs)}")
        print(f"[HYPER-DEBUG]   selection_rect (source coords): {selection_rect}")
        if paragraphs:
            print(f"[HYPER-DEBUG]   first paragraph rect: {paragraphs[0].rect}, text: {paragraphs[0].text[:30] if paragraphs[0].text else 'empty'}...")
        
        extracted_parts = []
        
        for para in paragraphs:
            px1, py1, px2, py2 = para.rect  # Source座標
            
            # 選択範囲と重なるかチェック（Source座標同士で比較）
            if self._rects_overlap(selection_rect, (px1, py1, px2, py2)):
                extracted_parts.append(para.text)
        
        print(f"[_extract_text_from_region] Matched {len(extracted_parts)} paragraphs from existing regions")
        
        return '\n'.join(extracted_parts)
    
    def _extract_text_with_gemini_ocr(self, rect, source: str) -> str:
        """
        ★ Gemini Vision API で選択範囲から直接テキスト抽出
        
        Phase 1.6: 精度優先 - Gemini 2.0/2.5/3.0 は日本語OCR精度が最高 (95%+)
        
        修正: Base64エンコードを廃止、PIL Imageを直接渡す (最もシンプルで確実)
        """
        import sys
        print(f"\n{'='*60}")
        print(f"[GeminiOCR] ★★★ ENTRY POINT ★★★")
        print(f"[GeminiOCR] rect: {rect}")
        print(f"[GeminiOCR] source: {source}")
        sys.stdout.flush()
        
        try:
            # 画像取得
            image = self.web_image if source == "web" else self.pdf_image
            if not image:
                print("[GeminiOCR] ❌ No image available")
                return ""
            
            # 選択範囲を切り抜き
            sx1, sy1, sx2, sy2 = [int(max(0, v)) for v in rect]
            
            # 画像サイズでクリップ
            sx2 = min(sx2, image.width)
            sy2 = min(sy2, image.height)
            
            if sx2 <= sx1 or sy2 <= sy1:
                print(f"[GeminiOCR] ❌ Invalid crop region: {rect}")
                return ""
            
            print(f"[GeminiOCR] Cropping: ({sx1}, {sy1}) -> ({sx2}, {sy2})")
            cropped = image.crop((sx1, sy1, sx2, sy2))
            print(f"[GeminiOCR] Cropped size: {cropped.size}")
            
            # ★ GeminiClient.generate() を使用 - PIL Image を直接渡す
            from app.sdk.llm import GeminiClient
            
            client = GeminiClient(model="gemini-2.0-flash")
            if not client.model:
                print("[GeminiOCR] ⚠️ Gemini client init failed - check GEMINI_API_KEY")
                return ""
            
            # OCR用プロンプト (日本語特化)
            prompt = """この画像に含まれるテキストを正確に抽出してください。

ルール:
1. 画像内のテキストをそのまま抽出（翻訳/解釈しない）
2. 改行は元のレイアウトを維持
3. 日本語・英語混在可
4. 説明文は不要、テキストのみ出力

出力:"""
            
            # ★ シンプルな呼び出し: generate(prompt, images=[cropped])
            # Base64エンコードは不要、PIL Imageを直接渡す
            print("[GeminiOCR] Calling Gemini Vision API...")
            result = client.generate(prompt, images=[cropped])
            
            if result:
                clean_text = result.strip()
                print(f"[GeminiOCR] ✅ SUCCESS! Extracted {len(clean_text)} chars")
                print(f"[GeminiOCR] Preview: {clean_text[:100]}...")
                return clean_text
            else:
                print("[GeminiOCR] ⚠️ Empty response from Gemini")
                return ""
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[GeminiOCR] ❌ Error: {e}")
            return ""
    
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

    # ============================================================
    # B5: Crosshair Sanity Check
    # ============================================================
    
    def _on_mouse_motion(self, event):
        """Show crosshair and coordinates on mouse move."""
        if not self._crosshair_enabled:
            return

        canvas = event.widget

        # View coordinates with scroll offset applied.
        vx = float(canvas.canvasx(event.x))
        vy = float(canvas.canvasy(event.y))

        # Read scrollregion bounds.
        scrollregion = canvas.cget("scrollregion")
        if scrollregion:
            try:
                parts = scrollregion.split()
                max_x = float(parts[2]) if len(parts) >= 3 else float(canvas.winfo_width())
                max_y = float(parts[3]) if len(parts) >= 4 else float(canvas.winfo_height())
            except Exception:
                max_x = float(canvas.winfo_width())
                max_y = float(canvas.winfo_height())
        else:
            max_x = float(canvas.winfo_width())
            max_y = float(canvas.winfo_height())

        # Clamp pointer to drawable bounds.
        vx = max(0.0, min(vx, max_x))
        vy = max(0.0, min(vy, max_y))

        # Constrain crosshair to rendered image area.
        line_min_x, line_min_y = 0.0, 0.0
        line_max_x, line_max_y = max_x, max_y
        try:
            src_w = float(getattr(canvas, "source_width", 0) or 0)
            src_h = float(getattr(canvas, "source_height", 0) or 0)
            sc_x = float(getattr(canvas, "scale_x", 0) or 0)
            sc_y = float(getattr(canvas, "scale_y", 0) or 0)
            off_x = float(getattr(canvas, "offset_x", 0) or 0)
            off_y = float(getattr(canvas, "offset_y", 0) or 0)
            if src_w > 0 and src_h > 0 and sc_x > 0 and sc_y > 0:
                line_min_x = max(0.0, off_x)
                line_min_y = max(0.0, off_y)
                line_max_x = min(max_x, off_x + src_w * sc_x)
                line_max_y = min(max_y, off_y + src_h * sc_y)
        except Exception:
            pass

        vx = max(line_min_x, min(vx, line_max_x))
        vy = max(line_min_y, min(vy, line_max_y))

        from app.gui.sdk.coord_transform import get_canvas_transform
        transform = get_canvas_transform(canvas)
        sx, sy = transform.view_to_src(int(vx), int(vy))
        error_x, error_y = transform.round_trip_error(sx, sy)

        canvas.delete("crosshair")
        canvas.delete("coord_label")

        canvas.create_line(line_min_x, vy, line_max_x, vy, fill="#00FF00", width=1, dash=(2, 2), tags="crosshair")
        canvas.create_line(vx, line_min_y, vx, line_max_y, fill="#00FF00", width=1, dash=(2, 2), tags="crosshair")

        source_type = "Web" if canvas == self.web_canvas else "PDF"
        error_text = f"d{error_x:.0f},{error_y:.0f}" if (error_x > 0 or error_y > 0) else "ok"
        coord_text = f"{source_type} V({int(vx)},{int(vy)}) -> S({sx},{sy}) {error_text}"

        label_x = vx + 15
        label_y = vy - 15
        box_w = len(coord_text) * 6 + 4
        box_h = 22

        if label_x + box_w > max_x:
            label_x = max(0.0, max_x - box_w)
        if label_y < 0:
            label_y = min(max_y - box_h, vy + 8)
        if label_y + box_h > max_y:
            label_y = max(0.0, max_y - box_h)

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
    def _on_mouse_leave(self, event):
        """マウスがキャンバスから離れたらクロスヘアを消去"""
        canvas = event.widget
        canvas.delete("crosshair")
        canvas.delete("coord_label")
        self._last_crosshair_pos = None


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

    def _find_similar_gemini(self):
        """
        ★ Gemini-Powered 類似検索
        
        選択中のテキストボックスの内容をテンプレートとして、
        反対側のソース（PDF/Web）から類似テキストをGemini AIで検索
        
        Phase 1.5: SDK GeminiSimilarSearch 統合
        """
        import threading
        
        # テンプレートテキスト取得 (選択中のテキストボックスから)
        try:
            web_text = self.web_text_box.get("1.0", "end-1c").strip()
            pdf_text = self.pdf_text_box.get("1.0", "end-1c").strip()
        except:
            web_text = ""
            pdf_text = ""
        
        template_text = web_text if web_text else pdf_text
        
        if not template_text:
            self.status_label.configure(text="⚠️ まず範囲を選択してテキストを抽出してください")
            return
        
        # 検索対象: テンプレートがWebならPDFを検索、逆も同様
        if web_text:
            search_regions = self.pdf_regions
            search_source = "PDF"
        else:
            search_regions = self.web_regions
            search_source = "Web"
        
        if not search_regions:
            self.status_label.configure(text=f"⚠️ {search_source}側に検索対象がありません")
            return
        
        self.status_label.configure(text=f"✨ Gemini AI で {search_source} 内を類似検索中...")
        self.update()
        
        def search_task():
            try:
                # SDK Import
                from app.sdk.similarity import GeminiSimilarSearch
                
                searcher = GeminiSimilarSearch(
                    model="gemini-2.0-flash",
                    threshold=0.5
                )
                
                # 候補リスト作成
                candidates = []
                for r in search_regions:
                    candidates.append({
                        'text': r.text,
                        'id': r.area_code,
                        'region': r
                    })
                
                # Gemini類似検索実行
                results = searcher.find_similar(template_text, candidates)
                
                # 結果をUIに反映
                self._safe_after(0, lambda: self._apply_gemini_results(results, search_source))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._safe_after(
                    0,
                    lambda: self._safe_status(f"笶・Gemini讀懃ｴ｢繧ｨ繝ｩ繝ｼ: {e}", force_update=False),
                )
        
        # バックグラウンドで実行
        threading.Thread(target=search_task, daemon=True).start()
    
    def _apply_gemini_results(self, results, search_source: str):
        """
        Gemini検索結果をUI反映
        - ステータス更新
        - 類似領域をハイライト
        - シートに反映
        """
        if not results:
            self.status_label.configure(text=f"⚠️ {search_source}に類似テキストが見つかりませんでした")
            return
        
        # 最も類似度の高い結果を反映
        top_result = results[0]
        
        # テキストボックスに表示
        if search_source == "PDF":
            self.pdf_text_box.configure(state="normal")
            self.pdf_text_box.delete("1.0", "end")
            self.pdf_text_box.insert("1.0", top_result.candidate_text)
        else:
            self.web_text_box.configure(state="normal")
            self.web_text_box.delete("1.0", "end")
            self.web_text_box.insert("1.0", top_result.candidate_text)
        
        # 類似度表示
        score_pct = top_result.similarity_score * 100
        semantic = "🧠" if top_result.is_semantic_match else "📝"
        
        self.status_label.configure(
            text=f"✅ {len(results)}件の類似発見！最高類似度: {score_pct:.0f}% {semantic} ({top_result.match_reason})"
        )
        
        # 領域をハイライト (結果リストを持つ場合)
        print(f"[GeminiSearch] Found {len(results)} similar regions in {search_source}")
        for r in results[:5]:  # 上位5件をログ出力
            print(f"  - Score: {r.similarity_score:.2f}, Reason: {r.match_reason}")
        
        # スプレッドシート更新
        if hasattr(self, '_refresh_inline_spreadsheet'):
            self._refresh_inline_spreadsheet()

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
        """Run Hybrid OCR and refresh regions/sheet."""
        if not getattr(self, "web_image", None) and not getattr(self, "pdf_image", None):
            self._safe_status("No images loaded")
            return

        self._safe_status("Hybrid OCR running...")

        try:
            from app.core.hybrid_ocr import HybridOCREngine
            engine = HybridOCREngine()

            # Web OCR
            if getattr(self, "web_pages", None):
                self._safe_status(f"Hybrid OCR: Web {len(self.web_pages)} pages")
                res_web = engine.detect_pages_parallel(self.web_pages)
                if not self.winfo_exists():
                    return
                self.web_regions = self._process_ocr_result(res_web, "web")
            elif getattr(self, "web_image", None):
                self._safe_status("Hybrid OCR: Web single page")
                res_web = engine.detect_document_text(self.web_image)
                if not self.winfo_exists():
                    return
                self.web_regions = self._process_ocr_result(res_web, "web")

            # PDF OCR: embedded text first, then OCR fallback
            if getattr(self, "pdf_image", None):
                pdf_embedded_success = False
                pdf_file_path = self._get_pdf_file_path()
                if pdf_file_path:
                    self._safe_status("PDF embedded text extraction...")
                    pdf_embedded_success = self._extract_pdf_embedded_text(pdf_file_path)

                if not self.winfo_exists():
                    return

                if not pdf_embedded_success:
                    pages = getattr(self, "pdf_pages_list", None) or getattr(self, "pdf_pages", None) or []
                    if pages:
                        self._safe_status(f"Hybrid OCR: PDF {len(pages)} pages")
                        res_pdf = engine.detect_pages_parallel(pages)
                        if not self.winfo_exists():
                            return
                        self.pdf_regions = self._process_ocr_result(res_pdf, "pdf")
                    else:
                        self._safe_status("Hybrid OCR: PDF single page")
                        res_pdf = engine.detect_document_text(self.pdf_image)
                        if not self.winfo_exists():
                            return
                        self.pdf_regions = self._process_ocr_result(res_pdf, "pdf")

            if not self.winfo_exists():
                return

            self._safe_status("Sync matching...")
            self._recalculate_sync()
            self._update_area_list()
            self._redraw_regions()
            self._refresh_inline_spreadsheet()

            self._safe_status(f"OCR done: Web {len(self.web_regions)} / PDF {len(self.pdf_regions)}")

        except Exception as e:
            if self.winfo_exists():
                self._safe_status(f"OCR error: {e}")
            print(f"OCR failed: {e}")
            import traceback
            traceback.print_exc()

    def _get_pdf_file_path(self) -> str:
        """親アプリからPDFファイルパスを取得"""
        try:
            # parent_app.comparison_queue から取得
            parent = getattr(self, 'parent_app', None)
            if parent and hasattr(parent, 'comparison_queue'):
                for item in parent.comparison_queue:
                    if item.get('type') == 'pdf':
                        url = item.get('url', '')
                        if url.startswith('file://'):
                            path = url.replace('file://', '').split('#')[0]
                            print(f"[PDF] Found file path: {path}")
                            return path
        except Exception as e:
            print(f"[PDF] Error getting file path: {e}")
        return ""
    
    def _rect_x_overlap_ratio(self, a, b) -> float:
        try:
            ax1, _, ax2, _ = [int(v) for v in a]
            bx1, _, bx2, _ = [int(v) for v in b]
            inter = max(0, min(ax2, bx2) - max(ax1, bx1))
            min_w = max(1, min(ax2 - ax1, bx2 - bx1))
            return inter / min_w
        except Exception:
            return 0.0

    def _merge_pdf_page_candidates(self, candidates):
        """Merge dense PDF blocks with title-paragraph aware grouping."""
        if not candidates:
            return []

        gap_y = int(getattr(self, "pdf_region_merge_gap_px", 28) or 28)
        min_overlap = float(getattr(self, "pdf_region_merge_x_overlap_ratio", 0.35) or 0.35)
        max_per_page = int(getattr(self, "pdf_max_regions_per_page", 240) or 240)

        items = sorted(candidates, key=lambda c: (c["rect"][1], c["rect"][0]))
        merged = []

        # Pass 1: line/block merge + micro-fragment absorption.
        for cand in items:
            rect = [int(v) for v in cand.get("rect", [0, 0, 0, 0])]
            text = str(cand.get("text", "") or "").strip()
            if len(rect) < 4 or not text:
                continue

            if not merged:
                merged.append({"rect": rect, "text": text})
                continue

            prev = merged[-1]
            pr = prev["rect"]
            gap = rect[1] - pr[3]
            overlap = self._rect_x_overlap_ratio(pr, rect)

            prev_area = max(1, (pr[2] - pr[0]) * (pr[3] - pr[1]))
            curr_area = max(1, (rect[2] - rect[0]) * (rect[3] - rect[1]))
            tiny_fragment = min(prev_area, curr_area) < 1800

            should_merge = False
            if gap <= gap_y and overlap >= min_overlap:
                should_merge = True
            elif tiny_fragment and gap <= max(gap_y + 16, 44) and overlap >= max(0.2, min_overlap - 0.15):
                should_merge = True

            if should_merge:
                prev["rect"] = [
                    min(pr[0], rect[0]),
                    min(pr[1], rect[1]),
                    max(pr[2], rect[2]),
                    max(pr[3], rect[3]),
                ]
                if text and text not in prev["text"]:
                    prev["text"] = (prev["text"] + "\n" + text).strip()
            else:
                merged.append({"rect": rect, "text": text})

        if not merged:
            return []

        # Pass 2: title -> paragraph relation simulation (layout-aware grouping).
        x_min = min(m["rect"][0] for m in merged)
        x_max = max(m["rect"][2] for m in merged)
        page_w = max(1, x_max - x_min)

        grouped = []
        i = 0
        while i < len(merged):
            base = merged[i]
            br = list(base["rect"])
            btxt = str(base.get("text", "") or "").strip()
            bw = max(1, br[2] - br[0])
            bh = max(1, br[3] - br[1])
            blen = len(btxt)

            is_title_like = (blen <= 90 and bh <= 150 and bw >= max(220, int(page_w * 0.16)))

            j = i + 1
            while j < len(merged):
                nxt = merged[j]
                nr = nxt["rect"]
                nt = str(nxt.get("text", "") or "").strip()
                if not nt:
                    j += 1
                    continue

                gap = nr[1] - br[3]
                overlap = self._rect_x_overlap_ratio(br, nr)
                nw = max(1, nr[2] - nr[0])

                c1 = (br[0] + br[2]) / 2.0
                c2 = (nr[0] + nr[2]) / 2.0
                center_near = abs(c2 - c1) <= max(220, page_w * 0.30)

                if is_title_like:
                    # Titles often own following paragraph blocks in same lane.
                    if gap <= 120 and overlap >= 0.20 and center_near and nw >= max(80, int(bw * 0.35)):
                        br = [min(br[0], nr[0]), min(br[1], nr[1]), max(br[2], nr[2]), max(br[3], nr[3])]
                        if nt not in btxt:
                            btxt = (btxt + "\n" + nt).strip()
                        j += 1
                        continue
                # General continuation merge for paragraph chunks.
                if gap <= max(gap_y + 18, 46) and overlap >= max(0.22, min_overlap - 0.10) and center_near:
                    br = [min(br[0], nr[0]), min(br[1], nr[1]), max(br[2], nr[2]), max(br[3], nr[3])]
                    if nt not in btxt:
                        btxt = (btxt + "\n" + nt).strip()
                    j += 1
                    continue

                break

            grouped.append({"rect": br, "text": btxt})
            i = j

        # Pass 3: coarse card-level merge for title+body+image layouts (right-side grid pages).
        grouped_before_card = list(grouped)
        card_merged = []
        for item in grouped:
            rect = list(item["rect"])
            txt = str(item.get("text", "") or "").strip()
            if not card_merged:
                card_merged.append({"rect": rect, "text": txt})
                continue

            prev = card_merged[-1]
            pr = prev["rect"]
            gap = rect[1] - pr[3]
            overlap = self._rect_x_overlap_ratio(pr, rect)
            c1 = (pr[0] + pr[2]) / 2.0
            c2 = (rect[0] + rect[2]) / 2.0
            center_near = abs(c2 - c1) <= max(260, page_w * 0.40)

            if gap <= 180 and overlap >= 0.08 and center_near:
                prev["rect"] = [
                    min(pr[0], rect[0]),
                    min(pr[1], rect[1]),
                    max(pr[2], rect[2]),
                    max(pr[3], rect[3]),
                ]
                if txt and txt not in prev["text"]:
                    prev["text"] = (prev["text"] + "\n" + txt).strip()
            else:
                card_merged.append({"rect": rect, "text": txt})

        # Safety valve: if card merge over-collapses regions, rollback.
        use_card_merged = True
        try:
            keep_ratio = float(getattr(self, "pdf_card_merge_min_keep_ratio", 0.45) or 0.45)
            max_area_ratio = float(getattr(self, "pdf_card_merge_max_area_ratio", 0.28) or 0.28)
            if grouped_before_card:
                if len(card_merged) < max(1, int(len(grouped_before_card) * keep_ratio)):
                    use_card_merged = False

            y_min = min(g["rect"][1] for g in grouped_before_card) if grouped_before_card else 0
            y_max = max(g["rect"][3] for g in grouped_before_card) if grouped_before_card else 1
            page_h_est = max(1, y_max - y_min)
            page_area_est = max(1, int(page_w * page_h_est))
            max_rect_area = 0
            for g in card_merged:
                x1, y1, x2, y2 = g["rect"]
                area = max(1, (x2 - x1) * (y2 - y1))
                if area > max_rect_area:
                    max_rect_area = area
            if max_rect_area > int(page_area_est * max_area_ratio):
                use_card_merged = False
        except Exception:
            use_card_merged = True

        grouped = card_merged if use_card_merged else grouped_before_card

        # Filter tiny noise after grouping.
        filtered = []
        min_area = int((getattr(self, "min_region_area_by_source", {}) or {}).get("pdf", 300) or 300)
        for m in grouped:
            x1, y1, x2, y2 = m["rect"]
            area = max(0, x2 - x1) * max(0, y2 - y1)
            txt = str(m.get("text", "") or "").strip()
            if area < min_area:
                continue
            if len(txt) < 2:
                continue
            filtered.append({"rect": [int(x1), int(y1), int(x2), int(y2)], "text": txt})

        if len(filtered) <= max_per_page:
            return filtered

        # Keep informative regions and restore reading order.
        scored = []
        for m in filtered:
            x1, y1, x2, y2 = m["rect"]
            area = max(1, (x2 - x1) * (y2 - y1))
            txt = len(m["text"])
            score = area * (1.0 + min(txt, 260) / 260.0)
            scored.append((score, m))

        scored.sort(key=lambda t: t[0], reverse=True)
        keep = [m for _, m in scored[:max_per_page]]
        keep.sort(key=lambda m: (m["rect"][1], m["rect"][0]))
        return keep

    def _extract_pdf_embedded_text(self, pdf_file_path: str) -> bool:
        """Extract PDF embedded text into page-local regions."""
        import os
        if not pdf_file_path or not os.path.exists(pdf_file_path):
            print(f"[PDF] File not found: {pdf_file_path}")
            return False

        try:
            import fitz

            doc = fitz.open(pdf_file_path)
            total_chars = 0
            self.pdf_regions = []

            PDF_DPI = 300
            DPI_SCALE = PDF_DPI / 72.0
            BBOX_PADDING = 5

            # Build page offsets for stitched-space compatibility.
            self.pdf_page_offsets = [0]
            cumulative = 0
            pages = getattr(self, "pdf_pages_list", None) or getattr(self, "pdf_pages", None) or []
            if pages:
                for page in pages:
                    img = page.get("image") if isinstance(page, dict) else None
                    if img:
                        cumulative += img.height
                        self.pdf_page_offsets.append(cumulative)
            else:
                for page_num in range(min(len(doc), 10)):
                    page = doc.load_page(page_num)
                    cumulative += int(page.rect.height * DPI_SCALE)
                    self.pdf_page_offsets.append(cumulative)

            seq = 0
            for page_num in range(min(len(doc), 10)):
                page = doc.load_page(page_num)
                text_dict = page.get_text("dict")
                page_id = page_num + 1
                page_offset = self.pdf_page_offsets[page_num] if page_num < len(self.pdf_page_offsets) else 0

                page_img = pages[page_num].get("image") if page_num < len(pages) and isinstance(pages[page_num], dict) else None
                if page_img is not None:
                    scale_x = float(page_img.width) / max(1.0, float(page.rect.width))
                    scale_y = float(page_img.height) / max(1.0, float(page.rect.height))
                else:
                    scale_x = DPI_SCALE
                    scale_y = DPI_SCALE

                candidates = []
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue

                    bbox = block.get("bbox", [])
                    if len(bbox) != 4:
                        continue

                    original_rect = fitz.Rect(bbox)
                    expanded_rect = fitz.Rect(
                        original_rect.x0 - BBOX_PADDING,
                        original_rect.y0 - BBOX_PADDING,
                        original_rect.x1 + BBOX_PADDING,
                        original_rect.y1 + BBOX_PADDING,
                    )
                    clip_rect = expanded_rect & page.rect
                    block_text = page.get_text("text", clip=clip_rect).strip()

                    if len(block_text) < 5:
                        continue

                    local_rect = [
                        int(bbox[0] * scale_x),
                        int(bbox[1] * scale_y),
                        int(bbox[2] * scale_x),
                        int(bbox[3] * scale_y),
                    ]
                    candidates.append({"rect": local_rect, "text": block_text})

                merged_regions = self._merge_pdf_page_candidates(candidates)
                for item in merged_regions:
                    seq += 1
                    total_chars += len(item["text"])
                    region = EditableRegion(
                        id=seq,
                        rect=item["rect"],
                        text=item["text"],
                        area_code=f"P{page_id}-{seq:03d}",
                        sync_number=None,
                        similarity=0.0,
                        source="pdf",
                        page_id=page_id,
                        coord_system="local",
                        stitched_y_offset=page_offset,
                    )
                    self.pdf_regions.append(region)

            doc.close()

            if total_chars > 100 and self.pdf_regions:
                print(f"[PDF] Embedded text OK: chars={total_chars}, regions={len(self.pdf_regions)}")
                return True

            print(f"[PDF] Embedded text insufficient: chars={total_chars}")
            return False

        except ImportError:
            print("[PDF] PyMuPDF not installed")
            return False
        except Exception as e:
            print(f"[PDF] Embedded text extraction error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _process_ocr_result(self, result, source):
        """Convert OCR result blocks into EditableRegion list."""
        regions = []
        if not result or "blocks" not in result:
            return regions

        blocks = list(result.get("blocks") or [])
        if not blocks:
            return regions

        def _rect_of(block):
            rect = block.get("bbox") or block.get("rect")
            if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                return None
            try:
                x1, y1, x2, y2 = [int(v) for v in rect]
                if x2 <= x1 or y2 <= y1:
                    return None
                return [x1, y1, x2, y2]
            except Exception:
                return None

        blocks = [b for b in blocks if _rect_of(b) is not None and str(b.get("text", "")).strip()]
        blocks.sort(key=lambda b: (_rect_of(b)[1], _rect_of(b)[0]))

        pdf_offsets = [0]
        cumulative = 0
        pdf_pages = getattr(self, "pdf_pages_list", None) or getattr(self, "pdf_pages", None) or []
        if pdf_pages:
            for p in pdf_pages:
                img = p.get("image") if isinstance(p, dict) else None
                if img:
                    cumulative += int(img.height)
                    pdf_offsets.append(cumulative)

        web_offsets = [0]
        cumulative_web = 0
        web_pages = getattr(self, "web_pages", None) or []
        if source == "web" and web_pages:
            for p in web_pages:
                img = p.get("image") if isinstance(p, dict) else None
                if img:
                    cumulative_web += int(img.height)
                    web_offsets.append(cumulative_web)

        for i, block in enumerate(blocks):
            rect = _rect_of(block)
            if rect is None:
                continue
            text = str(block.get("text", "")).strip()
            seq = i + 1

            if source == "web":
                if "page_index" in block:
                    page_id = int(block.get("page_index", 0)) + 1
                else:
                    # Infer page by y-center for stitched coordinates when page_index is missing.
                    y_center = (rect[1] + rect[3]) / 2
                    page_id = int(getattr(self, "current_pdf_idx", 0) or 0) + 1
                    if len(pdf_offsets) > 1:
                        for p_idx in range(len(pdf_offsets) - 1):
                            if pdf_offsets[p_idx] <= y_center < pdf_offsets[p_idx + 1]:
                                page_id = p_idx + 1
                                break
                        else:
                            page_id = max(1, len(pdf_offsets) - 1)

                    page_offset = (
                        pdf_offsets[page_id - 1]
                        if 0 <= page_id - 1 < len(pdf_offsets)
                        else self._get_page_y_offset_for_source("pdf", page_id)
                    )
                    local_rect = [rect[0], rect[1] - page_offset, rect[2], rect[3] - page_offset]
                    if local_rect[1] < 0 or local_rect[3] < 0:
                        local_rect = rect


                region = EditableRegion(
                    id=seq,
                    rect=[int(local_rect[0]), int(local_rect[1]), int(local_rect[2]), int(local_rect[3])],
                    text=text,
                    area_code=f"P{page_id}-{seq:03d}",
                    sync_number=None,
                    similarity=0.0,
                    source="pdf",
                    page_id=page_id,
                    coord_system="local",
                    stitched_y_offset=int(page_offset),
                )

            regions.append(region)

        print(f"[OCR] _process_ocr_result source={source} regions={len(regions)}")
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
