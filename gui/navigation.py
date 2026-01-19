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
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            header,
            text="🎛️ 操作パネル",
            font=("Meiryo", 14, "bold")
        ).pack(anchor="w")
        
        # セパレーター
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=5)
        
        # 【新規プロジェクト】ボタン（最上部、目立つ色）
        self._build_button(
            "➕ 新規プロジェクト",
            self.callbacks.get("new_project"),
            fg_color="#FF6F00"
        )
        
        # セパレーター
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【ビュー】セクション
        self._build_section("🗺️ ビュー")
        
        self._build_button(
            "🗺️ 全体マップ",
            self.callbacks.get("show_macro_view"),
            fg_color="#4CAF50"
        )
        
        # セパレーター
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【読込】セクション
        self._build_section("📂 読込")
        
        self._build_button(
            "🌐 Web一括クロール",
            self.callbacks.get("crawl_web"),
            fg_color="#E08E00"
        )
        
        self._build_button(
            "📁 PDF一括読込",
            self.callbacks.get("load_pdfs"),
            fg_color="#4CAF50"
        )
        
        # セパレーター
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【処理】セクション
        self._build_section("⚙️ 処理")
        
        self._build_button(
            "⚡ 一括マッチング",
            self.callbacks.get("match_all"),
            fg_color="#9C27B0"
        )
        
        self._build_button(
            "🔍 OCR実行",
            self.callbacks.get("run_ocr"),
            fg_color="#2196F3"
        )
        
        # セパレーター
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【出力】セクション
        self._build_section("💾 出力")
        
        self._build_button(
            "📤 Excel出力",
            self.callbacks.get("export_excel"),
            fg_color="#207f4c"
        )
        
        self._build_button(
            "💾 プロジェクト保存",
            self.callbacks.get("save_project"),
            fg_color="gray"
        )
        
        # セパレーター
        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【設定】セクション
        self._build_section("⚙️ 設定")
        
        self._build_button(
            "📂 プロジェクト読込",
            self.callbacks.get("load_project"),
            fg_color="gray"
        )
        
        # プログレスバー（下部）
        self.progress = ctk.CTkProgressBar(
            self,
            mode='indeterminate',
            width=180,
            height=20
        )
        self.progress.pack(side="bottom", pady=10, padx=10, fill="x")
        self.progress.pack_forget()  # 初期状態で非表示
    
    def _build_section(self, title: str):
        """セクションヘッダーを作成"""
        ctk.CTkLabel(
            self,
            text=title,
            font=("Meiryo", 11, "bold"),
            anchor="w"
        ).pack(fill="x", padx=10, pady=(5, 2))
    
    def _build_button(
        self,
        text: str,
        command: Callable,
        fg_color: str = "#1F6AA5"
    ):
        """ボタンを作成"""
        ctk.CTkButton(
            self,
            text=text,
            command=command if command else lambda: None,
            width=180,
            height=35,
            fg_color=fg_color
        ).pack(pady=3, padx=10)
    
    def show_progress(self):
        """プログレスバーを表示"""
        self.progress.pack(side="bottom", pady=10, padx=10, fill="x")
        self.progress.start()
    
    def hide_progress(self):
        """プログレスバーを非表示"""
        self.progress.stop()
        self.progress.pack_forget()

