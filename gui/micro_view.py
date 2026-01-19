"""
Micro View Module
詳細比較画面 - WebとPDFの精密な比較（画像・テキスト）
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
from PIL import Image, ImageTk, ImageDraw
import difflib
import threading


class MicroView(ctk.CTkFrame):
    """
    詳細比較ビュー
    - 画像比較タブ（左右分割、同期スクロール、オニオンスキン）
    - テキスト比較タブ（差分ハイライト）
    """
    
    def __init__(
        self, 
        master, 
        on_back: Optional[callable] = None,
        matched_pair=None,
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            on_back: 戻るボタンのコールバック
            matched_pair: 初期表示するペア（オプション）
        """
        # 独自引数をkwargsから除外して親クラスに渡す
        # (念のため、明示的に除外)
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ['on_back', 'matched_pair']}
        super().__init__(master, **clean_kwargs)
        
        self.on_back = on_back
        self.matched_pair = matched_pair
        
        # 画像キャッシュ（GC対策）
        self.image_cache = {}
        
        # オニオンスキン用
        self.onion_alpha = 0.5
        self.composite_image = None
        
        # プレースホルダー
        self.placeholder_widget = None

        # LLM分析結果用
        self.llm_analysis_text = None
        self.llm_button = None
        
        self._build_ui()
        
        # 初期データがあれば表示、なければプレースホルダー
        if self.matched_pair:
            self.update_pair(self.matched_pair)
        else:
            self._show_placeholder()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # 戻るボタン
        ctk.CTkButton(
            header,
            text="⬅ 戻る",
            command=self._on_back_click,
            width=100,
            height=35,
            font=("Meiryo", 13, "bold"),
            fg_color="#FF6F00",
            hover_color="#E65100"
        ).pack(side="left", padx=20, pady=20)
        
        # タイトル
        self.title_label = ctk.CTkLabel(
            header,
            text="詳細比較",
            font=("Meiryo", 20, "bold"),
            text_color="#4CAF50"
        )
        self.title_label.pack(side="left", padx=10, pady=20)
        
        # タブビュー
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # タブ追加
        self.tabview.add("🖼️ 画像比較")
        self.tabview.add("📝 テキスト比較")
        
        # 各タブの内容を構築
        self._build_visual_tab()
        self._build_text_tab()
    
    def _build_visual_tab(self):
        """画像比較タブの構築"""
        tab = self.tabview.tab("🖼️ 画像比較")
        
        # ツールバー
        toolbar = ctk.CTkFrame(tab, fg_color="transparent", height=50)
        toolbar.pack(fill="x", padx=10, pady=5)
        toolbar.pack_propagate(False)
        
        # オニオンスキンモード切替
        self.onion_var = ctk.BooleanVar(value=False)
        self.onion_toggle = ctk.CTkSwitch(
            toolbar,
            text="🧅 オニオンスキン",
            variable=self.onion_var,
            command=self._toggle_onion_skin,
            font=("Meiryo", 12)
        )
        self.onion_toggle.pack(side="left", padx=10)
        
        # 透過度スライダー
        self.alpha_slider = ctk.CTkSlider(
            toolbar,
            from_=0,
            to=1,
            number_of_steps=100,
            command=self._on_alpha_change,
            width=200
        )
        self.alpha_slider.set(0.5)
        self.alpha_slider.pack(side="left", padx=10)
        
        self.alpha_label = ctk.CTkLabel(
            toolbar,
            text="透過度: 50%",
            font=("Meiryo", 11)
        )
        self.alpha_label.pack(side="left", padx=5)
        
        # 分割ビュー
        self.visual_paned = tk.PanedWindow(
            tab,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            bg="#2B2B2B",
            sashrelief=tk.RAISED
        )
        self.visual_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左側: Web画像
        self.web_canvas_frame = ctk.CTkFrame(self.visual_paned, width=600)
        self.visual_paned.add(self.web_canvas_frame, width=600)
        
        web_label = ctk.CTkLabel(
            self.web_canvas_frame,
            text="🌐 Web",
            font=("Meiryo", 14, "bold"),
            text_color="#E08E00"
        )
        web_label.pack(pady=10)
        
        self.web_canvas = self._create_canvas_with_scrollbars(self.web_canvas_frame)
        
        # 右側: PDF画像
        self.pdf_canvas_frame = ctk.CTkFrame(self.visual_paned, width=600)
        self.visual_paned.add(self.pdf_canvas_frame, width=600)
        
        pdf_label = ctk.CTkLabel(
            self.pdf_canvas_frame,
            text="📁 PDF",
            font=("Meiryo", 14, "bold"),
            text_color="#4CAF50"
        )
        pdf_label.pack(pady=10)
        
        self.pdf_canvas = self._create_canvas_with_scrollbars(self.pdf_canvas_frame)
        
        # スクロール同期
        self._bind_sync_scroll()
    
    def _build_text_tab(self):
        """テキスト比較タブの構築"""
        tab = self.tabview.tab("📝 テキスト比較")
        
        # 統計情報
        stats_frame = ctk.CTkFrame(tab, fg_color="transparent", height=50)
        stats_frame.pack(fill="x", padx=10, pady=5)
        stats_frame = ctk.CTkFrame(tab, fg_color="transparent", height=50)
        stats_frame.pack(fill="x", padx=10, pady=5)
        # stats_frame.pack_propagate(False) # 高さ固定を解除
        
        self.similarity_label = ctk.CTkLabel(
            stats_frame,
            text="類似度: ---%",
            font=("Meiryo", 14, "bold")
        )
        self.similarity_label.pack(side="left", padx=10)
        
        self.diff_stats_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=("Meiryo", 11)
        )
        self.diff_stats_label.pack(side="left", padx=10)

        # AI分析ボタン
        self.llm_button = ctk.CTkButton(
            stats_frame,
            text="✨ AI分析実行",
            command=self._run_llm_analysis,
            width=120,
            fg_color="#6A1B9A",
            hover_color="#4A148C"
        )
        self.llm_button.pack(side="right", padx=10)
        
        # 分割ビュー (比率を変更)
        self.text_paned = tk.PanedWindow(
            tab,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            bg="#2B2B2B",
            sashrelief=tk.RAISED
        )
        self.text_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左側: Webテキスト
        web_text_frame = ctk.CTkFrame(self.text_paned, width=600)
        self.text_paned.add(web_text_frame, width=600)
        
        ctk.CTkLabel(
            web_text_frame,
            text="🌐 Web テキスト",
            font=("Meiryo", 14, "bold"),
            text_color="#E08E00"
        ).pack(pady=10)
        
        self.web_text = tk.Text(
            web_text_frame,
            wrap=tk.WORD,
            bg="#2B2B2B",
            fg="white",
            font=("Meiryo", 11),
            padx=10,
            pady=10,
            insertbackground="white"
        )
        self.web_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 右側: PDFテキスト
        pdf_text_frame = ctk.CTkFrame(self.text_paned, width=600)
        self.text_paned.add(pdf_text_frame, width=600)
        
        ctk.CTkLabel(
            pdf_text_frame,
            text="📁 PDF テキスト",
            font=("Meiryo", 14, "bold"),
            text_color="#4CAF50"
        ).pack(pady=10)
        
        self.pdf_text = tk.Text(
            pdf_text_frame,
            wrap=tk.WORD,
            bg="#2B2B2B",
            fg="white",
            font=("Meiryo", 11),
            padx=10,
            pady=10,
            insertbackground="white"
        )
        self.pdf_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # タグ設定（ハイライト用）
        self._setup_text_tags()

        # --- AI Insights Panel ---
        self._build_llm_panel(tab)

    def _build_llm_panel(self, parent):
        """LLM分析結果表示パネル"""
        # 区切り線
        ctk.CTkFrame(parent, height=2, fg_color="#444444").pack(fill="x", padx=10, pady=5)

        llm_frame = ctk.CTkFrame(parent, fg_color="#232323", height=200)
        llm_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # ヘッダー
        header = ctk.CTkFrame(llm_frame, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            header, 
            text="🤖 AI Semantic Insights", 
            font=("Meiryo", 12, "bold"),
            text_color="#AB47BC"
        ).pack(side="left")
        
        self.llm_status = ctk.CTkLabel(header, text="", font=("Meiryo", 10), text_color="gray")
        self.llm_status.pack(side="right", padx=10)

        # 結果テキストエリア
        self.llm_analysis_text = ctk.CTkTextbox(
            llm_frame,
            font=("Meiryo", 11),
            fg_color="#1A1A1A",
            text_color="#E0E0E0",
            wrap="word",
            height=150
        )
        self.llm_analysis_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.llm_analysis_text.insert("1.0", "「AI分析実行」ボタンを押すと、単純な文字比較ではなく、意味のある違い（価格、日付、条件の変更など）をAIが解説します。")
        self.llm_analysis_text.configure(state="disabled")
    
    def _create_canvas_with_scrollbars(self, parent):
        """スクロールバー付きCanvasを作成"""
        # コンテナ
        container = ctk.CTkFrame(parent)
        container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # スクロールバー
        v_scroll = ctk.CTkScrollbar(container, orientation="vertical")
        v_scroll.pack(side="right", fill="y")
        
        h_scroll = ctk.CTkScrollbar(container, orientation="horizontal")
        h_scroll.pack(side="bottom", fill="x")
        
        # Canvas
        canvas = tk.Canvas(
            container,
            bg="#2B2B2B",
            highlightthickness=0,
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
            width=500,
            height=600
        )
        canvas.pack(side="left", fill="both", expand=True)
        
        v_scroll.configure(command=canvas.yview)
        h_scroll.configure(command=canvas.xview)
        
        return canvas
    
    def _bind_sync_scroll(self):
        """スクロール同期を設定"""
        def sync_y(*args):
            self.web_canvas.yview(*args)
            self.pdf_canvas.yview(*args)
        
        def sync_x(*args):
            self.web_canvas.xview(*args)
            self.pdf_canvas.xview(*args)
        
        # 両方のCanvasに同じスクロールコマンドを適用
        # ※実際は片方をマスターにして、もう片方を追従させる実装が必要
    
    def _setup_text_tags(self):
        """テキストハイライト用のタグを設定"""
        # 一致部分（変更なし）
        self.web_text.tag_config("equal", background="#2B2B2B")
        self.pdf_text.tag_config("equal", background="#2B2B2B")
        
        # 削除（Webにあり、PDFにない）
        self.web_text.tag_config("delete", background="#5D1F1F", foreground="#FF6B6B")
        
        # 追加（PDFにあり、Webにない）
        self.pdf_text.tag_config("insert", background="#1F5D2C", foreground="#6BFF6B")
        
        # 変更
        self.web_text.tag_config("replace", background="#5D4A1F", foreground="#FFD700")
        self.pdf_text.tag_config("replace", background="#5D4A1F", foreground="#FFD700")
    
    def _show_placeholder(self):
        """プレースホルダー表示"""
        self.placeholder_widget = ctk.CTkLabel(
            self.tabview.tab("🖼️ 画像比較"),
            text="全体マップからペアを選択してください",
            font=("Meiryo", 16),
            text_color="gray"
        )
        self.placeholder_widget.place(relx=0.5, rely=0.5, anchor="center")
    
    def update_pair(self, matched_pair):
        """
        ペアデータを更新して表示
        
        Args:
            matched_pair: MatchedPair オブジェクト
        """
        print(f"[MicroView] ペア更新: {matched_pair}")
        
        # プレースホルダーを削除
        if self.placeholder_widget:
            self.placeholder_widget.destroy()
            self.placeholder_widget = None
        
        self.matched_pair = matched_pair
        
        # タイトル更新
        web_title = matched_pair.web_page.title[:30] if hasattr(matched_pair, 'web_page') else "Web"
        pdf_title = f"PDF P{matched_pair.pdf_page.page_num}" if hasattr(matched_pair, 'pdf_page') else "PDF"
        similarity = matched_pair.similarity_score * 100
        
        self.title_label.configure(
            text=f"📊 {web_title} ⇔ {pdf_title} ({similarity:.1f}%)"
        )
        
        # 画像タブを更新
        self._update_visual_tab()
        
        # テキストタブを更新
        self._update_text_tab()
        
        # PanedWindowの分割位置を中央に設定（画像読み込み後）
        self.after(100, lambda: self.visual_paned.sash_place(0, 600, 0))
        self.after(100, lambda: self.text_paned.sash_place(0, 600, 0))
    
    def _update_visual_tab(self):
        """画像比較タブを更新"""
        if not self.matched_pair:
            print("[MicroView] ペアデータなし")
            return
        
        print(f"[MicroView] 画像タブ更新開始")
        
        # Web画像
        web_img = self.matched_pair.web_page.image if hasattr(self.matched_pair, 'web_page') else None
        print(f"[MicroView] Web画像: {web_img is not None} - {type(web_img) if web_img else 'None'}")
        if web_img:
            self._display_image(self.web_canvas, web_img, "web")
        else:
            print("⚠️ [MicroView] Web画像がありません")
        
        # PDF画像
        pdf_img = self.matched_pair.pdf_page.image if hasattr(self.matched_pair, 'pdf_page') else None
        print(f"[MicroView] PDF画像: {pdf_img is not None} - {type(pdf_img) if pdf_img else 'None'}")
        if pdf_img:
            self._display_image(self.pdf_canvas, pdf_img, "pdf")
        else:
            print("⚠️ [MicroView] PDF画像がありません")
    
    def _display_image(self, canvas, pil_image, key):
        """Canvas画像を表示"""
        try:
            print(f"[MicroView] 画像表示: {key} - サイズ {pil_image.size}")
            
            # PhotoImageに変換
            photo = ImageTk.PhotoImage(pil_image)
            self.image_cache[key] = photo  # GC対策
            
            # Canvasに描画
            canvas.delete("all")
            canvas.create_image(0, 0, anchor="nw", image=photo)
            
            # スクロール領域を設定
            canvas.configure(scrollregion=(0, 0, pil_image.width, pil_image.height))
            
            print(f"[MicroView] 画像表示完了: {key}")
            
        except Exception as e:
            print(f"⚠️ [MicroView] 画像表示エラー ({key}): {e}")
            import traceback
            traceback.print_exc()
    
    def _update_text_tab(self):
        """テキスト比較タブを更新"""
        if not self.matched_pair:
            return
        
        # テキスト取得
        web_text = self.matched_pair.web_page.text if hasattr(self.matched_pair, 'web_page') else ""
        pdf_text = self.matched_pair.pdf_page.text if hasattr(self.matched_pair, 'pdf_page') else ""
        
        # 差分計算
        diff = list(difflib.unified_diff(
            web_text.splitlines(),
            pdf_text.splitlines(),
            lineterm=''
        ))
        
        # テキスト表示とハイライト
        self._display_diff_text(web_text, pdf_text)
        
        # 統計情報更新
        similarity = self.matched_pair.similarity_score * 100
        self.similarity_label.configure(text=f"類似度: {similarity:.1f}%")
        
        # 差分統計
        added = sum(1 for line in diff if line.startswith('+'))
        removed = sum(1 for line in diff if line.startswith('-'))
        self.diff_stats_label.configure(
            text=f"追加: {added}行 | 削除: {removed}行"
        )

        # ペアが変わったらAI分析内容もリセット
        self.llm_analysis_text.configure(state="normal")
        self.llm_analysis_text.delete("1.0", tk.END)
        self.llm_analysis_text.insert("1.0", "「AI分析実行」ボタンを押して分析を開始してください...")
        self.llm_analysis_text.configure(state="disabled")
        self.llm_button.configure(state="normal")
    
    def _display_diff_text(self, web_text, pdf_text):
        """差分ハイライト付きでテキスト表示"""
        # クリア
        self.web_text.delete("1.0", tk.END)
        self.pdf_text.delete("1.0", tk.END)
        
        # テキスト挿入
        self.web_text.insert("1.0", web_text)
        self.pdf_text.insert("1.0", pdf_text)
        
        # difflib で詳細な差分を取得（文字単位）
        matcher = difflib.SequenceMatcher(None, web_text, pdf_text)
        
        # Webテキストのハイライト
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                self.web_text.tag_add("delete", f"1.0+{i1}c", f"1.0+{i2}c")
            elif tag == 'replace':
                self.web_text.tag_add("replace", f"1.0+{i1}c", f"1.0+{i2}c")
        
        # PDFテキストのハイライト
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'insert':
                self.pdf_text.tag_add("insert", f"1.0+{j1}c", f"1.0+{j2}c")
            elif tag == 'replace':
                self.pdf_text.tag_add("replace", f"1.0+{j1}c", f"1.0+{j2}c")
    
    def _toggle_onion_skin(self):
        """オニオンスキンモードの切り替え"""
        if self.onion_var.get():
            print("[MicroView] オニオンスキンモード: ON")
            self._create_composite_image()
        else:
            print("[MicroView] オニオンスキンモード: OFF")
            self._update_visual_tab()
    
    def _on_alpha_change(self, value):
        """透過度変更"""
        self.onion_alpha = float(value)
        self.alpha_label.configure(text=f"透過度: {int(value*100)}%")
        
        if self.onion_var.get():
            self._create_composite_image()
    
    def _create_composite_image(self):
        """オニオンスキン用の合成画像を作成"""
        if not self.matched_pair:
            return
        
        try:
            web_img = self.matched_pair.web_page.image
            pdf_img = self.matched_pair.pdf_page.image
            
            if not web_img or not pdf_img:
                return
            
            # 両方の画像を同じサイズにリサイズ
            max_width = max(web_img.width, pdf_img.width)
            max_height = max(web_img.height, pdf_img.height)
            
            web_resized = web_img.resize((max_width, max_height), Image.Resampling.LANCZOS)
            pdf_resized = pdf_img.resize((max_width, max_height), Image.Resampling.LANCZOS)
            
            # アルファブレンド
            composite = Image.blend(
                web_resized.convert('RGB'),
                pdf_resized.convert('RGB'),
                self.onion_alpha
            )
            
            # 表示
            self._display_image(self.web_canvas, composite, "composite")
            self._display_image(self.pdf_canvas, composite, "composite2")
            
        except Exception as e:
            print(f"⚠️ [MicroView] 合成画像作成エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_back_click(self):
        """戻るボタンクリック"""
        if self.on_back:
            self.on_back()

    def _run_llm_analysis(self):
        """LLM分析をバックグラウンドで実行"""
        if not self.matched_pair:
            return

        self.llm_button.configure(state="disabled")
        self.llm_status.configure(text="分析中...", text_color="#FFD700")
        
        self.llm_analysis_text.configure(state="normal")
        self.llm_analysis_text.delete("1.0", tk.END)
        self.llm_analysis_text.insert("1.0", "🤔 AIが違いを分析しています...\nこれには数秒かかる場合があります。")
        self.llm_analysis_text.configure(state="disabled")

        # 別スレッドで実行
        threading.Thread(target=self._llm_analysis_task, daemon=True).start()

    def _llm_analysis_task(self):
        """分析タスクの実体"""
        try:
            # analyzerを取得 (親のmain_windowからアクセスできる前提だが、疎結合にするためmatched_pair経由は難しい)
            # ここでは簡易的に、self.master.master... と辿らず、新しいAnalyzerインスタンスを作るか、
            # もしくはペアデータにAnalyzerへの参照を持たせるのが良いが、
            # シンプルに Analyzer をインポートして使う。
            
            # TODO: 本来はDIすべき
            from app.core.analyzer import ContentAnalyzer
            analyzer = ContentAnalyzer() 
            
            web_text = self.matched_pair.web_page.text if hasattr(self.matched_pair, 'web_page') else ""
            pdf_text = self.matched_pair.pdf_page.text if hasattr(self.matched_pair, 'pdf_page') else ""

            # analyzerはステートフルなので、同じインスタンスを使いたいが、
            # ここではあくまで「ロジックの使用」として割り切る
            result = analyzer.analyze_semantic_difference(web_text, pdf_text)
            
            # UI更新 (メインスレッドで行うべきだが、Tkinterは一部スレッドセーフ、ctkは怪しいのでafterを使う)
            self.after(0, lambda: self._update_llm_result(result))
            
        except Exception as e:
            error_msg = f"エラーが発生しました: {e}"
            self.after(0, lambda: self._update_llm_result(error_msg, error=True))

    def _update_llm_result(self, text, error=False):
        """分析結果を表示"""
        self.llm_analysis_text.configure(state="normal")
        self.llm_analysis_text.delete("1.0", tk.END)
        self.llm_analysis_text.insert("1.0", text)
        self.llm_analysis_text.configure(state="disabled")
        
        self.llm_button.configure(state="normal")
        if error:
            self.llm_status.configure(text="エラー", text_color="#F44336")
        else:
            self.llm_status.configure(text="完了", text_color="#4CAF50")
