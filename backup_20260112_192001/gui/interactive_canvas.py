"""
画像上の領域編集を行うための専用クラス
"""
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class InteractiveCanvas(ctk.CTkFrame):
    """画像上に矩形領域を表示・編集するインタラクティブキャンバス"""
    
    def __init__(self, master, width=800, height=600, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        
        # ヘッダーラベル（URL/ファイル名表示）
        self.header_label = ctk.CTkLabel(
            self,
            text="",
            font=("Arial", 14, "bold"),
            anchor="w",
            height=40
        )
        self.header_label.pack(fill="x", padx=10, pady=(5, 0))
        
        # キャンバスとスクロールバーのフレーム
        canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 縦スクロールバー
        self.v_scrollbar = tk.Scrollbar(canvas_frame, orient="vertical")
        self.v_scrollbar.pack(side="right", fill="y")
        
        # 横スクロールバー
        self.h_scrollbar = tk.Scrollbar(canvas_frame, orient="horizontal")
        self.h_scrollbar.pack(side="bottom", fill="x")
        
        # キャンバス
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#2B2B2B",
            highlightthickness=0,
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # スクロールバーとキャンバスを連携
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)
        
        # 内部データ
        self.current_image_path: Optional[str] = None
        self.pil_image: Optional[Image.Image] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None  # GC対策
        self.image_id: Optional[int] = None
        self.areas: List[Dict] = []  # {"id": int, "bbox": [x0,y0,x1,y1], "rect_id": int, "badge_ids": list, "selected": bool}
        self.next_area_id = 1
        self.selected_area_id: Optional[int] = None  # 選択中のエリアID
        
        # オニオンスキンモード用
        self.onion_skin_mode: bool = False
        self.base_image: Optional[Image.Image] = None  # 下層画像（Web）
        self.overlay_image: Optional[Image.Image] = None  # 上層画像（PDF）
        self.blend_alpha: float = 0.5  # 混合比率（0.0=base, 1.0=overlay）
        self.offset_x: int = 0  # 上層画像のX方向オフセット
        self.offset_y: int = 0  # 上層画像のY方向オフセット
        self.onion_slider: Optional[ctk.CTkSlider] = None
        self.onion_control_frame: Optional[ctk.CTkFrame] = None
        
        # ドラッグ用の一時変数
        self.drag_start: Optional[Tuple[int, int]] = None
        self.temp_rect_id: Optional[int] = None
        self.is_dragging: bool = False
        
        # マウスイベントバインド
        self.canvas.bind("<Button-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        
        # === テキストベースオニオンレイヤー用 ===
        self.text_overlay_mode: bool = False
        self.web_clusters: List[Dict] = []   # [{"id": str, "rect": [x0,y0,x1,y1], "text": str}, ...]
        self.pdf_clusters: List[Dict] = []   # 同上
        self.cluster_matches: List[Dict] = []  # [{"web_id": str, "pdf_id": str, "score": float}, ...]
        self.active_source: str = "web"  # "web" or "pdf" - どちらの枠を前面に表示するか
        self._web_rect_ids: List[int] = []
        self._pdf_rect_ids: List[int] = []
        self._match_line_ids: List[int] = []
        
        # 選択コールバック（外部からセット可能）
        self.on_area_selected: Optional[callable] = None  # callback(area_id, source, text)
    
    def load_data(self, image_path: str, title: str, area_data_list: List[Dict] = None):
        """
        画像と既存エリアデータを読み込む（推奨メソッド）
        
        Args:
            image_path: 画像ファイルのパス
            title: ヘッダーに表示するタイトル（URL/ファイル名）
            area_data_list: 既存の矩形エリアリスト [{"bbox": [x0,y0,x1,y1], "area_id": int}, ...]
        """
        self.load_image(image_path, title, area_data_list)
    
    def load_image(self, image_path: str, title: str, areas: List[Dict] = None):
        """
        画像と既存エリアを読み込む
        
        Args:
            image_path: 画像ファイルのパス
            title: ヘッダーに表示するタイトル（URL/ファイル名）
            areas: 既存の矩形エリアリスト [{"bbox": [x0,y0,x1,y1]}, ...]
        """
        # ヘッダー更新
        self.header_label.configure(text=title)
        
        # 画像読み込み
        try:
            self.current_image_path = image_path
            self.pil_image = Image.open(image_path)
            self._display_image()
        except Exception as e:
            print(f"⚠️ 画像読み込みエラー: {e}")
            return
        
        # 既存エリアを描画
        self._load_areas(areas)
    
    def load_image_from_pil(self, pil_image: Image.Image, title: str = "", areas: List[Dict] = None):
        """
        PIL Imageオブジェクトから直接読み込む
        
        Args:
            pil_image: PIL.Image.Image オブジェクト
            title: ヘッダーに表示するタイトル
            areas: 既存の矩形エリアリスト
        """
        # ヘッダー更新
        if title:
            self.header_label.configure(text=title)
        
        # 画像読み込み
        self.current_image_path = None
        self.pil_image = pil_image
        self._display_image()
        
        # 既存エリアを描画
        self._load_areas(areas)
    
    def _load_areas(self, areas: List[Dict] = None):
        """エリアデータを読み込んで描画"""
        self.areas.clear()
        self.next_area_id = 1
        self.selected_area_id = None
        
        if areas:
            for area in areas:
                bbox = area.get("bbox", [0, 0, 100, 100])
                self._add_area(bbox)
    
    def _display_image(self):
        """画像をキャンバスに表示"""
        if not self.pil_image:
            return
        
        # PIL ImageをPhotoImageに変換（GC対策で参照保持）
        self.tk_image = ImageTk.PhotoImage(self.pil_image)
        
        # キャンバスクリア
        self.canvas.delete("all")
        
        # 画像を配置
        self.image_id = self.canvas.create_image(
            0, 0,
            anchor="nw",
            image=self.tk_image
        )
        
        # スクロール領域を設定
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
    
    def _add_area(self, bbox: List[int], selected: bool = False):
        """矩形エリアを追加
        
        Args:
            bbox: [x0, y0, x1, y1]
            selected: 選択状態かどうか
        """
        x0, y0, x1, y1 = bbox
        
        # 矩形を描画（赤枠、選択時は緑）
        color = "green" if selected else "red"
        rect_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline=color,
            width=3 if selected else 2,
            tags="area"
        )
        
        # エリア番号バッジを描画（丸数字）
        circle_numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
                         "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]
        
        badge_text = circle_numbers[self.next_area_id - 1] if self.next_area_id <= 20 else str(self.next_area_id)
        
        badge_bg_id = self.canvas.create_rectangle(
            x0, y0, x0 + 35, y0 + 25,
            fill=color,
            outline="",
            tags="badge_bg"
        )
        
        badge_text_id = self.canvas.create_text(
            x0 + 17, y0 + 12,
            text=badge_text,
            fill="white",
            font=("Arial", 12, "bold"),
            tags="badge_text"
        )
        
        # エリア情報を保存
        self.areas.append({
            "id": self.next_area_id,
            "bbox": [x0, y0, x1, y1],
            "rect_id": rect_id,
            "badge_bg_id": badge_bg_id,
            "badge_text_id": badge_text_id,
            "selected": selected
        })
        
        self.next_area_id += 1
    
    def _on_left_press(self, event):
        """マウス左ボタン押下（選択またはドラッグ開始）"""
        # キャンバス座標に変換
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # クリック位置にエリアがあるか確認（選択機能）
        clicked_area = None
        for area in self.areas:
            x0, y0, x1, y1 = area["bbox"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                clicked_area = area
                break
        
        if clicked_area:
            # エリアをクリックした場合は選択
            self._select_area(clicked_area["id"])
            self.is_dragging = False
        else:
            # 空白をクリックした場合は新規ドラッグ開始
            self.is_dragging = True
            self.drag_start = (x, y)
            # 一時的な矩形を作成
            self.temp_rect_id = self.canvas.create_rectangle(
                x, y, x, y,
                outline="yellow",
                width=2,
                dash=(4, 4),
                tags="temp"
            )
    
    def _on_left_drag(self, event):
        """マウス左ドラッグ中"""
        if not self.is_dragging or self.drag_start is None or self.temp_rect_id is None:
            return
        
        # キャンバス座標に変換
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 一時矩形を更新
        x0, y0 = self.drag_start
        self.canvas.coords(self.temp_rect_id, x0, y0, x, y)
    
    def _on_left_release(self, event):
        """マウス左ボタン離す（矩形確定）"""
        if not self.is_dragging or self.drag_start is None or self.temp_rect_id is None:
            return
        
        # キャンバス座標に変換
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        x0, y0 = self.drag_start
        
        # 一時矩形を削除
        self.canvas.delete(self.temp_rect_id)
        self.temp_rect_id = None
        self.drag_start = None
        self.is_dragging = False
        
        # 最小サイズチェック（10px以上）
        if abs(x - x0) < 10 or abs(y - y0) < 10:
            return
        
        # 座標を正規化（左上→右下）
        bbox = [
            min(x0, x),
            min(y0, y),
            max(x0, x),
            max(y0, y)
        ]
        
        # 新しいエリアを追加
        self._add_area(bbox)
    
    def _select_area(self, area_id: int):
        """エリアを選択状態にする"""
        # 以前の選択を解除
        if self.selected_area_id is not None:
            for area in self.areas:
                if area["id"] == self.selected_area_id:
                    area["selected"] = False
                    self.canvas.itemconfig(area["rect_id"], outline="red", width=2)
                    self.canvas.itemconfig(area["badge_bg_id"], fill="red")
                    break
        
        # 新しいエリアを選択
        selected_area = None
        for area in self.areas:
            if area["id"] == area_id:
                area["selected"] = True
                self.canvas.itemconfig(area["rect_id"], outline="green", width=3)
                self.canvas.itemconfig(area["badge_bg_id"], fill="green")
                self.selected_area_id = area_id
                selected_area = area
                break
        
        # コールバック発火（即時セル反映用）
        if selected_area and self.on_area_selected:
            try:
                area_text = selected_area.get("text", "")
                source = "web"  # デフォルト
                self.on_area_selected(area_id, source, area_text)
            except Exception as e:
                print(f"⚠️ on_area_selected callback error: {e}")
    
    def _on_right_click(self, event):
        """右クリック（矩形削除）"""
        # キャンバス座標に変換
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # クリック位置にある矩形を探す
        for area in self.areas[:]:  # コピーしてループ（削除するため）
            x0, y0, x1, y1 = area["bbox"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                # 矩形とバッジを削除
                self.canvas.delete(area["rect_id"])
                self.canvas.delete(area["badge_bg_id"])
                self.canvas.delete(area["badge_text_id"])
                self.areas.remove(area)
                
                # エリア番号を振り直す
                self._renumber_areas()
                break
    
    def _renumber_areas(self):
        """エリア番号を振り直す"""
        circle_numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
                         "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]
        
        for idx, area in enumerate(self.areas, start=1):
            area["id"] = idx
            # バッジテキストを更新
            badge_text = circle_numbers[idx - 1] if idx <= 20 else str(idx)
            self.canvas.itemconfig(area["badge_text_id"], text=badge_text)
        
        self.next_area_id = len(self.areas) + 1
        
        # 選択中のエリアが削除された場合、選択解除
        if self.selected_area_id is not None:
            if not any(area["id"] == self.selected_area_id for area in self.areas):
                self.selected_area_id = None
    
    def get_areas(self) -> List[Dict]:
        """
        現在のエリアリストを取得
        
        Returns:
            List[Dict]: [{"id": int, "bbox": [x0,y0,x1,y1]}, ...]
        """
        return [
            {
                "id": area["id"],
                "bbox": area["bbox"].copy()
            }
            for area in self.areas
        ]
    
    def clear(self):
        """キャンバスをクリア"""
        self.canvas.delete("all")
        self.areas.clear()
        self.next_area_id = 1
        self.selected_area_id = None
        self.current_image_path = None
        self.pil_image = None
        self.tk_image = None
        self.image_id = None
        self.header_label.configure(text="")
    
    def set_title(self, title: str):
        """ヘッダータイトルを設定"""
        self.header_label.configure(text=title)
    
    def enable_onion_skin_mode(
        self,
        base_image: Image.Image,
        overlay_image: Image.Image,
        base_title: str = "Base",
        overlay_title: str = "Overlay"
    ):
        """
        オニオンスキン（重ね合わせ）モードを有効化
        
        Args:
            base_image: 下層画像（Webなど）
            overlay_image: 上層画像（PDFなど）
            base_title: 下層画像のタイトル
            overlay_title: 上層画像のタイトル
        """
        self.onion_skin_mode = True
        self.base_image = base_image
        self.overlay_image = overlay_image
        self.blend_alpha = 0.5
        self.offset_x = 0
        self.offset_y = 0
        
        # ヘッダー更新
        self.header_label.configure(text=f"🔄 オニオンスキン: {base_title} ⇔ {overlay_title}")
        
        # コントロールパネルを表示
        self._show_onion_controls()
        
        # 合成画像を表示
        self._update_onion_skin()
        
        # 矢印キーのバインド（位置合わせ用）
        self.canvas.bind("<Left>", lambda e: self._nudge_overlay(-1, 0))
        self.canvas.bind("<Right>", lambda e: self._nudge_overlay(1, 0))
        self.canvas.bind("<Up>", lambda e: self._nudge_overlay(0, -1))
        self.canvas.bind("<Down>", lambda e: self._nudge_overlay(0, 1))
        self.canvas.focus_set()  # キャンバスにフォーカス
    
    def disable_onion_skin_mode(self):
        """オニオンスキンモードを無効化"""
        self.onion_skin_mode = False
        self.base_image = None
        self.overlay_image = None
        
        # コントロールパネルを非表示
        if self.onion_control_frame:
            self.onion_control_frame.pack_forget()
            self.onion_control_frame = None
        
        # 矢印キーのバインド解除
        self.canvas.unbind("<Left>")
        self.canvas.unbind("<Right>")
        self.canvas.unbind("<Up>")
        self.canvas.unbind("<Down>")
    
    def _show_onion_controls(self):
        """オニオンスキン用のコントロールパネルを表示"""
        if self.onion_control_frame:
            self.onion_control_frame.pack_forget()
        
        # コントロールフレーム
        self.onion_control_frame = ctk.CTkFrame(self, height=100)
        self.onion_control_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        self.onion_control_frame.pack_propagate(False)
        
        # タイトル
        ctk.CTkLabel(
            self.onion_control_frame,
            text="🎚️ 透明度調整",
            font=("Arial", 12, "bold")
        ).pack(pady=(5, 0))
        
        # スライダーラベル
        label_frame = ctk.CTkFrame(self.onion_control_frame, fg_color="transparent")
        label_frame.pack(fill="x", padx=20, pady=(5, 0))
        
        ctk.CTkLabel(
            label_frame,
            text="Web 100%",
            font=("Arial", 10)
        ).pack(side="left")
        
        ctk.CTkLabel(
            label_frame,
            text="PDF 100%",
            font=("Arial", 10)
        ).pack(side="right")
        
        # 透明度スライダー
        self.onion_slider = ctk.CTkSlider(
            self.onion_control_frame,
            from_=0.0,
            to=1.0,
            command=self._on_slider_change,
            width=500
        )
        self.onion_slider.set(0.5)
        self.onion_slider.pack(pady=(0, 5))
        
        # 情報表示
        info_frame = ctk.CTkFrame(self.onion_control_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=20)
        
        ctk.CTkLabel(
            info_frame,
            text="💡 矢印キー (↑↓←→) で上層画像を微調整できます",
            font=("Arial", 9),
            text_color="gray"
        ).pack(side="left")
        
        # リセットボタン
        ctk.CTkButton(
            info_frame,
            text="🔄 リセット",
            command=self._reset_onion_skin,
            width=80,
            height=25,
            font=("Arial", 9)
        ).pack(side="right")
    
    def _on_slider_change(self, value: float):
        """スライダー値変更時のコールバック"""
        self.blend_alpha = value
        self._update_onion_skin()
    
    def _nudge_overlay(self, dx: int, dy: int):
        """上層画像を微調整（ナッジ）
        
        Args:
            dx: X方向の移動量（ピクセル）
            dy: Y方向の移動量（ピクセル）
        """
        self.offset_x += dx
        self.offset_y += dy
        self._update_onion_skin()
        print(f"📍 オフセット: ({self.offset_x}, {self.offset_y})")
    
    def _reset_onion_skin(self):
        """オニオンスキン設定をリセット"""
        self.blend_alpha = 0.5
        self.offset_x = 0
        self.offset_y = 0
        self.onion_slider.set(0.5)
        self._update_onion_skin()
    
    def _update_onion_skin(self):
        """オニオンスキン画像を更新"""
        if not self.base_image or not self.overlay_image:
            return
        
        try:
            # 両画像を同じサイズにリサイズ
            # より大きい方のサイズに合わせる
            max_width = max(self.base_image.width, self.overlay_image.width)
            max_height = max(self.base_image.height, self.overlay_image.height)
            
            # 下層画像をリサイズ
            base_resized = self.base_image.copy()
            if base_resized.size != (max_width, max_height):
                base_resized = base_resized.resize((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 上層画像をリサイズ
            overlay_resized = self.overlay_image.copy()
            if overlay_resized.size != (max_width, max_height):
                overlay_resized = overlay_resized.resize((max_width, max_height), Image.Resampling.LANCZOS)
            
            # オフセットを適用（上層画像を移動）
            if self.offset_x != 0 or self.offset_y != 0:
                # 新しいキャンバスを作成
                offset_canvas = Image.new('RGB', (max_width, max_height), color='white')
                # オフセット位置に上層画像を貼り付け
                paste_x = max(0, self.offset_x)
                paste_y = max(0, self.offset_y)
                
                # クロップ領域を計算（はみ出し防止）
                crop_x = max(0, -self.offset_x)
                crop_y = max(0, -self.offset_y)
                crop_width = min(max_width - paste_x, overlay_resized.width - crop_x)
                crop_height = min(max_height - paste_y, overlay_resized.height - crop_y)
                
                if crop_width > 0 and crop_height > 0:
                    cropped = overlay_resized.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height))
                    offset_canvas.paste(cropped, (paste_x, paste_y))
                    overlay_resized = offset_canvas
            
            # 画像を合成（blend）
            # alpha=0.0 → 100% base（Web）
            # alpha=1.0 → 100% overlay（PDF）
            blended = Image.blend(base_resized, overlay_resized, self.blend_alpha)
            
            # 合成画像を表示
            self.pil_image = blended
            self._display_image()
            
        except Exception as e:
            print(f"⚠️ オニオンスキン更新エラー: {e}")
            import traceback
            traceback.print_exc()
    
    # ==========================================================
    #  テキストベースオニオンレイヤー（Phase C 追加機能）
    # ==========================================================
    
    def enable_text_overlay_mode(
        self,
        web_clusters: List[Dict],
        pdf_clusters: List[Dict],
        matches: List[Dict] = None,
        base_image: Image.Image = None
    ):
        """
        テキストベースオニオンレイヤーを有効化
        画像ではなくテキストクラスター境界を重ね表示
        
        Args:
            web_clusters: [{"id": str, "rect": [x0,y0,x1,y1], "text": str}, ...]
            pdf_clusters: [{"id": str, "rect": [x0,y0,x1,y1], "text": str}, ...]
            matches: [{"web_id": str, "pdf_id": str, "score": float}, ...]
            base_image: 背景画像（オプション）
        """
        self.text_overlay_mode = True
        self.web_clusters = web_clusters or []
        self.pdf_clusters = pdf_clusters or []
        self.cluster_matches = matches or []
        
        # 背景画像がある場合は表示
        if base_image:
            self.pil_image = base_image
            self._display_image()
        
        # ヘッダー更新
        self.header_label.configure(
            text=f"📊 テキストオーバーレイ: Web {len(self.web_clusters)}件 | PDF {len(self.pdf_clusters)}件"
        )
        
        # クラスター枠を描画
        self._draw_text_overlay()
    
    def disable_text_overlay_mode(self):
        """テキストオーバーレイモードを無効化"""
        self.text_overlay_mode = False
        self._clear_text_overlay()
        self.web_clusters = []
        self.pdf_clusters = []
        self.cluster_matches = []
    
    def _draw_text_overlay(self):
        """テキストクラスター境界を描画"""
        self._clear_text_overlay()
        
        # PDF枠を描画（赤/オレンジ、後ろ）
        for cluster in self.pdf_clusters:
            rect = cluster.get("rect", [0, 0, 100, 100])
            cluster_id = cluster.get("id", "?")
            
            rect_id = self.canvas.create_rectangle(
                rect[0], rect[1], rect[2], rect[3],
                outline="#FF6F00",  # オレンジ
                width=2,
                dash=(6, 3),
                tags="pdf_cluster"
            )
            self._pdf_rect_ids.append(rect_id)
            
            # ラベル
            label_id = self.canvas.create_text(
                rect[2], rect[1],
                text=f"PDF-{cluster_id}",
                fill="#FF6F00",
                font=("Arial", 9, "bold"),
                anchor="ne",
                tags="pdf_label"
            )
            self._pdf_rect_ids.append(label_id)
        
        # Web枠を描画（青/シアン、前面）
        for cluster in self.web_clusters:
            rect = cluster.get("rect", [0, 0, 100, 100])
            cluster_id = cluster.get("id", "?")
            
            rect_id = self.canvas.create_rectangle(
                rect[0], rect[1], rect[2], rect[3],
                outline="#00BCD4",  # シアン
                width=2,
                tags="web_cluster"
            )
            self._web_rect_ids.append(rect_id)
            
            # ラベル
            label_id = self.canvas.create_text(
                rect[0], rect[1],
                text=f"WEB-{cluster_id}",
                fill="#00BCD4",
                font=("Arial", 9, "bold"),
                anchor="sw",
                tags="web_label"
            )
            self._web_rect_ids.append(label_id)
        
        # マッチング線を描画
        self._draw_match_lines()
    
    def _draw_match_lines(self):
        """マッチングペア間の接続線を描画"""
        for match in self.cluster_matches:
            web_id = match.get("web_id")
            pdf_id = match.get("pdf_id")
            score = match.get("score", 0)
            
            # 対応するクラスターを探す
            web_cluster = next((c for c in self.web_clusters if str(c.get("id")) == str(web_id)), None)
            pdf_cluster = next((c for c in self.pdf_clusters if str(c.get("id")) == str(pdf_id)), None)
            
            if web_cluster and pdf_cluster:
                # 中心点を計算
                w_rect = web_cluster["rect"]
                p_rect = pdf_cluster["rect"]
                
                w_cx = (w_rect[0] + w_rect[2]) / 2
                w_cy = (w_rect[1] + w_rect[3]) / 2
                p_cx = (p_rect[0] + p_rect[2]) / 2
                p_cy = (p_rect[1] + p_rect[3]) / 2
                
                # スコアに応じて色を変える
                if score >= 0.8:
                    color = "#4CAF50"  # 緑（高マッチ）
                elif score >= 0.5:
                    color = "#FFC107"  # 黄（中マッチ）
                else:
                    color = "#F44336"  # 赤（低マッチ）
                
                line_id = self.canvas.create_line(
                    w_cx, w_cy, p_cx, p_cy,
                    fill=color,
                    width=1,
                    dash=(4, 4),
                    tags="match_line"
                )
                self._match_line_ids.append(line_id)
    
    def _clear_text_overlay(self):
        """テキストオーバーレイの描画をクリア"""
        for rect_id in self._web_rect_ids:
            self.canvas.delete(rect_id)
        for rect_id in self._pdf_rect_ids:
            self.canvas.delete(rect_id)
        for line_id in self._match_line_ids:
            self.canvas.delete(line_id)
        
        self._web_rect_ids.clear()
        self._pdf_rect_ids.clear()
        self._match_line_ids.clear()
        
        self.canvas.delete("web_cluster")
        self.canvas.delete("pdf_cluster")
        self.canvas.delete("web_label")
        self.canvas.delete("pdf_label")
        self.canvas.delete("match_line")
    
    def toggle_active_source(self):
        """前面に表示するソース（Web/PDF）を切り替え"""
        if self.active_source == "web":
            self.active_source = "pdf"
            # PDF枠を前面に
            for rect_id in self._pdf_rect_ids:
                self.canvas.tag_raise(rect_id)
        else:
            self.active_source = "web"
            # Web枠を前面に
            for rect_id in self._web_rect_ids:
                self.canvas.tag_raise(rect_id)
        
        return self.active_source
    
    def get_selected_cluster_text(self) -> Optional[str]:
        """選択中のエリアのテキストを取得"""
        if self.selected_area_id is None:
            return None
        
        for area in self.areas:
            if area["id"] == self.selected_area_id:
                # areasにtextがある場合
                return area.get("text", "")
        
        return None
