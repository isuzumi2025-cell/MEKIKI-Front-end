"""
スプレッドシートビュー - OCR結果をテーブル形式で表示
リアルタイム編集 + Excel出力対応
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass


@dataclass
class SpreadsheetRow:
    """スプレッドシートの1行"""
    id: str
    source: str  # "web" or "pdf"
    page: int
    text: str
    match_id: Optional[str]
    similarity: float
    rect: List[int]
    
    @property
    def text_preview(self) -> str:
        """テキストプレビュー (100文字)"""
        text = self.text.replace('\n', ' ').strip()
        return text[:100] + "..." if len(text) > 100 else text
    
    @property
    def status_icon(self) -> str:
        if self.similarity >= 0.5:
            return "🟢"
        elif self.similarity >= 0.3:
            return "🟡"
        elif self.match_id:
            return "🔴"
        else:
            return "⚪"


class SpreadsheetView(ctk.CTkFrame):
    """
    スプレッドシート形式のOCR結果表示ウィジェット
    - TreeViewによるテーブル表示
    - ダブルクリックで詳細ビューへ連携
    - リアルタイム編集対応
    """
    
    def __init__(self, parent, on_row_select: Callable = None, **kwargs):
        super().__init__(parent, fg_color="#1E1E1E", **kwargs)
        
        self.on_row_select = on_row_select  # 行選択時のコールバック
        self.rows: List[SpreadsheetRow] = []
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#2D2D2D", height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="📊 パラグラフ一覧",
            font=("Meiryo", 12, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        # カウント表示
        self.count_label = ctk.CTkLabel(
            header,
            text="0件",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.count_label.pack(side="left", padx=10)
        
        # フィルターボタン
        filter_frame = ctk.CTkFrame(header, fg_color="transparent")
        filter_frame.pack(side="right", padx=10)
        
        self.filter_var = ctk.StringVar(value="all")
        
        for text, value in [("全て", "all"), ("Web", "web"), ("PDF", "pdf"), ("マッチ", "match")]:
            ctk.CTkRadioButton(
                filter_frame,
                text=text,
                variable=self.filter_var,
                value=value,
                font=("Meiryo", 9),
                command=self._apply_filter
            ).pack(side="left", padx=5)
        
        # TreeView (スプレッドシート本体)
        tree_frame = ctk.CTkFrame(self, fg_color="#1E1E1E")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # スタイル設定
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Spreadsheet.Treeview",
            background="#2B2B2B",
            foreground="white",
            fieldbackground="#2B2B2B",
            font=("Meiryo", 9),
            rowheight=28
        )
        style.configure(
            "Spreadsheet.Treeview.Heading",
            background="#383838",
            foreground="white",
            font=("Meiryo", 9, "bold")
        )
        style.map(
            "Spreadsheet.Treeview",
            background=[("selected", "#4A6785")]
        )
        
        # TreeView作成
        columns = ("source", "page", "text", "match", "similarity")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Spreadsheet.Treeview",
            selectmode="browse"
        )
        
        # カラム設定
        self.tree.heading("source", text="Source")
        self.tree.heading("page", text="Page")
        self.tree.heading("text", text="Text")
        self.tree.heading("match", text="Match")
        self.tree.heading("similarity", text="Sync")
        
        self.tree.column("source", width=60, anchor="center")
        self.tree.column("page", width=50, anchor="center")
        self.tree.column("text", width=400, anchor="w")
        self.tree.column("match", width=80, anchor="center")
        self.tree.column("similarity", width=80, anchor="center")
        
        # スクロールバー
        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 配置
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        
        # イベントバインド
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)
    
    def load_data(self, web_regions: List, pdf_regions: List):
        """
        データをロード
        
        Args:
            web_regions: WebのEditableRegionリスト
            pdf_regions: PDFのEditableRegionリスト
        """
        self.rows = []
        
        # Webデータ
        for region in web_regions:
            row = SpreadsheetRow(
                id=region.area_code,
                source="web",
                page=int(region.area_code.split('-')[0].replace('P', '')) if '-' in region.area_code else 1,
                text=region.text,
                match_id=getattr(region, 'sync_id', None),
                similarity=getattr(region, 'similarity', 0.0),
                rect=list(region.rect)
            )
            self.rows.append(row)
        
        # PDFデータ
        for region in pdf_regions:
            row = SpreadsheetRow(
                id=region.area_code,
                source="pdf",
                page=1,
                text=region.text,
                match_id=getattr(region, 'sync_id', None),
                similarity=getattr(region, 'similarity', 0.0),
                rect=list(region.rect)
            )
            self.rows.append(row)
        
        self._refresh_tree()
    
    def _refresh_tree(self):
        """TreeViewを更新"""
        # 既存データクリア
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # フィルター適用
        filter_value = self.filter_var.get()
        filtered_rows = self._filter_rows(filter_value)
        
        # データ追加
        for row in filtered_rows:
            values = (
                f"{row.status_icon} {row.source.upper()}",
                row.page,
                row.text_preview,
                row.match_id or "-",
                f"{row.similarity*100:.0f}%" if row.similarity > 0 else "-"
            )
            self.tree.insert("", "end", iid=row.id, values=values)
        
        # カウント更新
        self.count_label.configure(text=f"{len(filtered_rows)}件 / 全{len(self.rows)}件")
    
    def _filter_rows(self, filter_value: str) -> List[SpreadsheetRow]:
        """フィルター適用"""
        if filter_value == "all":
            return self.rows
        elif filter_value == "web":
            return [r for r in self.rows if r.source == "web"]
        elif filter_value == "pdf":
            return [r for r in self.rows if r.source == "pdf"]
        elif filter_value == "match":
            return [r for r in self.rows if r.match_id]
        return self.rows
    
    def _apply_filter(self):
        """フィルター変更時"""
        self._refresh_tree()
    
    def _on_select(self, event):
        """行選択時"""
        selection = self.tree.selection()
        if selection and self.on_row_select:
            row_id = selection[0]
            row = next((r for r in self.rows if r.id == row_id), None)
            if row:
                self.on_row_select(row, "select")
    
    def _on_double_click(self, event):
        """ダブルクリック時 → 詳細ビューへ"""
        selection = self.tree.selection()
        if selection and self.on_row_select:
            row_id = selection[0]
            row = next((r for r in self.rows if r.id == row_id), None)
            if row:
                self.on_row_select(row, "double_click")
    
    def highlight_row(self, row_id: str):
        """指定行をハイライト"""
        self.tree.selection_set(row_id)
        self.tree.see(row_id)
    
    def update_row(self, row_id: str, **kwargs):
        """行を更新（リアルタイム編集用）"""
        for row in self.rows:
            if row.id == row_id:
                for key, value in kwargs.items():
                    if hasattr(row, key):
                        setattr(row, key, value)
                break
        self._refresh_tree()
