"""
インタラクティブキャンバスエディター
画像上の矩形領域を編集できる再利用可能なコンポーネント
"""
import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import List, Dict, Optional, Callable
import os


class InteractiveCanvas:
    """インタラクティブキャンバスクラス"""
    
    def __init__(self, parent, width=800, height=600):
        """
        Args:
            parent: 親ウィジェット
            width: キャンバス幅
            height: キャンバス高さ
        """
        self.parent = parent
        self.canvas_width = width
        self.canvas_height = height
        
        # キャンバス作成
        self.canvas = Canvas(
            parent,
            width=width,
            height=height,
            bg="#202020",
            highlightthickness=0
        )
        
        # 画像関連
        self.original_image = None
        self.display_image = None
        self.image_tk = None
        self.image_id = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # 矩形データ
        self.areas = []  # [{"area_id": int, "bbox": [x0, y0, x1, y1], "text": str}, ...]
        self.rect_ids = {}  # {area_id: canvas_rect_id}
        self.label_ids = {}  # {area_id: canvas_text_id}
        
        # 編集状態
        self.is_drawing = False
        self.draw_start_x = None
        self.draw_start_y = None
        self.temp_rect_id = None
        self.selected_area_id = None
        
        # コールバック
        self.on_area_selected = None  # 領域選択時のコールバック
        self.on_area_created = None  # 領域作成時のコールバック
        self.on_area_deleted = None  # 領域削除時のコールバック
        
        # イベントバインド
        self._bind_events()
    
    def _bind_events(self):
        """イベントをバインド"""
        self.canvas.bind("<ButtonPress-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<ButtonPress-3>", self._on_right_click)
    
    def pack(self, **kwargs):
        """キャンバスをpack"""
        self.canvas.pack(**kwargs)
    
    def load_image(self, image_path: str):
        """画像を読み込み"""
        if not os.path.exists(image_path):
            return False
        
        try:
            self.original_image = Image.open(image_path)
            self._update_display()
            return True
        except Exception as e:
            print(f"画像読み込みエラー: {e}")
            return False
    
    def load_image_from_pil(self, image: Image.Image):
        """PIL画像を読み込み"""
        self.original_image = image
        self._update_display()
    
    def set_areas(self, areas: List[Dict]):
        """領域データを設定
        Args:
            areas: [{"area_id": int, "bbox": [x0, y0, x1, y1], "text": str}, ...]
        """
        self.areas = areas
        self._draw_all_areas()
    
    def get_areas(self) -> List[Dict]:
        """領域データを取得"""
        return self.areas
    
    def clear_areas(self):
        """すべての領域をクリア"""
        for rect_id in self.rect_ids.values():
            self.canvas.delete(rect_id)
        for label_id in self.label_ids.values():
            self.canvas.delete(label_id)
        
        self.rect_ids.clear()
        self.label_ids.clear()
        self.areas.clear()
        self.selected_area_id = None
    
    def _update_display(self):
        """表示を更新"""
        if not self.original_image:
            return
        
        # 画像をキャンバスサイズに合わせてリサイズ
        img_w, img_h = self.original_image.size
        scale_w = self.canvas_width / img_w
        scale_h = self.canvas_height / img_h
        self.scale = min(scale_w, scale_h, 1.0)  # 最大1.0（拡大しない）
        
        new_w = int(img_w * self.scale)
        new_h = int(img_h * self.scale)
        
        self.display_image = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.image_tk = ImageTk.PhotoImage(self.display_image)
        
        # 中央に配置
        self.offset_x = (self.canvas_width - new_w) // 2
        self.offset_y = (self.canvas_height - new_h) // 2
        
        # キャンバスに描画
        if self.image_id:
            self.canvas.delete(self.image_id)
        
        self.image_id = self.canvas.create_image(
            self.offset_x, self.offset_y,
            anchor="nw",
            image=self.image_tk
        )
        
        # 矩形を再描画
        self._draw_all_areas()
    
    def _draw_all_areas(self):
        """すべての領域を描画"""
        # 既存の矩形を削除
        for rect_id in self.rect_ids.values():
            self.canvas.delete(rect_id)
        for label_id in self.label_ids.values():
            self.canvas.delete(label_id)
        
        self.rect_ids.clear()
        self.label_ids.clear()
        
        # 領域を描画
        for area in self.areas:
            self._draw_area(area)
    
    def _draw_area(self, area: Dict):
        """単一の領域を描画"""
        area_id = area["area_id"]
        bbox = area["bbox"]  # [x0, y0, x1, y1] (元画像座標)
        
        # キャンバス座標に変換
        x0 = bbox[0] * self.scale + self.offset_x
        y0 = bbox[1] * self.scale + self.offset_y
        x1 = bbox[2] * self.scale + self.offset_x
        y1 = bbox[3] * self.scale + self.offset_y
        
        # 矩形を描画
        color = "#00FF00" if area_id == self.selected_area_id else "#FF9800"
        rect_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline=color,
            width=2,
            tags=f"area_{area_id}"
        )
        self.rect_ids[area_id] = rect_id
        
        # エリアナンバーを描画
        label_id = self.canvas.create_text(
            x0 + 5, y0 + 5,
            text=f"#{area_id}",
            anchor="nw",
            fill="#FFFFFF",
            font=("Arial", 10, "bold"),
            tags=f"label_{area_id}"
        )
        self.label_ids[area_id] = label_id
    
    def _on_left_press(self, event):
        """左クリック開始"""
        # 既存の矩形をクリックしたか確認
        clicked_area = self._get_area_at_position(event.x, event.y)
        
        if clicked_area:
            # 既存の領域を選択
            self.selected_area_id = clicked_area["area_id"]
            self._draw_all_areas()
            
            if self.on_area_selected:
                self.on_area_selected(clicked_area)
        else:
            # 新規矩形の描画開始
            self.is_drawing = True
            self.draw_start_x = event.x
            self.draw_start_y = event.y
    
    def _on_left_drag(self, event):
        """左ドラッグ"""
        if not self.is_drawing:
            return
        
        # 一時的な矩形を描画
        if self.temp_rect_id:
            self.canvas.delete(self.temp_rect_id)
        
        self.temp_rect_id = self.canvas.create_rectangle(
            self.draw_start_x, self.draw_start_y,
            event.x, event.y,
            outline="#00FF00",
            width=2,
            dash=(4, 4)
        )
    
    def _on_left_release(self, event):
        """左クリック終了"""
        if not self.is_drawing:
            return
        
        self.is_drawing = False
        
        # 一時的な矩形を削除
        if self.temp_rect_id:
            self.canvas.delete(self.temp_rect_id)
            self.temp_rect_id = None
        
        # 矩形のサイズをチェック
        if abs(event.x - self.draw_start_x) < 10 or abs(event.y - self.draw_start_y) < 10:
            return  # 小さすぎる矩形は無視
        
        # キャンバス座標を元画像座標に変換
        x0 = min(self.draw_start_x, event.x)
        y0 = min(self.draw_start_y, event.y)
        x1 = max(self.draw_start_x, event.x)
        y1 = max(self.draw_start_y, event.y)
        
        # オフセットとスケールを考慮
        img_x0 = (x0 - self.offset_x) / self.scale
        img_y0 = (y0 - self.offset_y) / self.scale
        img_x1 = (x1 - self.offset_x) / self.scale
        img_y1 = (y1 - self.offset_y) / self.scale
        
        # 新しい領域を作成
        new_area_id = max([a["area_id"] for a in self.areas], default=0) + 1
        new_area = {
            "area_id": new_area_id,
            "bbox": [img_x0, img_y0, img_x1, img_y1],
            "text": ""
        }
        
        self.areas.append(new_area)
        self._draw_area(new_area)
        
        if self.on_area_created:
            self.on_area_created(new_area)
    
    def _on_right_click(self, event):
        """右クリック（削除）"""
        clicked_area = self._get_area_at_position(event.x, event.y)
        
        if clicked_area:
            area_id = clicked_area["area_id"]
            
            # 矩形を削除
            if area_id in self.rect_ids:
                self.canvas.delete(self.rect_ids[area_id])
                del self.rect_ids[area_id]
            
            if area_id in self.label_ids:
                self.canvas.delete(self.label_ids[area_id])
                del self.label_ids[area_id]
            
            # データから削除
            self.areas = [a for a in self.areas if a["area_id"] != area_id]
            
            if self.selected_area_id == area_id:
                self.selected_area_id = None
            
            if self.on_area_deleted:
                self.on_area_deleted(clicked_area)
    
    def _get_area_at_position(self, x, y) -> Optional[Dict]:
        """指定位置の領域を取得"""
        for area in self.areas:
            bbox = area["bbox"]
            
            # キャンバス座標に変換
            x0 = bbox[0] * self.scale + self.offset_x
            y0 = bbox[1] * self.scale + self.offset_y
            x1 = bbox[2] * self.scale + self.offset_x
            y1 = bbox[3] * self.scale + self.offset_y
            
            if x0 <= x <= x1 and y0 <= y <= y1:
                return area
        
        return None


