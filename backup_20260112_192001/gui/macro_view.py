"""
Macro View Module
全体マップビュー - WebとPDFのグリッド配置、マッチング線描画
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from typing import List, Dict, Optional, Callable, Tuple
from PIL import Image, ImageTk, ImageDraw, ImageFont
import math


class MacroView(ctk.CTkFrame):
    """
    全体マップビュー（Canvas版）
    Webサムネイルとマッチング線を描画
    """
    
    def __init__(
        self,
        master,
        analyzer=None,
        on_detail_click: Optional[Callable] = None,
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            analyzer: ContentAnalyzerインスタンス
            on_detail_click: 詳細比較ボタンのコールバック
        """
        super().__init__(master, **kwargs)
        
        self.analyzer = analyzer
        self.on_detail_click = on_detail_click
        
        # データ（ページレベル）
        self.web_pages: List = []  # PageData
        self.pdf_pages: List = []  # PageData
        
        # データ（エリアレベル・後方互換性）
        self.web_areas: List = []  # DetectedArea
        self.pdf_areas: List = []
        self.matched_pairs: List = []  # MatchedPair
        
        # UI設定
        self.thumbnail_size = (200, 150)
        self.grid_padding = 20
        self.grid_columns = 3
        
        # Canvas上のアイテムID管理
        self.web_items: Dict[str, Dict] = {}  # area.id -> {"rect": id, "text": id, "image": id}
        self.pdf_items: Dict[str, Dict] = {}
        self.line_items: List[int] = []
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🗺️ 全体マッピングビュー",
            font=("Meiryo", 18, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=20, pady=10)
        
        # ツールバー
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=20, pady=10)
        
        ctk.CTkButton(
            toolbar,
            text="🔄 再描画",
            command=self.refresh_canvas,
            width=100,
            height=30
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="📂 画像検索",
            command=self._open_image_search,
            width=120,
            height=30,
            fg_color="#9C27B0"
        ).pack(side="left", padx=5)
        
        # メインキャンバスエリア
        canvas_frame = ctk.CTkFrame(self)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # スクロールバー
        self.v_scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="vertical")
        self.v_scrollbar.pack(side="right", fill="y")
        
        self.h_scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="horizontal")
        self.h_scrollbar.pack(side="bottom", fill="x")
        
        # Canvas
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#2B2B2B",
            highlightthickness=0,
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.v_scrollbar.configure(command=self.canvas.yview)
        self.h_scrollbar.configure(command=self.canvas.xview)
        
        # ドラッグ&ドロップエリア（右下）
        self.drop_zone = ctk.CTkFrame(
            self,
            fg_color="#3A3A3A",
            border_width=2,
            border_color="#9C27B0",
            corner_radius=10,
            width=250,
            height=150
        )
        self.drop_zone.place(relx=0.98, rely=0.95, anchor="se")
        self.drop_zone.pack_propagate(False)
        
        ctk.CTkLabel(
            self.drop_zone,
            text="📸 画像検索\n\n画像をドロップまたは\nボタンから選択",
            font=("Meiryo", 11),
            text_color="#9C27B0"
        ).pack(expand=True)
        
        # 統計情報（左下）
        self.stats_label = ctk.CTkLabel(
            self,
            text="Web: 0 | PDF: 0 | ペア: 0",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.stats_label.place(relx=0.02, rely=0.98, anchor="sw")
    
    def load_from_analyzer(self):
        """Analyzerからデータを読み込んで描画"""
        if not self.analyzer:
            print("⚠️ [MacroView] Analyzerが設定されていません")
            return
        
        print(f"[MacroView] Analyzerからデータ読み込み中...")
        
        # ページデータを優先的に使用
        if hasattr(self.analyzer, 'web_pages') and hasattr(self.analyzer, 'pdf_pages'):
            self.web_pages = self.analyzer.web_pages
            self.pdf_pages = self.analyzer.pdf_pages
            print(f"[MacroView] ページデータを使用")
        else:
            # 後方互換性: エリアデータを使用
            self.web_pages = []
            self.pdf_pages = []
            print(f"[MacroView] ⚠️ エリアデータにフォールバック")
        
        # 旧形式のエリアデータも保持（互換性のため）
        self.web_areas = self.analyzer.web_areas if hasattr(self.analyzer, 'web_areas') else []
        self.pdf_areas = self.analyzer.pdf_areas if hasattr(self.analyzer, 'pdf_areas') else []
        self.matched_pairs = self.analyzer.matched_pairs if hasattr(self.analyzer, 'matched_pairs') else []
        
        print(f"[MacroView] データ読み込み完了:")
        print(f"  Web Pages: {len(self.web_pages)}")
        print(f"  PDF Pages: {len(self.pdf_pages)}")
        print(f"  Matched Pairs: {len(self.matched_pairs)}")
        
        self.refresh_canvas()
    
    def refresh_canvas(self):
        """Canvas全体を再描画"""
        print(f"[MacroView] Canvas再描画開始")
        print(f"  Web Pages: {len(self.web_pages)}")
        print(f"  PDF Pages: {len(self.pdf_pages)}")
        
        # クリア
        self.canvas.delete("all")
        self.web_items.clear()
        self.pdf_items.clear()
        self.line_items.clear()
        
        if not self.web_pages and not self.pdf_pages:
            # プレースホルダー
            print(f"[MacroView] データなし - プレースホルダー表示")
            self.canvas.create_text(
                400, 300,
                text="データがありません\n\nナビゲーションから\n「Web一括クロール」または「PDF一括読込」を実行してください",
                font=("Meiryo", 14),
                fill="gray",
                justify="center"
            )
            return
        
        print(f"[MacroView] 描画処理開始...")
        
        # 左側: Webページ描画
        web_x_start = 50
        web_y_start = 50
        self._draw_page_grid(
            self.web_pages,
            web_x_start,
            web_y_start,
            "🌐 Web Pages",
            "#E08E00",
            self.web_items
        )
        
        # 右側: PDFページ描画
        canvas_width = 1600  # 仮想キャンバス幅
        pdf_x_start = canvas_width // 2 + 50
        pdf_y_start = 50
        self._draw_page_grid(
            self.pdf_pages,
            pdf_x_start,
            pdf_y_start,
            "📁 PDF Pages",
            "#4CAF50",
            self.pdf_items
        )
        
        # マッチング線を描画
        self._draw_matching_lines()
        
        # スクロール領域を設定
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # 統計情報を更新
        self._update_stats()
    
    def _draw_page_grid(
        self,
        pages: List,
        start_x: int,
        start_y: int,
        title: str,
        color: str,
        items_dict: Dict
    ):
        """ページデータをグリッド状に描画（画像付き）"""
        print(f"[MacroView] _draw_page_grid: {title} - {len(pages)} ページ")
        
        # タイトル
        self.canvas.create_text(
            start_x, start_y - 20,
            text=title,
            font=("Meiryo", 14, "bold"),
            fill=color,
            anchor="w"
        )
        
        # 画像キャッシュ（GC対策）
        # ⚠️ 重要: Tkinterの画像はPythonで参照を保持しないとGCで消える
        if not hasattr(self, '_image_cache'):
            self._image_cache = []
        # 既存のキャッシュはクリアしない（複数回描画対応）
        
        # グリッド配置
        for i, page in enumerate(pages):
            try:
                print(f"[MacroView]   [{i+1}/{len(pages)}] Drawing: {page.source_id[:60] if hasattr(page, 'source_id') else 'Unknown'}")
                
                row = i // self.grid_columns
                col = i % self.grid_columns
                
                x = start_x + col * (self.thumbnail_size[0] + self.grid_padding)
                y = start_y + row * (self.thumbnail_size[1] + self.grid_padding)
                
                # エラーページの場合は特別表示
                has_error = hasattr(page, 'error') and page.error
                
                # 画像を描画
                image_id = None
                if page.image and not has_error:
                    try:
                        # サムネイル生成
                        thumbnail = page.image.copy()
                        thumbnail.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                        
                        # PhotoImageに変換
                        photo = ImageTk.PhotoImage(thumbnail)
                        self._image_cache.append(photo)  # GC対策
                        
                        # キャンバスに描画
                        image_id = self.canvas.create_image(
                            x + self.thumbnail_size[0] // 2,
                            y + self.thumbnail_size[1] // 2,
                            image=photo
                        )
                        
                        # 画像にクリックイベントを追加（ページ自体をクリック可能に）
                        self.canvas.tag_bind(image_id, "<Button-1>", lambda e, pg=page: self._on_page_click(pg))
                        
                    except Exception as e:
                        print(f"⚠️ [MacroView] 画像描画エラー: {e}")
                
                # 画像がない場合またはエラーの場合はプレースホルダー
                if not image_id or has_error:
                    # エラーの場合は赤背景
                    bg_color = "#3A1A1A" if has_error else "#2A2A2A"
                    text_color = "#FF4444" if has_error else "gray"
                    
                    rect_id = self.canvas.create_rectangle(
                        x, y,
                        x + self.thumbnail_size[0],
                        y + self.thumbnail_size[1],
                        outline=color if not has_error else "#FF4444",
                        width=3,
                        fill=bg_color
                    )
                    
                    # プレースホルダーにもクリックイベントを追加
                    if not has_error:
                        self.canvas.tag_bind(rect_id, "<Button-1>", lambda e, pg=page: self._on_page_click(pg))
                    
                    # エラーメッセージを表示
                    if has_error:
                        error_short = page.error[:40] + "..." if len(page.error) > 40 else page.error
                        self.canvas.create_text(
                            x + self.thumbnail_size[0] // 2,
                            y + self.thumbnail_size[1] // 2,
                            text=f"⚠️ エラー\n{error_short}",
                            font=("Meiryo", 9),
                            fill=text_color,
                            width=self.thumbnail_size[0] - 20,
                            justify="center"
                        )
                    else:
                        self.canvas.create_text(
                            x + self.thumbnail_size[0] // 2,
                            y + self.thumbnail_size[1] // 2,
                            text="No Image",
                            font=("Meiryo", 12),
                            fill=text_color
                        )
                else:
                    # 枠線を描画（正常な画像の場合のみ）
                    self.canvas.create_rectangle(
                        x, y,
                        x + self.thumbnail_size[0],
                        y + self.thumbnail_size[1],
                        outline=color,
                        width=3
                    )
                
                # タイトル/URL（下部）
                if has_error:
                    # エラーの場合は赤色で表示
                    label_text = "⚠️ 取得失敗"
                    label_color = "#FF4444"
                else:
                    label_text = page.title[:20] + "..." if len(page.title) > 20 else page.title
                    if page.source_type == "pdf":
                        label_text = f"Page {page.page_num}"
                    label_color = color
                
                self.canvas.create_text(
                    x + self.thumbnail_size[0] // 2,
                    y + self.thumbnail_size[1] + 10,
                    text=label_text,
                    font=("Meiryo", 9),
                    fill=label_color
                )
                
                # アイテムIDを保存
                items_dict[page.id] = {
                    "image": image_id,
                    "x": x + self.thumbnail_size[0] // 2,
                    "y": y + self.thumbnail_size[1] // 2,
                    "has_error": has_error
                }
                
                print(f"[MacroView]     ✅ Drawn successfully")
                
            except Exception as e:
                print(f"⚠️ [MacroView] ページ描画エラー ({i+1}/{len(pages)}): {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"[MacroView] _draw_page_grid完了: {len(items_dict)} アイテム描画")
    
    def _draw_grid(
        self,
        areas: List,
        start_x: int,
        start_y: int,
        title: str,
        color: str,
        items_dict: Dict
    ):
        """グリッド状にエリアを描画（後方互換性用・非推奨）"""
        print(f"⚠️ [MacroView] _draw_gridは非推奨です。_draw_page_gridを使用してください。")
    
    def _draw_matching_lines(self):
        """マッチング線を描画"""
        print(f"[MacroView] _draw_matching_lines: {len(self.matched_pairs)} ペア")
        
        for pair in self.matched_pairs:
            # PageDataベースの場合
            web_id = pair.web_page.id if hasattr(pair, 'web_page') else pair.web_area.id
            pdf_id = pair.pdf_page.id if hasattr(pair, 'pdf_page') else pair.pdf_area.id
            
            if web_id not in self.web_items or pdf_id not in self.pdf_items:
                continue
            
            # 座標を取得
            x1 = self.web_items[web_id]["x"]
            y1 = self.web_items[web_id]["y"]
            x2 = self.pdf_items[pdf_id]["x"]
            y2 = self.pdf_items[pdf_id]["y"]
            
            # 類似度に応じた色
            score = pair.similarity_score
            if score >= 0.7:
                line_color = "#4CAF50"  # 緑
            elif score >= 0.4:
                line_color = "#FFC107"  # 黄
            else:
                line_color = "#FF5722"  # 赤
            
            # ベジェ曲線風に描画
            line_id = self._draw_bezier_line(
                x1, y1, x2, y2,
                color=line_color,
                width=2
            )
            
            # クリックイベントを追加（詳細比較に遷移）
            self.canvas.tag_bind(line_id, "<Button-1>", lambda e, p=pair: self._on_pair_click(p))
            self.canvas.tag_bind(line_id, "<Enter>", lambda e, lid=line_id: self.canvas.itemconfig(lid, width=4))
            self.canvas.tag_bind(line_id, "<Leave>", lambda e, lid=line_id: self.canvas.itemconfig(lid, width=2))
            
            self.line_items.append(line_id)
            
            # スコアラベル
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            self.canvas.create_text(
                mid_x, mid_y - 10,
                text=f"{score:.0%}",
                font=("Meiryo", 9, "bold"),
                fill=line_color
            )
    
    def _draw_bezier_line(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        color: str = "white",
        width: int = 2
    ) -> int:
        """ベジェ曲線風の線を描画"""
        # 制御点を計算
        cx = (x1 + x2) // 2
        cy = min(y1, y2) - 50
        
        # 簡易的な曲線（複数の直線で近似）
        points = []
        steps = 20
        for i in range(steps + 1):
            t = i / steps
            # 2次ベジェ曲線
            x = (1-t)**2 * x1 + 2*(1-t)*t * cx + t**2 * x2
            y = (1-t)**2 * y1 + 2*(1-t)*t * cy + t**2 * y2
            points.extend([x, y])
        
        return self.canvas.create_line(
            *points,
            fill=color,
            width=width,
            smooth=True
        )
    
    def _update_stats(self):
        """統計情報を更新"""
        web_count = len(self.web_pages) if self.web_pages else len(self.web_areas)
        pdf_count = len(self.pdf_pages) if self.pdf_pages else len(self.pdf_areas)
        pair_count = len(self.matched_pairs)
        
        self.stats_label.configure(
            text=f"Web: {web_count} | PDF: {pdf_count} | ペア: {pair_count}"
        )
    
    def _on_pair_click(self, pair):
        """ペアクリック時の処理（詳細比較画面に遷移）"""
        print(f"[MacroView] ペアクリック: {pair}")
        
        if self.on_detail_click:
            self.on_detail_click(pair)
    
    def _on_page_click(self, page):
        """ページクリック時の処理（ペアを探して詳細比較画面に遷移）"""
        print(f"[MacroView] ページクリック: {page.id if hasattr(page, 'id') else 'Unknown'}")
        
        # このページに紐づくペアを検索
        target_pair = None
        for pair in self.matched_pairs:
            if hasattr(pair, 'web_page') and pair.web_page.id == page.id:
                target_pair = pair
                break
            elif hasattr(pair, 'pdf_page') and pair.pdf_page.id == page.id:
                target_pair = pair
                break
        
        if target_pair:
            print(f"[MacroView] ペアが見つかりました -> 詳細比較画面に遷移")
            if self.on_detail_click:
                self.on_detail_click(target_pair)
        else:
            print(f"[MacroView] このページに紐づくペアがありません")
            from tkinter import messagebox
            messagebox.showinfo(
                "ペアなし",
                "このページは他のページとマッチングされていません。\n自動マッチング機能を実行してください。"
            )
    
    def _open_image_search(self):
        """画像検索ダイアログを開く"""
        file_path = filedialog.askopenfilename(
            title="検索する画像を選択",
            filetypes=[
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp"),
                ("全てのファイル", "*.*")
            ]
        )
        
        if file_path:
            print(f"🔍 画像検索: {file_path}")
            # TODO: VisualSearchEngineを使用した逆引き検索
            # 今は未実装メッセージ
            self.canvas.create_text(
                800, 400,
                text=f"画像検索機能は実装予定です\n選択された画像: {file_path}",
                font=("Meiryo", 12),
                fill="#9C27B0",
                justify="center",
                tags="search_message"
            )
            self.after(3000, lambda: self.canvas.delete("search_message"))

