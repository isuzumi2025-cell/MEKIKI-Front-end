"""
Micro View Module
詳細比較ビュー - Visual/Textモード切替、同期スクロール
"""
import customtkinter as ctk
import tkinter as tk
from typing import Dict, Optional, Tuple
from PIL import Image, ImageTk
import difflib


class MicroView(ctk.CTkToplevel):
    """
    詳細比較ビュー（Micro View）
    Visualモード（画像比較）とTextモード（テキスト差分）
    """
    
    def __init__(
        self,
        master,
        matched_pair,
        analyzer=None,
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            matched_pair: MatchedPairオブジェクト
            analyzer: ContentAnalyzer（オプション）
        """
        super().__init__(master, **kwargs)
        
        self.matched_pair = matched_pair
        self.analyzer = analyzer
        self.current_mode = "visual"  # "visual" or "text"
        
        # 同期スクロール制御
        self.sync_scroll_enabled = True
        self._scrolling = False
        
        # オニオンスキン用
        self.onion_alpha = 0.5
        self.onion_mode = False
        
        self.title("🔍 詳細比較")
        self.geometry("1600x900")
        
        self._build_ui()
        self._load_data()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, height=90, corner_radius=0, fg_color="#1A1A1A")
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        # タイトル
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=10)
        
        ctk.CTkLabel(
            title_frame,
            text="🔍 詳細比較",
            font=("Meiryo", 18, "bold"),
            text_color="#FF6F00"
        ).pack(anchor="w")
        
        score_text = f"類似度: {self.matched_pair.similarity_score:.1%}"
        score_color = self._get_score_color(self.matched_pair.similarity_score)
        ctk.CTkLabel(
            title_frame,
            text=score_text,
            font=("Meiryo", 12),
            text_color=score_color
        ).pack(anchor="w")
        
        # モード切替タブ
        tab_frame = ctk.CTkFrame(header, fg_color="transparent")
        tab_frame.pack(side="right", padx=20, pady=10)
        
        self.visual_tab = ctk.CTkButton(
            tab_frame,
            text="🖼️ Visual",
            command=lambda: self._switch_mode("visual"),
            width=120,
            height=40,
            fg_color="#FF6F00"
        )
        self.visual_tab.pack(side="left", padx=5)
        
        self.text_tab = ctk.CTkButton(
            tab_frame,
            text="📝 Text",
            command=lambda: self._switch_mode("text"),
            width=120,
            height=40,
            fg_color="gray"
        )
        self.text_tab.pack(side="left", padx=5)
        
        # ツールバー
        toolbar = ctk.CTkFrame(self, height=60, corner_radius=0)
        toolbar.pack(side="top", fill="x")
        toolbar.pack_propagate(False)
        
        # 同期スクロール切り替え
        self.sync_checkbox = ctk.CTkCheckBox(
            toolbar,
            text="同期スクロール",
            font=("Meiryo", 11),
            command=self._toggle_sync_scroll
        )
        self.sync_checkbox.select()
        self.sync_checkbox.pack(side="left", padx=20, pady=10)
        
        # オニオンスキンモード
        self.onion_button = ctk.CTkButton(
            toolbar,
            text="🧅 オニオンスキン",
            command=self._toggle_onion_mode,
            width=140,
            height=30,
            fg_color="#9C27B0"
        )
        self.onion_button.pack(side="left", padx=10, pady=10)
        
        # 閉じるボタン
        ctk.CTkButton(
            toolbar,
            text="← 戻る",
            command=self.destroy,
            width=100,
            height=30
        ).pack(side="right", padx=20, pady=10)
        
        # メインコンテンツエリア（スタック形式）
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Visualモード用コンテンツ
        self.visual_content = self._build_visual_mode()
        self.visual_content.pack(fill="both", expand=True)
        
        # Textモード用コンテンツ
        self.text_content = self._build_text_mode()
        # 初期状態では非表示
    
    def _build_visual_mode(self) -> ctk.CTkFrame:
        """Visualモード（画像比較）を構築"""
        frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        # PanedWindowで左右分割
        self.paned = tk.PanedWindow(
            frame,
            orient="horizontal",
            bg="#2B2B2B",
            sashwidth=6
        )
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左: Web
        self.web_canvas_frame = self._build_canvas_panel(
            self.paned,
            "🌐 Web",
            self.matched_pair.web_area.source_id
        )
        self.paned.add(self.web_canvas_frame, width=780)
        
        # 右: PDF
        self.pdf_canvas_frame = self._build_canvas_panel(
            self.paned,
            "📁 PDF",
            f"{self.matched_pair.pdf_area.source_id} (p.{self.matched_pair.pdf_area.page_num})"
        )
        self.paned.add(self.pdf_canvas_frame, width=780)
        
        # オニオンスキンスライダー（初期は非表示）
        self.onion_slider_frame = ctk.CTkFrame(frame, height=60)
        
        ctk.CTkLabel(
            self.onion_slider_frame,
            text="透過度:",
            font=("Meiryo", 11)
        ).pack(side="left", padx=10)
        
        self.alpha_slider = ctk.CTkSlider(
            self.onion_slider_frame,
            from_=0,
            to=1,
            number_of_steps=100,
            command=self._on_alpha_change
        )
        self.alpha_slider.set(0.5)
        self.alpha_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        self.alpha_label = ctk.CTkLabel(
            self.onion_slider_frame,
            text="50%",
            font=("Meiryo", 11),
            width=50
        )
        self.alpha_label.pack(side="left", padx=10)
        
        return frame
    
    def _build_canvas_panel(self, parent, title: str, subtitle: str) -> ctk.CTkFrame:
        """Canvasパネルを構築"""
        frame = ctk.CTkFrame(parent, corner_radius=0)
        
        # ヘッダー
        header = ctk.CTkFrame(frame, height=50)
        header.pack(fill="x", padx=5, pady=5)
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text=title,
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ).pack(side="left", padx=10)
        
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=("Meiryo", 9),
            text_color="gray",
            anchor="w"
        ).pack(side="left", padx=10)
        
        # スクロール可能なCanvas
        canvas_container = ctk.CTkFrame(frame)
        canvas_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        v_scrollbar = ctk.CTkScrollbar(canvas_container, orientation="vertical")
        v_scrollbar.pack(side="right", fill="y")
        
        h_scrollbar = ctk.CTkScrollbar(canvas_container, orientation="horizontal")
        h_scrollbar.pack(side="bottom", fill="x")
        
        canvas = tk.Canvas(
            canvas_container,
            bg="#2B2B2B",
            highlightthickness=0,
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        canvas.pack(side="left", fill="both", expand=True)
        
        v_scrollbar.configure(command=canvas.yview)
        h_scrollbar.configure(command=canvas.xview)
        
        # Canvasを保存
        if title.startswith("🌐"):
            self.web_canvas = canvas
            self.web_v_scroll = v_scrollbar
            self.web_h_scroll = h_scrollbar
        else:
            self.pdf_canvas = canvas
            self.pdf_v_scroll = v_scrollbar
            self.pdf_h_scroll = h_scrollbar
        
        return frame
    
    def _build_text_mode(self) -> ctk.CTkFrame:
        """Textモード（テキスト差分）を構築"""
        frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        # PanedWindowで左右分割
        paned = tk.PanedWindow(
            frame,
            orient="horizontal",
            bg="#2B2B2B",
            sashwidth=6
        )
        paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左: Webテキスト
        self.web_text_frame = self._build_text_panel(
            paned,
            "🌐 Web Text",
            self.matched_pair.web_area.source_id
        )
        paned.add(self.web_text_frame, width=780)
        
        # 右: PDFテキスト
        self.pdf_text_frame = self._build_text_panel(
            paned,
            "📁 PDF Text",
            f"{self.matched_pair.pdf_area.source_id} (p.{self.matched_pair.pdf_area.page_num})"
        )
        paned.add(self.pdf_text_frame, width=780)
        
        return frame
    
    def _build_text_panel(self, parent, title: str, subtitle: str) -> ctk.CTkFrame:
        """テキストパネルを構築"""
        frame = ctk.CTkFrame(parent, corner_radius=0)
        
        # ヘッダー
        header = ctk.CTkFrame(frame, height=50)
        header.pack(fill="x", padx=5, pady=5)
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text=title,
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ).pack(side="left", padx=10)
        
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=("Meiryo", 9),
            text_color="gray",
            anchor="w"
        ).pack(side="left", padx=10)
        
        # テキストウィジェット
        text_widget = tk.Text(
            frame,
            bg="#1A1A1A",
            fg="white",
            font=("Consolas", 10),
            wrap="word",
            padx=10,
            pady=10
        )
        text_widget.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 色のタグを定義
        text_widget.tag_configure("match", background="#1A1A1A", foreground="white")
        text_widget.tag_configure("add", background="#1B5E20", foreground="white")
        text_widget.tag_configure("delete", background="#B71C1C", foreground="white")
        text_widget.tag_configure("change", background="#F57F17", foreground="white")
        
        # テキストウィジェットを保存
        if title.startswith("🌐"):
            self.web_text_widget = text_widget
        else:
            self.pdf_text_widget = text_widget
        
        return frame
    
    def _load_data(self):
        """データを読み込んで表示"""
        # Visualモード: プレースホルダー画像を表示
        self._load_visual_data()
        
        # Textモード: テキストを表示
        self._load_text_data()
    
    def _load_visual_data(self):
        """Visualモードのデータ読み込み"""
        # TODO: 実際の画像データを読み込む
        # 今はプレースホルダーテキストを表示
        web_text = f"Web画像\n\n{self.matched_pair.web_area.text}"
        pdf_text = f"PDF画像\n\n{self.matched_pair.pdf_area.text}"
        
        self.web_canvas.create_text(
            200, 200,
            text=web_text,
            font=("Meiryo", 11),
            fill="white",
            width=300,
            justify="center"
        )
        
        self.pdf_canvas.create_text(
            200, 200,
            text=pdf_text,
            font=("Meiryo", 11),
            fill="white",
            width=300,
            justify="center"
        )
    
    def _load_text_data(self):
        """Textモードのデータ読み込み"""
        web_text = self.matched_pair.web_area.text
        pdf_text = self.matched_pair.pdf_area.text
        
        # 差分を計算
        if self.analyzer:
            differences = self.analyzer.find_differences(web_text, pdf_text)
        else:
            differences = []
        
        # Webテキストを表示
        self.web_text_widget.delete("1.0", "end")
        self._display_diff_text(
            self.web_text_widget,
            web_text,
            pdf_text,
            is_left=True
        )
        
        # PDFテキストを表示
        self.pdf_text_widget.delete("1.0", "end")
        self._display_diff_text(
            self.pdf_text_widget,
            web_text,
            pdf_text,
            is_left=False
        )
    
    def _display_diff_text(
        self,
        text_widget: tk.Text,
        text1: str,
        text2: str,
        is_left: bool
    ):
        """差分をハイライト表示"""
        # difflibで差分を計算
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        diff = list(difflib.ndiff(lines1, lines2))
        
        for line in diff:
            if line.startswith('  '):  # 一致
                text_widget.insert("end", line[2:] + "\n", "match")
            elif line.startswith('+ '):  # 追加
                if not is_left:
                    text_widget.insert("end", line[2:] + "\n", "add")
            elif line.startswith('- '):  # 削除
                if is_left:
                    text_widget.insert("end", line[2:] + "\n", "delete")
            elif line.startswith('? '):  # 変更インジケータ
                pass
    
    def _switch_mode(self, mode: str):
        """モードを切り替え"""
        self.current_mode = mode
        
        if mode == "visual":
            # Visualモードを表示
            self.visual_content.pack(fill="both", expand=True)
            self.text_content.pack_forget()
            
            # タブの色を更新
            self.visual_tab.configure(fg_color="#FF6F00")
            self.text_tab.configure(fg_color="gray")
            
        else:  # text
            # Textモードを表示
            self.text_content.pack(fill="both", expand=True)
            self.visual_content.pack_forget()
            
            # タブの色を更新
            self.text_tab.configure(fg_color="#FF6F00")
            self.visual_tab.configure(fg_color="gray")
    
    def _toggle_sync_scroll(self):
        """同期スクロールの切り替え"""
        self.sync_scroll_enabled = self.sync_checkbox.get()
        print(f"同期スクロール: {'有効' if self.sync_scroll_enabled else '無効'}")
    
    def _toggle_onion_mode(self):
        """オニオンスキンモードの切り替え"""
        self.onion_mode = not self.onion_mode
        
        if self.onion_mode:
            self.onion_slider_frame.pack(side="bottom", fill="x", pady=10)
            self.onion_button.configure(fg_color="#7B1FA2")
            print("🧅 オニオンスキンモード: ON")
        else:
            self.onion_slider_frame.pack_forget()
            self.onion_button.configure(fg_color="#9C27B0")
            print("🧅 オニオンスキンモード: OFF")
    
    def _on_alpha_change(self, value):
        """透過度スライダーの変更"""
        self.onion_alpha = value
        self.alpha_label.configure(text=f"{int(value * 100)}%")
        # TODO: オニオンスキン画像を更新
    
    def _get_score_color(self, score: float) -> str:
        """スコアに応じた色を返す"""
        if score >= 0.7:
            return "#4CAF50"  # 緑
        elif score >= 0.4:
            return "#FFC107"  # 黄
        else:
            return "#FF5722"  # 赤
