"""
Phase 3: Inspector (Comparison) 画面
詳細比較画面 - 同期スクロール対応
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import Dict
from PIL import Image
from pathlib import Path

from app.gui.sync_scroll_canvas import SyncScrollCanvas


class Inspector(ctk.CTkToplevel):
    """Phase 3: 詳細比較画面（Inspector）"""
    
    def __init__(
        self,
        parent,
        web_page: Dict,
        pdf_page: Dict
    ):
        """
        Args:
            parent: 親ウィンドウ
            web_page: Webページデータ {"id": int, "url": str, "title": str, "image": Image, ...}
            pdf_page: PDFページデータ {"id": int, "filename": str, "page_num": int, "image": Image, ...}
        """
        super().__init__(parent)
        
        self.title("🔍 Inspector - 詳細比較")
        self.geometry("1800x1000")
        
        self.web_page = web_page
        self.pdf_page = pdf_page
        
        # 同期スクロール有効フラグ
        self.sync_enabled = True
        
        self._setup_ui()
        self._load_images()
    
    def _setup_ui(self):
        """UI構築"""
        # ヘッダー
        self._build_header()
        
        # ツールバー
        self._build_toolbar()
        
        # メインエリア（左右分割 + 同期スクロール）
        self._build_main_area()
        
        # ステータスバー
        self._build_status_bar()
    
    def _build_header(self):
        """ヘッダー構築"""
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color="#1A1A1A")
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        # タイトル
        ctk.CTkLabel(
            header,
            text="🔍 Inspector - 詳細比較",
            font=("Meiryo", 18, "bold"),
            text_color="#FF6F00"
        ).pack(side="left", padx=20, pady=15)
        
        # 説明
        ctk.CTkLabel(
            header,
            text="💡 左右のスクロールは自動同期されます | マウスホイール・スクロールバーで操作可能",
            font=("Meiryo", 10),
            text_color="gray"
        ).pack(side="left", padx=20, pady=15)
    
    def _build_toolbar(self):
        """ツールバー構築"""
        toolbar = ctk.CTkFrame(self, height=60, corner_radius=0)
        toolbar.pack(side="top", fill="x")
        toolbar.pack_propagate(False)
        
        # 同期制御
        sync_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        sync_frame.pack(side="left", padx=10, pady=10)
        
        self.sync_checkbox = ctk.CTkCheckBox(
            sync_frame,
            text="同期スクロール",
            command=self._toggle_sync,
            font=("Meiryo", 11)
        )
        self.sync_checkbox.select()  # デフォルトでON
        self.sync_checkbox.pack(side="left", padx=5)
        
        # 表示制御
        view_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        view_frame.pack(side="left", padx=20, pady=10)
        
        ctk.CTkButton(
            view_frame,
            text="🔄 オニオンスキン",
            command=self._toggle_onion_skin,
            width=140
        ).pack(side="left", padx=5)
        
        # エクスポート
        export_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        export_frame.pack(side="right", padx=10, pady=10)
        
        ctk.CTkButton(
            export_frame,
            text="📤 エクスポート",
            command=self._export_comparison,
            width=120,
            fg_color="#4CAF50",
            hover_color="#45A049"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            export_frame,
            text="← 戻る",
            command=self.destroy,
            width=100
        ).pack(side="left", padx=5)
    
    def _build_main_area(self):
        """メインエリア構築"""
        # PanedWindowで左右分割
        self.main_paned = tk.PanedWindow(
            self,
            orient="horizontal",
            bg="#2B2B2B",
            sashwidth=6,
            sashrelief="raised"
        )
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左側: Web Canvas
        self.web_canvas = SyncScrollCanvas(
            self.main_paned,
            width=880,
            height=800,
            title=f"🌐 Web: {self.web_page.get('url', '')[:60]}..."
        )
        self.main_paned.add(self.web_canvas, width=900)
        
        # 右側: PDF Canvas
        pdf_filename = Path(self.pdf_page.get('filename', '')).name
        pdf_page_num = self.pdf_page.get('page_num', 1)
        self.pdf_canvas = SyncScrollCanvas(
            self.main_paned,
            width=880,
            height=800,
            title=f"📁 PDF: {pdf_filename} (ページ {pdf_page_num})"
        )
        self.main_paned.add(self.pdf_canvas, width=900)
        
        # 同期スクロール設定
        self.web_canvas.bind_partner(self.pdf_canvas)
        self.pdf_canvas.bind_partner(self.web_canvas)
    
    def _build_status_bar(self):
        """ステータスバー構築"""
        status_bar = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color="#1A1A1A")
        status_bar.pack(side="bottom", fill="x")
        status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_bar,
            text="準備完了",
            font=("Meiryo", 9),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=20, pady=8)
    
    def _load_images(self):
        """画像を読み込む"""
        # Web画像
        web_image = self.web_page.get('image')
        if web_image and isinstance(web_image, Image.Image):
            self.web_canvas.load_image(
                web_image,
                title=f"🌐 Web: {self.web_page.get('title', '')}"
            )
            self.status_label.configure(text="Web画像読み込み完了")
        
        # PDF画像
        pdf_image = self.pdf_page.get('image')
        if pdf_image and isinstance(pdf_image, Image.Image):
            pdf_filename = Path(self.pdf_page.get('filename', '')).name
            pdf_page_num = self.pdf_page.get('page_num', 1)
            self.pdf_canvas.load_image(
                pdf_image,
                title=f"📁 PDF: {pdf_filename} (ページ {pdf_page_num})"
            )
            self.status_label.configure(text="すべての画像読み込み完了")
    
    def _toggle_sync(self):
        """同期スクロールのON/OFF切り替え"""
        if self.sync_checkbox.get():
            self.web_canvas.enable_sync()
            self.pdf_canvas.enable_sync()
            self.status_label.configure(text="同期スクロール: ON")
        else:
            self.web_canvas.disable_sync()
            self.pdf_canvas.disable_sync()
            self.status_label.configure(text="同期スクロール: OFF")
    
    def _toggle_onion_skin(self):
        """オニオンスキンモード切り替え（TODO: 実装）"""
        messagebox.showinfo("TODO", "オニオンスキン機能は実装中です")
    
    def _export_comparison(self):
        """比較結果をエクスポート（TODO: 実装）"""
        messagebox.showinfo("TODO", "エクスポート機能は実装中です")

