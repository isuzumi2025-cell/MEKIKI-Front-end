"""
着脱式ナビゲーションパネル
メニューボタン群を管理し、ドッキング/フローティング切り替えに対応
"""
import customtkinter as ctk


class NavigationPanel:
    """ナビゲーションパネルクラス - メニューボタン群を管理"""
    
    def __init__(self, parent, callbacks):
        """
        Args:
            parent: 親ウィジェット（CTkFrameまたはCTkToplevel）
            callbacks: コールバック関数の辞書
                - load_file: 画像読み込み
                - open_web_dialog: Web読込ダイアログ
                - save_project: プロジェクト保存
                - load_project: プロジェクト読込
                - run_ocr: AI解析実行
                - export_csv: CSV出力
                - open_gsheet_dialog: Google Sheets出力
                - open_comparison_mode: 比較モード
                - toggle_detach: ウィンドウ分離/結合
                - toggle_panel_dock: パレット分離/結合（オプション）
        """
        self.parent = parent
        self.callbacks = callbacks
        self.frame = None
        self.switch_partial_ocr = None
        self.seg_view_mode = None
        self.btn_run = None
        self.progress = None
        
        # ウィジェット参照を保持するための辞書
        self.widgets = {}
        
        self._build_panel()
    
    def _build_panel(self):
        """パネルを構築"""
        self.frame = ctk.CTkFrame(self.parent, width=200, corner_radius=0)
        
        # パレット分離/結合ボタン（最上部）
        btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        if "open_project_mode" in self.callbacks:
            ctk.CTkButton(
                btn_frame, 
                text="🏠 プロジェクト管理", 
                command=self.callbacks["open_project_mode"],
                width=180,
                fg_color="#1F6AA5",
                height=35
            ).pack(fill="x", pady=(0, 5))
        
        if "open_dashboard" in self.callbacks:
            ctk.CTkButton(
                btn_frame, 
                text="📊 Dashboard (NEW)", 
                command=self.callbacks["open_dashboard"],
                width=180,
                fg_color="#9C27B0",
                height=35
            ).pack(fill="x", pady=(0, 5))
        
        if "toggle_panel_dock" in self.callbacks:
            self.btn_dock = ctk.CTkButton(
                btn_frame, 
                text="🗔 パレット分離", 
                command=self.callbacks["toggle_panel_dock"],
                width=180,
                fg_color="#555",
                height=30
            )
            self.btn_dock.pack(fill="x")
        
        # セパレーター
        ctk.CTkFrame(self.frame, height=2, fg_color="gray").pack(fill="x", padx=10, pady=5)
        
        # 【読込】セクション
        self._build_section_header("📂 読込")
        
        ctk.CTkButton(
            self.frame, 
            text="画像/PDF", 
            command=self.callbacks["load_file"],
            width=180,
            height=30
        ).pack(pady=3, padx=10)
        
        ctk.CTkButton(
            self.frame, 
            text="🌐 Web読込", 
            command=self.callbacks["open_web_dialog"],
            width=180,
            height=30,
            fg_color="#E08E00"
        ).pack(pady=3, padx=10)
        
        # セパレーター
        ctk.CTkFrame(self.frame, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【編集】セクション
        self._build_section_header("✏️ 編集")
        
        self.btn_run = ctk.CTkButton(
            self.frame, 
            text="▶ 全体AI解析", 
            command=self.callbacks["run_ocr"],
            width=180,
            height=35,
            fg_color="#1F6AA5"
        )
        self.btn_run.pack(pady=5, padx=10)
        
        # 範囲指定OCRスイッチ
        switch_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        switch_frame.pack(fill="x", padx=10, pady=3)
        self.switch_partial_ocr = ctk.CTkSwitch(
            switch_frame, 
            text="範囲指定OCR",
            width=180
        )
        self.switch_partial_ocr.pack(anchor="w")
        
        # Web表示切替（初期状態は無効）
        self.seg_view_mode = ctk.CTkSegmentedButton(
            self.frame, 
            values=["全体", "1画面"], 
            command=self.callbacks.get("switch_view_mode", lambda x: None)
        )
        self.seg_view_mode.set("全体")
        self.seg_view_mode.pack(pady=5, padx=10, fill="x")
        self.seg_view_mode.configure(state="disabled")
        
        # セパレーター
        ctk.CTkFrame(self.frame, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【比較】セクション
        self._build_section_header("⚖️ 比較")
        
        ctk.CTkButton(
            self.frame, 
            text="比較モード", 
            command=self.callbacks["open_comparison_mode"],
            width=180,
            height=30,
            fg_color="#8B4513"
        ).pack(pady=3, padx=10)
        
        # セパレーター
        ctk.CTkFrame(self.frame, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【出力】セクション
        self._build_section_header("💾 出力")
        
        ctk.CTkButton(
            self.frame, 
            text="プロジェクト保存", 
            command=self.callbacks["save_project"],
            width=180,
            height=30,
            fg_color="gray"
        ).pack(pady=3, padx=10)
        
        ctk.CTkButton(
            self.frame, 
            text="プロジェクト読込", 
            command=self.callbacks["load_project"],
            width=180,
            height=30,
            fg_color="gray"
        ).pack(pady=3, padx=10)
        
        ctk.CTkButton(
            self.frame, 
            text="CSV出力", 
            command=self.callbacks["export_csv"],
            width=180,
            height=30
        ).pack(pady=3, padx=10)
        
        ctk.CTkButton(
            self.frame, 
            text="Google Sheets", 
            command=self.callbacks["open_gsheet_dialog"],
            width=180,
            height=30,
            fg_color="#207f4c"
        ).pack(pady=3, padx=10)
        
        # セパレーター
        ctk.CTkFrame(self.frame, height=2, fg_color="gray").pack(fill="x", padx=10, pady=8)
        
        # 【ウィンドウ】セクション
        self._build_section_header("🗔 ウィンドウ")
        
        ctk.CTkButton(
            self.frame, 
            text="テキスト分離/結合", 
            command=self.callbacks.get("toggle_detach", lambda: None),
            width=180,
            height=30,
            fg_color="#555"
        ).pack(pady=3, padx=10)
        
        # プログレスバー（下部に配置）
        self.progress = ctk.CTkProgressBar(
            self.frame, 
            mode='indeterminate', 
            width=180,
            height=20
        )
        self.progress.pack(pady=10, padx=10, fill="x")
        
        # 初期状態では非表示
        self.progress.pack_forget()
    
    def _build_section_header(self, text):
        """セクションヘッダーを作成"""
        header = ctk.CTkLabel(
            self.frame, 
            text=text, 
            font=("Arial", 11, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=10, pady=(5, 2))
    
    def pack(self, **kwargs):
        """パネルを表示"""
        self.frame.pack(**kwargs)
    
    def pack_forget(self):
        """パネルを非表示"""
        self.frame.pack_forget()
    
    def destroy(self):
        """パネルを破棄"""
        if self.frame:
            self.frame.destroy()

