"""
MEKIKI Canvas Manager
画像表示・キャッシュ・リサイズの一元管理

Created: 2026-01-28
"""

import tkinter as tk
from typing import Optional, Dict, Tuple, Callable
from PIL import Image, ImageTk
from dataclasses import dataclass
import time


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    photo: ImageTk.PhotoImage
    size: Tuple[int, int]
    timestamp: float


class CanvasManager:
    """
    キャンバス画像表示マネージャー
    
    責務:
    - 画像のリサイズ・表示
    - キャッシュ管理 (メモリ効率)
    - 例外隔離 (UIを壊さない)
    - スクロール連携
    """
    
    MAX_CACHE_SIZE = 3
    RESIZE_DEBOUNCE_MS = 150
    
    def __init__(self, canvas: tk.Canvas, source: str = ""):
        """
        Args:
            canvas: 対象のTkinterキャンバス
            source: 識別子 ("web" or "pdf")
        """
        self.canvas = canvas
        self.source = source
        
        # 画像
        self._current_image: Optional[Image.Image] = None
        self._photo_ref: Optional[ImageTk.PhotoImage] = None
        self._image_id: Optional[int] = None
        
        # キャッシュ
        self._cache: Dict[str, CacheEntry] = {}
        
        # 表示設定
        self.fit_mode: str = "width"  # "width", "fit", "cover"
        self.display_scale: float = 1.0
        
        # リサイズデバウンス
        self._resize_timer: Optional[str] = None
        self._last_size: Tuple[int, int] = (0, 0)
        
        # コールバック
        self._on_display_complete: Optional[Callable] = None
    
    def set_image(self, image: Image.Image, redisplay: bool = True):
        """
        画像を設定
        
        Args:
            image: PIL Image
            redisplay: 即座に再表示するか
        """
        try:
            self._current_image = image
            self._clear_cache()
            if redisplay:
                self.redisplay()
        except Exception as e:
            print(f"⚠️ [{self.source}] set_image error: {e}")
    
    def redisplay(self):
        """現在の画像を再表示"""
        if self._current_image is None:
            return
        
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                return
            
            # キャッシュチェック
            cache_key = f"{canvas_width}x{canvas_height}_{self.fit_mode}"
            if cache_key in self._cache:
                self._display_cached(cache_key)
                return
            
            # リサイズ
            resized = self._resize_image(
                self._current_image,
                canvas_width,
                canvas_height
            )
            
            # PhotoImage作成
            photo = ImageTk.PhotoImage(resized)
            
            # キャッシュ追加
            self._add_to_cache(cache_key, photo, resized.size)
            
            # 表示
            self._display_photo(photo, resized.size)
            
        except Exception as e:
            print(f"⚠️ [{self.source}] redisplay error: {e}")
    
    def _resize_image(
        self,
        image: Image.Image,
        canvas_width: int,
        canvas_height: int
    ) -> Image.Image:
        """
        画像をリサイズ
        
        Args:
            image: 元画像
            canvas_width: キャンバス幅
            canvas_height: キャンバス高さ
        
        Returns:
            リサイズ後の画像
        """
        img_width, img_height = image.size
        
        if self.fit_mode == "width":
            # 幅優先フィット (縦スクロール対応)
            scale = canvas_width / img_width
            new_width = canvas_width
            new_height = int(img_height * scale)
        
        elif self.fit_mode == "fit":
            # 全体表示 (アスペクト比維持)
            scale_w = canvas_width / img_width
            scale_h = canvas_height / img_height
            scale = min(scale_w, scale_h)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
        
        elif self.fit_mode == "cover":
            # カバー表示 (はみ出しあり)
            scale_w = canvas_width / img_width
            scale_h = canvas_height / img_height
            scale = max(scale_w, scale_h)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
        
        else:
            new_width, new_height = img_width, img_height
        
        self.display_scale = canvas_width / img_width
        
        # 最小サイズ保証
        new_width = max(1, new_width)
        new_height = max(1, new_height)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _display_photo(self, photo: ImageTk.PhotoImage, size: Tuple[int, int]):
        """PhotoImageを表示"""
        try:
            # 既存の画像を削除
            if self._image_id:
                self.canvas.delete(self._image_id)
            
            # 新しい画像を表示
            self._image_id = self.canvas.create_image(
                0, 0,
                image=photo,
                anchor="nw"
            )
            
            # 参照を保持 (GC対策)
            self._photo_ref = photo
            
            # スクロール領域を設定
            self.canvas.configure(scrollregion=(0, 0, size[0], size[1]))
            
            # コールバック
            if self._on_display_complete:
                self._on_display_complete()
                
        except Exception as e:
            print(f"⚠️ [{self.source}] display_photo error: {e}")
    
    def _display_cached(self, cache_key: str):
        """キャッシュから表示"""
        entry = self._cache[cache_key]
        self._display_photo(entry.photo, entry.size)
    
    def _add_to_cache(
        self,
        key: str,
        photo: ImageTk.PhotoImage,
        size: Tuple[int, int]
    ):
        """キャッシュに追加"""
        # サイズ制限
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            # 最古のエントリを削除
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].timestamp
            )
            del self._cache[oldest_key]
        
        self._cache[key] = CacheEntry(
            photo=photo,
            size=size,
            timestamp=time.time()
        )
    
    def _clear_cache(self):
        """キャッシュをクリア"""
        self._cache.clear()
    
    def on_configure(self, event):
        """
        キャンバスリサイズイベントハンドラ
        デバウンス付き
        """
        new_size = (event.width, event.height)
        
        # サイズ変化チェック
        if new_size == self._last_size:
            return
        
        self._last_size = new_size
        
        # 既存タイマーをキャンセル
        if self._resize_timer:
            self.canvas.after_cancel(self._resize_timer)
        
        # デバウンス
        self._resize_timer = self.canvas.after(
            self.RESIZE_DEBOUNCE_MS,
            self.redisplay
        )
    
    def set_fit_mode(self, mode: str):
        """表示モードを設定"""
        if mode in ("width", "fit", "cover"):
            self.fit_mode = mode
            self._clear_cache()
            self.redisplay()
    
    def get_image_coords(self, canvas_x: int, canvas_y: int) -> Tuple[int, int]:
        """
        キャンバス座標を画像座標に変換
        
        Args:
            canvas_x: キャンバスX座標
            canvas_y: キャンバスY座標
        
        Returns:
            (image_x, image_y)
        """
        if self.display_scale == 0:
            return (0, 0)
        
        return (
            int(canvas_x / self.display_scale),
            int(canvas_y / self.display_scale)
        )
    
    def get_canvas_coords(self, image_x: int, image_y: int) -> Tuple[int, int]:
        """
        画像座標をキャンバス座標に変換
        
        Args:
            image_x: 画像X座標
            image_y: 画像Y座標
        
        Returns:
            (canvas_x, canvas_y)
        """
        return (
            int(image_x * self.display_scale),
            int(image_y * self.display_scale)
        )
    
    def scroll_to(self, image_y: int):
        """指定の画像Y座標までスクロール"""
        if self._current_image is None:
            return
        
        try:
            img_height = self._current_image.size[1]
            if img_height > 0:
                fraction = image_y / img_height
                self.canvas.yview_moveto(fraction)
        except Exception as e:
            print(f"⚠️ [{self.source}] scroll_to error: {e}")
    
    def set_on_display_complete(self, callback: Callable):
        """表示完了コールバックを設定"""
        self._on_display_complete = callback
    
    def destroy(self):
        """クリーンアップ"""
        self._clear_cache()
        self._current_image = None
        self._photo_ref = None
