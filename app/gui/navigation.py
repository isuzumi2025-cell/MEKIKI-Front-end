"""
Navigation Module
ナビゲーションパネル - メニューボタン、操作パネル
"""
import customtkinter as ctk
from typing import Dict, Callable


class NavigationPanel(ctk.CTkFrame):
    """
    ナビゲーションパネル
    主要な操作ボタンを配置
    """
    
    def __init__(
        self,
        master,
        callbacks: Dict[str, Callable],
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            callbacks: コールバック関数の辞書
        """
        super().__init__(master, **kwargs)
        
        self.callbacks = callbacks
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ロゴエリア
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            logo_frame,
            text="👁️ MEKIKI",
            font=("Inter", 24, "bold"),
            text_color=("gray10", "white")
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            logo_frame,
            text="Genius Edition",
            font=("Inter", 12),
            text_color=("gray50", "gray70")
        ).pack(anchor="w", pady=(0, 10))
        
        # メインスクロールコンテナ (項目が多い場合に対応)
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            width=260
        )
        self.scroll_frame.pack(fill="both", expand=True)
        
        # --- メインアクション ---
        self._build_section_header("MAIN ACTIONS")
        
        self._build_sidebar_button(
            "➕ New Project",
            self.callbacks.get("new_project"),
            icon="✨",
            fg_color=("#FF8F00", "#FF6F00")
        )
        
        self._build_sidebar_button(
            "🗺️ Dashboard",
            self.callbacks.get("show_macro_view"),
            icon="📊"
        )
        
        # --- データ取り込み ---
        self._build_section_header("DATA SOURCES")
        
        self._build_sidebar_button(
            "🌐 Web Crawler",
            self.callbacks.get("crawl_web"),
            icon="🌍"
        )
        
        self._build_sidebar_button(
            "📄 Load PDFs",
            self.callbacks.get("load_pdfs"),
            icon="📁"
        )
        
        # --- 分析 & AI ---
        self._build_section_header("INTELLIGENCE")
        
        self._build_sidebar_button(
            "⚡ Auto Match",
            self.callbacks.get("match_all"),
            icon="🔄",
            fg_color=("#8E24AA", "#AB47BC")
        )
        
        self._build_sidebar_button(
            "🧠 Gemini OCR",
            self.callbacks.get("run_ocr"),
            icon="🤖",
            fg_color=("#1565C0", "#1976D2")
        )
        
        # --- 出力 & 管理 ---
        self._build_section_header("EXPORT & MANAGE")

        self._build_sidebar_button(
            "📤 Export Excel",
            self.callbacks.get("export_excel"),
            icon="📊"
        )

        self._build_sidebar_button(
            "💾 Save Project",
            self.callbacks.get("save_project"),
            icon="💾",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90")
        )

        # --- 設定 ---
        self._build_section_header("SETTINGS")

        self._build_sidebar_button(
            "⚙️ API Settings",
            self.callbacks.get("open_settings"),
            icon="🔐",
            fg_color=("#455A64", "#37474F")
        )
         
        # プログレスバー（最下部固定）
        self.progress = ctk.CTkProgressBar(
            self,
            mode='indeterminate',
            height=10,
            corner_radius=0
        )
        self.progress.pack_forget()  # pack_forgetで初期は隠す
    
    def _build_section_header(self, title: str):
        """セクションヘッダー"""
        ctk.CTkLabel(
            self.scroll_frame,
            text=title,
            font=("Inter", 11, "bold"),
            text_color=("gray50", "gray60"),
            anchor="w"
        ).pack(fill="x", padx=20, pady=(15, 5))
    
    def _build_sidebar_button(
        self,
        text: str,
        command: Callable,
        icon: str = "",
        fg_color: str = "transparent",
        hover_color: str = None,
        text_color: str = None,
        border_width: int = 0
    ):
        """サイドバースタイルのボタン"""
        # デフォルトの透明/グレー
        if fg_color == "transparent":
            text_color = text_color or ("gray10", "gray90")
            hover_color = hover_color or ("gray80", "gray30")
        else:
            text_color = text_color or "white"
            
        ctk.CTkButton(
            self.scroll_frame,
            text=f"  {icon}  {text}",
            command=command if command else lambda: None,
            width=220,
            height=40,
            corner_radius=8,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=border_width,
            border_color=("gray70", "gray50"),
            font=("Inter", 13),
            anchor="w"
        ).pack(padx=15, pady=4)

    def show_progress(self):
        """プログレスバーを表示"""
        self.progress.pack(side="bottom", fill="x", padx=0, pady=0)
        self.progress.start()
    
    def hide_progress(self):
        """プログレスバーを非表示"""
        self.progress.stop()
        self.progress.pack_forget()

