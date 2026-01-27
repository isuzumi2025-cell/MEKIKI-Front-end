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

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    print("⚠️ CustomTkinter not available")

from PIL import Image, ImageTk


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
        
        # UI構築
        self._build_ui()
        
        # キーバインド
        self.bind("<Escape>", lambda e: self.destroy())
        
        # フォーカス
        self.focus_force()
        self.lift()
    
    def _build_ui(self):
        """UIを構築"""
        # メインコンテナ
        self.grid_columnconfigure(0, weight=0)  # サイドバー
        self.grid_columnconfigure(1, weight=1)  # コンテンツ
        self.grid_rowconfigure(0, weight=1)
        
        # ===== サイドバー =====
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0) if CTK_AVAILABLE else tk.Frame(self, width=250)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        
        self._build_sidebar()
        
        # ===== メインコンテンツ =====
        self.content = ctk.CTkFrame(self) if CTK_AVAILABLE else tk.Frame(self)
        self.content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)
        
        self._build_content()
    
    def _build_sidebar(self):
        """サイドバーを構築"""
        # ロゴ/タイトル
        title_label = ctk.CTkLabel(
            self.sidebar,
            text="📎 コンテ素材抽出",
            font=("Meiryo", 18, "bold")
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="📎 コンテ素材抽出", font=("Meiryo", 18, "bold"))
        title_label.pack(pady=(20, 5))
        
        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Storyboard Asset Extractor",
            font=("Meiryo", 10),
            text_color="gray"
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="Storyboard Asset Extractor", font=("Meiryo", 10), fg="gray")
        subtitle.pack(pady=(0, 20))
        
        # セパレーター
        if CTK_AVAILABLE:
            sep1 = ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30")
            sep1.pack(fill="x", padx=20, pady=10)
        
        # === インポートセクション ===
        section_import = ctk.CTkLabel(
            self.sidebar,
            text="📥 インポート",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="📥 インポート", font=("Meiryo", 12, "bold"), anchor="w")
        section_import.pack(fill="x", padx=20, pady=(10, 5))
        
        # PDFインポートボタン
        self.import_btn = ctk.CTkButton(
            self.sidebar,
            text="📄 PDFを開く",
            command=self._import_pdf,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=("Meiryo", 14)
        ) if CTK_AVAILABLE else tk.Button(self.sidebar, text="📄 PDFを開く", command=self._import_pdf)
        self.import_btn.pack(fill="x", padx=20, pady=5)
        
        # ファイル情報ラベル
        self.file_label = ctk.CTkLabel(
            self.sidebar,
            text="ファイル未選択",
            font=("Meiryo", 10),
            text_color="gray",
            wraplength=200
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="ファイル未選択", font=("Meiryo", 10), fg="gray", wraplength=200)
        self.file_label.pack(fill="x", padx=20, pady=(0, 10))
        
        # セパレーター
        if CTK_AVAILABLE:
            sep2 = ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30")
            sep2.pack(fill="x", padx=20, pady=10)
        
        # === 抽出セクション ===
        section_extract = ctk.CTkLabel(
            self.sidebar,
            text="🔍 レイヤー抽出",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="🔍 レイヤー抽出", font=("Meiryo", 12, "bold"), anchor="w")
        section_extract.pack(fill="x", padx=20, pady=(10, 5))
        
        # テキスト抽出
        self.extract_text_btn = ctk.CTkButton(
            self.sidebar,
            text="📝 テキスト抽出",
            command=self._extract_text_layer,
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.sidebar, text="📝 テキスト抽出", command=self._extract_text_layer, state="disabled")
        self.extract_text_btn.pack(fill="x", padx=20, pady=3)
        
        # 画像抽出
        self.extract_image_btn = ctk.CTkButton(
            self.sidebar,
            text="🖼️ 画像抽出",
            command=self._extract_image_layer,
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.sidebar, text="🖼️ 画像抽出", command=self._extract_image_layer, state="disabled")
        self.extract_image_btn.pack(fill="x", padx=20, pady=3)
        
        # 画像パーツ分割
        self.slice_btn = ctk.CTkButton(
            self.sidebar,
            text="✂️ パーツ分割",
            command=self._slice_images,
            fg_color="#F59E0B",
            hover_color="#D97706",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.sidebar, text="✂️ パーツ分割", command=self._slice_images, state="disabled")
        self.slice_btn.pack(fill="x", padx=20, pady=3)
        
        # セパレーター
        if CTK_AVAILABLE:
            sep3 = ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30")
            sep3.pack(fill="x", padx=20, pady=10)
        
        # === エクスポートセクション ===
        section_export = ctk.CTkLabel(
            self.sidebar,
            text="📤 エクスポート",
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="📤 エクスポート", font=("Meiryo", 12, "bold"), anchor="w")
        section_export.pack(fill="x", padx=20, pady=(10, 5))
        
        # Excelエクスポート
        self.export_excel_btn = ctk.CTkButton(
            self.sidebar,
            text="📊 Excelに出力",
            command=self._export_excel,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.sidebar, text="📊 Excelに出力", command=self._export_excel, state="disabled")
        self.export_excel_btn.pack(fill="x", padx=20, pady=3)
        
        # PowerPointエクスポート
        self.export_pptx_btn = ctk.CTkButton(
            self.sidebar,
            text="📑 PowerPointに出力",
            command=self._export_pptx,
            fg_color="#10B981",
            hover_color="#059669",
            font=("Meiryo", 12),
            state="disabled"
        ) if CTK_AVAILABLE else tk.Button(self.sidebar, text="📑 PowerPointに出力", command=self._export_pptx, state="disabled")
        self.export_pptx_btn.pack(fill="x", padx=20, pady=3)
        
        # ステータス表示（下部）
        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="Ready",
            font=("Meiryo", 10),
            text_color="gray"
        ) if CTK_AVAILABLE else tk.Label(self.sidebar, text="Ready", font=("Meiryo", 10), fg="gray")
        self.status_label.pack(side="bottom", pady=20)
    
    def _build_content(self):
        """メインコンテンツを構築"""
        # タブビュー
        if CTK_AVAILABLE:
            self.tabview = ctk.CTkTabview(self.content)
            self.tabview.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
            
            # タブ追加
            self.tab_preview = self.tabview.add("📄 プレビュー")
            self.tab_text = self.tabview.add("📝 テキスト")
            self.tab_images = self.tabview.add("🖼️ 画像")
            self.tab_parts = self.tabview.add("✂️ パーツ")
        else:
            # tkinterの場合はNotebookを使用
            import tkinter.ttk as ttk
            self.tabview = ttk.Notebook(self.content)
            self.tabview.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
            
            self.tab_preview = tk.Frame(self.tabview)
            self.tab_text = tk.Frame(self.tabview)
            self.tab_images = tk.Frame(self.tabview)
            self.tab_parts = tk.Frame(self.tabview)
            
            self.tabview.add(self.tab_preview, text="📄 プレビュー")
            self.tabview.add(self.tab_text, text="📝 テキスト")
            self.tabview.add(self.tab_images, text="🖼️ 画像")
            self.tabview.add(self.tab_parts, text="✂️ パーツ")
        
        # 各タブの内容を構築
        self._build_preview_tab()
        self._build_text_tab()
        self._build_images_tab()
        self._build_parts_tab()
    
    def _build_preview_tab(self):
        """プレビュータブを構築"""
        # キャンバス（PDFページ表示用）
        canvas_frame = ctk.CTkFrame(self.tab_preview) if CTK_AVAILABLE else tk.Frame(self.tab_preview)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.preview_canvas = tk.Canvas(canvas_frame, bg="gray20", highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True)
        
        # ウェルカムメッセージ
        self.preview_canvas.create_text(
            400, 300,
            text="PDFファイルをインポートしてください",
            fill="gray60",
            font=("Meiryo", 16)
        )
    
    def _build_text_tab(self):
        """テキストタブを構築"""
        # テキストエリア
        self.text_display = ctk.CTkTextbox(
            self.tab_text,
            font=("Consolas", 12),
            wrap="word"
        ) if CTK_AVAILABLE else tk.Text(self.tab_text, font=("Consolas", 12), wrap="word")
        self.text_display.pack(fill="both", expand=True, padx=10, pady=10)
        
        if CTK_AVAILABLE:
            self.text_display.insert("1.0", "テキストレイヤーを抽出すると、ここに表示されます。")
    
    def _build_images_tab(self):
        """画像タブを構築"""
        # スクロール可能なフレーム
        self.images_scroll = ctk.CTkScrollableFrame(self.tab_images) if CTK_AVAILABLE else tk.Frame(self.tab_images)
        self.images_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        info_label = ctk.CTkLabel(
            self.images_scroll,
            text="画像レイヤーを抽出すると、ここにサムネイルが表示されます。",
            text_color="gray"
        ) if CTK_AVAILABLE else tk.Label(self.images_scroll, text="画像レイヤーを抽出すると、ここにサムネイルが表示されます。", fg="gray")
        info_label.pack(pady=20)
    
    def _build_parts_tab(self):
        """パーツタブを構築"""
        self.parts_scroll = ctk.CTkScrollableFrame(self.tab_parts) if CTK_AVAILABLE else tk.Frame(self.tab_parts)
        self.parts_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        info_label = ctk.CTkLabel(
            self.parts_scroll,
            text="画像をパーツ分割すると、ここに個別パーツが表示されます。",
            text_color="gray"
        ) if CTK_AVAILABLE else tk.Label(self.parts_scroll, text="画像をパーツ分割すると、ここに個別パーツが表示されます。", fg="gray")
        info_label.pack(pady=20)
    
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
        
        # プレビュー表示
        self._show_pdf_preview()
        
        self._set_status(f"読み込み完了: {Path(file_path).name}")
    
    def _show_pdf_preview(self):
        """PDFのプレビューを表示"""
        if not self.current_pdf_path:
            return
        
        try:
            from app.pipeline.storyboard.layer_separator import LayerSeparator
            
            if self._layer_separator is None:
                self._layer_separator = LayerSeparator(force_ocr=False)  # 埋め込みテキスト優先、なければOCR
            
            # 最初のページを画像としてレンダリング
            preview_img = self._layer_separator.render_page_as_image(
                self.current_pdf_path, 
                page_num=0, 
                scale=1.5
            )
            
            if preview_img:
                # キャンバスサイズに合わせてリサイズ
                canvas_w = self.preview_canvas.winfo_width() or 800
                canvas_h = self.preview_canvas.winfo_height() or 600
                
                ratio = min(canvas_w / preview_img.width, canvas_h / preview_img.height)
                new_w = int(preview_img.width * ratio * 0.9)
                new_h = int(preview_img.height * ratio * 0.9)
                
                resized = preview_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Tkinter用に変換
                self._preview_photo = ImageTk.PhotoImage(resized)
                
                # キャンバスに表示
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(
                    canvas_w // 2, canvas_h // 2,
                    image=self._preview_photo,
                    anchor="center"
                )
                
        except Exception as e:
            print(f"⚠️ Preview failed: {e}")
    
    def _extract_text_layer(self):
        """テキストレイヤーを抽出（バックグラウンドスレッドで実行）"""
        if not self.current_pdf_path:
            return
        
        self._set_status("テキスト抽出中... (処理には時間がかかります)")
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
        
        # エクスポートボタン有効化
        self.export_excel_btn.configure(state="normal")
        self.export_pptx_btn.configure(state="normal")
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
        """テキスト表示を更新"""
        if CTK_AVAILABLE:
            self.text_display.delete("1.0", "end")
        else:
            self.text_display.delete("1.0", tk.END)
        
        for para in self.paragraphs:
            para_id = getattr(para, 'id', 'P-???')
            para_type = getattr(para, 'paragraph_type', 'body')
            text = getattr(para, 'text', str(para))
            
            display_text = f"[{para_id}] ({para_type})\n{text}\n\n"
            
            if CTK_AVAILABLE:
                self.text_display.insert("end", display_text)
            else:
                self.text_display.insert(tk.END, display_text)
    
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
            
            # パーツ分割ボタン有効化
            if self.layer_result.image_layer.blocks:
                self.slice_btn.configure(state="normal")
            
            self._set_status(f"画像抽出完了: {len(self.layer_result.image_layer.blocks)}枚")
            
            # 画像タブに切り替え
            if CTK_AVAILABLE:
                self.tabview.set("🖼️ 画像")
            
        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"画像抽出に失敗しました:\n{e}")
    
    def _update_images_display(self):
        """画像表示を更新"""
        # 既存のウィジェットをクリア
        for widget in self.images_scroll.winfo_children():
            widget.destroy()
        
        self._image_refs = []
        
        if not self.layer_result or not self.layer_result.image_layer.blocks:
            info_label = ctk.CTkLabel(
                self.images_scroll,
                text="画像が見つかりませんでした。",
                text_color="gray"
            ) if CTK_AVAILABLE else tk.Label(self.images_scroll, text="画像が見つかりませんでした。", fg="gray")
            info_label.pack(pady=20)
            return
        
        for i, img_block in enumerate(self.layer_result.image_layer.blocks):
            frame = ctk.CTkFrame(self.images_scroll) if CTK_AVAILABLE else tk.Frame(self.images_scroll)
            frame.pack(fill="x", padx=5, pady=5)
            
            # サムネイル
            img = img_block.image
            if isinstance(img, Image.Image):
                thumb = img.copy()
                thumb.thumbnail((150, 150))
                photo = ImageTk.PhotoImage(thumb)
                self._image_refs.append(photo)
                
                img_label = tk.Label(frame, image=photo)
                img_label.pack(side="left", padx=10, pady=10)
            
            # 情報
            info_text = f"画像 {i+1}\nサイズ: {img_block.original_width}x{img_block.original_height}\nページ: {img_block.page_num + 1}"
            info_label = ctk.CTkLabel(
                frame,
                text=info_text,
                font=("Meiryo", 11),
                justify="left"
            ) if CTK_AVAILABLE else tk.Label(frame, text=info_text, font=("Meiryo", 11), justify="left")
            info_label.pack(side="left", padx=10)
    
    def _slice_images(self):
        """画像をパーツに分割"""
        if not self.layer_result or not self.layer_result.image_layer.blocks:
            return
        
        self._set_status("パーツ分割中... (Gemini Vision使用)")
        
        try:
            from app.pipeline.storyboard.image_slicer import ImageSlicer
            
            if self._image_slicer is None:
                self._image_slicer = ImageSlicer()
            
            self.image_parts = []
            
            for img_block in self.layer_result.image_layer.blocks:
                parts = self._image_slicer.slice_image(img_block.image, mode="auto")
                self.image_parts.extend(parts)
            
            # パーツ表示を更新
            self._update_parts_display()
            
            self._set_status(f"パーツ分割完了: {len(self.image_parts)}パーツ")
            
            # パーツタブに切り替え
            if CTK_AVAILABLE:
                self.tabview.set("✂️ パーツ")
            
        except Exception as e:
            self._set_status(f"エラー: {e}")
            messagebox.showerror("エラー", f"パーツ分割に失敗しました:\n{e}")
    
    def _update_parts_display(self):
        """パーツ表示を更新"""
        for widget in self.parts_scroll.winfo_children():
            widget.destroy()
        
        if not self.image_parts:
            info_label = ctk.CTkLabel(
                self.parts_scroll,
                text="パーツが見つかりませんでした。",
                text_color="gray"
            ) if CTK_AVAILABLE else tk.Label(self.parts_scroll, text="パーツが見つかりませんでした。", fg="gray")
            info_label.pack(pady=20)
            return
        
        for part in self.image_parts:
            frame = ctk.CTkFrame(self.parts_scroll) if CTK_AVAILABLE else tk.Frame(self.parts_scroll)
            frame.pack(fill="x", padx=5, pady=5)
            
            # サムネイル
            if isinstance(part.image, Image.Image):
                thumb = part.image.copy()
                thumb.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(thumb)
                self._image_refs.append(photo)
                
                img_label = tk.Label(frame, image=photo)
                img_label.pack(side="left", padx=10, pady=10)
            
            # 情報
            info_text = f"ID: {part.id}\nラベル: {part.label}\nレイヤー: {part.layer_order}"
            info_label = ctk.CTkLabel(
                frame,
                text=info_text,
                font=("Meiryo", 10),
                justify="left"
            ) if CTK_AVAILABLE else tk.Label(frame, text=info_text, font=("Meiryo", 10), justify="left")
            info_label.pack(side="left", padx=10)
    
    def _export_excel(self):
        """Excelにエクスポート"""
        if not self.paragraphs and not self.image_parts:
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
            
            images = self.image_parts if self.image_parts else (
                self.layer_result.image_layer.blocks if self.layer_result else []
            )
            
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
        if not self.paragraphs and not self.image_parts:
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
            
            images = self.image_parts if self.image_parts else (
                self.layer_result.image_layer.blocks if self.layer_result else []
            )
            
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
    
    # ===== ユーティリティ =====
    
    def _enable_buttons(self):
        """ボタンを有効化"""
        self.extract_text_btn.configure(state="normal")
        self.extract_image_btn.configure(state="normal")
    
    def _set_status(self, message: str):
        """ステータスを設定"""
        self.status_label.configure(text=message)
        self.update_idletasks()
        print(f"[StoryboardExtractor] {message}")


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
