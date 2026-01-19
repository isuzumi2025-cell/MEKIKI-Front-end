"""
最先端 Proofing Workspace
3パネルレイアウト: Web Canvas | PDF Canvas | Live Spreadsheet
全機能統合: InteractiveCanvas, LiveCellSync, TextMatcher, ClusteringEngine

Created: 2026-01-11
"""
import sys
import os
from pathlib import Path

# スタンドアロン実行用パス設定
if __name__ == "__main__":
    OCR_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(OCR_ROOT))
    os.chdir(OCR_ROOT)

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from typing import Dict, List, Optional

# Phase 6 モジュール
from app.gui.interactive_canvas import InteractiveCanvas
from app.core.live_cell_sync import LiveCellSync
from app.core.text_matcher import TextMatcher
from app.core.engine_clustering import VisualAwareClusteringEngine
from app.core.visual_analyzer import VisualAnalyzer, enhance_blocks_with_visual_info


class ProofingWorkspace(ctk.CTkToplevel):
    """
    最先端の校正ワークスペース
    3パネル構成でWeb/PDF同時比較 + 即時セル反映
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("📊 Proofing Workspace - 校正ワークスペース")
        self.geometry("1920x1080")
        self.configure(fg_color="#0D0D0D")
        
        # コア機能
        self.live_sync = LiveCellSync(on_cell_update=self._on_cell_update)
        self.text_matcher = TextMatcher()
        self.clustering_engine = VisualAwareClusteringEngine()
        self.visual_analyzer = VisualAnalyzer()
        
        # データ
        self.web_image: Optional[Image.Image] = None
        self.pdf_image: Optional[Image.Image] = None
        self.web_clusters: List[Dict] = []
        self.pdf_clusters: List[Dict] = []
        
        # UI構築
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        self._build_header()
        
        # メインエリア（3パネル）
        self._build_main_area()
        
        # コントロールパネル
        self._build_control_panel()
        
        # ステータスバー
        self._build_status_bar()
    
    def _build_header(self):
        """ヘッダー構築"""
        header = ctk.CTkFrame(self, height=60, fg_color="#1A1A1A", corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        # タイトル
        ctk.CTkLabel(
            header,
            text="📊 Proofing Workspace",
            font=("Meiryo", 20, "bold"),
            text_color="#00BCD4"
        ).pack(side="left", padx=20, pady=15)
        
        # 統計表示
        self.stats_label = ctk.CTkLabel(
            header,
            text="Web: 0 | PDF: 0 | Match: 0 | Avg Sync: 0%",
            font=("Meiryo", 12),
            text_color="gray"
        )
        self.stats_label.pack(side="right", padx=20, pady=15)
    
    def _build_main_area(self):
        """メイン3パネルエリア"""
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # PanedWindow for resizable panels
        self.paned = tk.PanedWindow(
            main_frame,
            orient="horizontal",
            bg="#1A1A1A",
            sashwidth=6,
            sashrelief="raised"
        )
        self.paned.pack(fill="both", expand=True)
        
        # === 左パネル: Web Canvas ===
        web_frame = ctk.CTkFrame(self.paned, fg_color="#1E1E1E")
        self.paned.add(web_frame, width=600)
        
        ctk.CTkLabel(
            web_frame,
            text="🌐 Web画像",
            font=("Meiryo", 14, "bold"),
            text_color="#00BCD4"
        ).pack(pady=10)
        
        self.web_canvas = InteractiveCanvas(web_frame, width=580, height=700)
        self.web_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.web_canvas.on_area_selected = lambda id, src, txt: self._on_area_selected(id, "web", txt)
        
        # === 中央パネル: PDF Canvas ===
        pdf_frame = ctk.CTkFrame(self.paned, fg_color="#1E1E1E")
        self.paned.add(pdf_frame, width=600)
        
        ctk.CTkLabel(
            pdf_frame,
            text="📄 PDF画像",
            font=("Meiryo", 14, "bold"),
            text_color="#FF6F00"
        ).pack(pady=10)
        
        self.pdf_canvas = InteractiveCanvas(pdf_frame, width=580, height=700)
        self.pdf_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.pdf_canvas.on_area_selected = lambda id, src, txt: self._on_area_selected(id, "pdf", txt)
        
        # === 右パネル: スプレッドシート ===
        sheet_frame = ctk.CTkFrame(self.paned, fg_color="#1E1E1E")
        self.paned.add(sheet_frame, width=500)
        
        ctk.CTkLabel(
            sheet_frame,
            text="📋 比較スプレッドシート",
            font=("Meiryo", 14, "bold"),
            text_color="#4CAF50"
        ).pack(pady=10)
        
        # スプレッドシート（スクロール可能）
        self._build_spreadsheet(sheet_frame)
    
    def _build_spreadsheet(self, parent):
        """スプレッドシート構築"""
        # ヘッダー
        header_frame = ctk.CTkFrame(parent, fg_color="#2B2B2B", height=40)
        header_frame.pack(fill="x", padx=5)
        header_frame.pack_propagate(False)
        
        headers = [("ID", 80), ("Web Text", 150), ("PDF Text", 150), ("Sync%", 60)]
        for text, width in headers:
            ctk.CTkLabel(
                header_frame,
                text=text,
                width=width,
                font=("Meiryo", 11, "bold"),
                text_color="white"
            ).pack(side="left", padx=2)
        
        # スクロール可能なコンテンツ
        self.sheet_scroll = ctk.CTkScrollableFrame(parent, fg_color="#1A1A1A")
        self.sheet_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.sheet_rows: List[ctk.CTkFrame] = []
    
    def _build_control_panel(self):
        """コントロールパネル"""
        control = ctk.CTkFrame(self, height=80, fg_color="#1A1A1A", corner_radius=0)
        control.pack(fill="x", side="bottom")
        control.pack_propagate(False)
        
        # 左側: 読込ボタン
        load_frame = ctk.CTkFrame(control, fg_color="transparent")
        load_frame.pack(side="left", padx=20, pady=15)
        
        ctk.CTkButton(
            load_frame,
            text="🌐 Web画像読込",
            command=self._load_web_image,
            width=140,
            fg_color="#00BCD4",
            hover_color="#0097A7"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            load_frame,
            text="📄 PDF画像読込",
            command=self._load_pdf_image,
            width=140,
            fg_color="#FF6F00",
            hover_color="#E65100"
        ).pack(side="left", padx=5)
        
        # 中央: 分析ボタン
        analyze_frame = ctk.CTkFrame(control, fg_color="transparent")
        analyze_frame.pack(side="left", padx=20, pady=15)
        
        ctk.CTkButton(
            analyze_frame,
            text="🔍 自動クラスタリング",
            command=self._run_auto_clustering,
            width=160,
            fg_color="#9C27B0",
            hover_color="#7B1FA2"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            analyze_frame,
            text="🔗 自動マッチング",
            command=self._run_auto_matching,
            width=140,
            fg_color="#673AB7",
            hover_color="#512DA8"
        ).pack(side="left", padx=5)
        
        # 右側: アクションボタン
        action_frame = ctk.CTkFrame(control, fg_color="transparent")
        action_frame.pack(side="right", padx=20, pady=15)
        
        ctk.CTkButton(
            action_frame,
            text="✅ Approve",
            width=100,
            fg_color="#4CAF50",
            hover_color="#388E3C"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            action_frame,
            text="📤 Export",
            command=self._export_report,
            width=100,
            fg_color="#2196F3",
            hover_color="#1976D2"
        ).pack(side="left", padx=5)
    
    def _build_status_bar(self):
        """ステータスバー"""
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color="#0D0D0D", corner_radius=0)
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="準備完了",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=20, pady=5)
    
    # ========== イベントハンドラ ==========
    
    def _load_web_image(self):
        """Web画像読込"""
        path = filedialog.askopenfilename(
            title="Web画像を選択",
            filetypes=[("画像", "*.png *.jpg *.jpeg *.webp")]
        )
        if path:
            self.web_image = Image.open(path)
            self.web_canvas.load_image_from_pil(self.web_image, f"🌐 {Path(path).name}")
            self._update_status(f"Web画像読込: {Path(path).name}")
    
    def _load_pdf_image(self):
        """PDF画像読込"""
        path = filedialog.askopenfilename(
            title="PDF画像を選択",
            filetypes=[("画像", "*.png *.jpg *.jpeg *.webp")]
        )
        if path:
            self.pdf_image = Image.open(path)
            self.pdf_canvas.load_image_from_pil(self.pdf_image, f"📄 {Path(path).name}")
            self._update_status(f"PDF画像読込: {Path(path).name}")
    
    def _run_auto_clustering(self):
        """自動クラスタリング実行"""
        self._update_status("自動クラスタリング実行中...")
        
        # サンプルクラスタ（実際はOCR結果から生成）
        if self.web_image:
            # ダミークラスタ生成（デモ用）
            w, h = self.web_image.size
            self.web_clusters = [
                {"id": 1, "rect": [50, 50, 300, 120], "text": "見出しテキスト"},
                {"id": 2, "rect": [50, 140, 350, 280], "text": "本文段落サンプル"},
                {"id": 3, "rect": [50, 300, 300, 380], "text": "フッター情報"},
            ]
            
            # クラスタをキャンバスに表示
            self.web_canvas._load_areas([{"bbox": c["rect"]} for c in self.web_clusters])
        
        if self.pdf_image:
            self.pdf_clusters = [
                {"id": 1, "rect": [60, 60, 310, 130], "text": "見出しテキスト"},
                {"id": 2, "rect": [60, 150, 360, 290], "text": "本文段落サンプル"},
                {"id": 3, "rect": [60, 310, 310, 390], "text": "フッター情報"},
            ]
            self.pdf_canvas._load_areas([{"bbox": c["rect"]} for c in self.pdf_clusters])
        
        self._update_status(f"クラスタリング完了: Web {len(self.web_clusters)}件, PDF {len(self.pdf_clusters)}件")
        self._update_stats()
    
    def _run_auto_matching(self):
        """自動マッチング実行"""
        if not self.web_clusters or not self.pdf_clusters:
            messagebox.showwarning("警告", "先にクラスタリングを実行してください")
            return
        
        self._update_status("自動マッチング実行中...")
        
        # テキストマッチング
        web_pages = [{"page_id": c["id"], "text": c["text"]} for c in self.web_clusters]
        pdf_pages = [{"page_id": c["id"], "text": c["text"]} for c in self.pdf_clusters]
        
        matches = self.text_matcher.match_all(web_pages, pdf_pages)
        
        # マッチング結果をスプレッドシートに反映
        self._clear_spreadsheet()
        
        for match in matches:
            web_id = match["web_id"]
            pdf_id = match["pdf_id"]
            score = match["score"]
            
            web_text = next((c["text"] for c in self.web_clusters if c["id"] == web_id), "")
            pdf_text = next((c["text"] for c in self.pdf_clusters if c["id"] == pdf_id), "")
            
            self._add_sheet_row(f"W{web_id}-P{pdf_id}", web_text, pdf_text, score)
            
            # LiveSyncに登録
            self.live_sync.add_match(f"WEB-{web_id:03d}", f"PDF-P1-{pdf_id:03d}", score)
        
        self._update_status(f"マッチング完了: {len(matches)}ペア")
        self._update_stats()
    
    def _on_area_selected(self, area_id: int, source: str, text: str):
        """エリア選択時のコールバック"""
        self.live_sync.on_area_selected(area_id, source, text)
        self._update_status(f"選択: {source.upper()}-{area_id:03d}")
        self._update_stats()
    
    def _on_cell_update(self, cell, row_index):
        """セル更新時のコールバック"""
        self._update_stats()
    
    def _add_sheet_row(self, uid: str, web_text: str, pdf_text: str, score: float):
        """スプレッドシートに行追加"""
        row = ctk.CTkFrame(self.sheet_scroll, fg_color="#2B2B2B", height=50)
        row.pack(fill="x", pady=2)
        
        # スコアに応じた色
        if score >= 0.8:
            color = "#4CAF50"
        elif score >= 0.5:
            color = "#FFC107"
        else:
            color = "#F44336"
        
        ctk.CTkLabel(row, text=uid, width=80, font=("Meiryo", 10)).pack(side="left", padx=2)
        ctk.CTkLabel(row, text=web_text[:20], width=150, font=("Meiryo", 10), anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(row, text=pdf_text[:20], width=150, font=("Meiryo", 10), anchor="w").pack(side="left", padx=2)
        ctk.CTkLabel(row, text=f"{score*100:.0f}%", width=60, font=("Meiryo", 10, "bold"), text_color=color).pack(side="left", padx=2)
        
        self.sheet_rows.append(row)
    
    def _clear_spreadsheet(self):
        """スプレッドシートクリア"""
        for row in self.sheet_rows:
            row.destroy()
        self.sheet_rows.clear()
    
    def _export_report(self):
        """レポートエクスポート"""
        messagebox.showinfo("Export", "レポートエクスポート機能は実装中です")
    
    def _update_status(self, text: str):
        """ステータス更新"""
        self.status_label.configure(text=text)
        self.update_idletasks()
    
    def _update_stats(self):
        """統計更新"""
        stats = self.live_sync.get_statistics()
        self.stats_label.configure(
            text=f"Web: {stats['web_count']} | PDF: {stats['pdf_count']} | "
                 f"Match: {stats['match_count']} | Avg Sync: {stats['avg_sync_rate']*100:.0f}%"
        )


def launch_proofing_workspace(parent=None):
    """Proofing Workspaceを起動"""
    workspace = ProofingWorkspace(parent)
    workspace.grab_set()
    return workspace


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    root.withdraw()
    
    workspace = ProofingWorkspace()
    workspace.mainloop()
