"""
canvas_operations.py - Canvas操作SDK

スクロール、ページナビゲーション、選択操作を一元管理。
全ての操作はこのSDK経由でCanvasを制御する。

使用例:
    from app.gui.sdk.canvas_operations import CanvasController
    
    controller = CanvasController(canvas, image, transform)
    controller.scroll_to_region(y_start, y_end)
    controller.enable_drag_selection(on_select_callback)
"""

import tkinter as tk
from typing import Callable, Optional, Tuple, List
from dataclasses import dataclass, field
from PIL import Image, ImageTk


@dataclass
class PageInfo:
    """ページ情報"""
    index: int
    total: int
    image: Optional[Image.Image] = None
    label: str = ""


@dataclass  
class CanvasState:
    """Canvas状態管理"""
    image: Optional[Image.Image] = None
    photo: Optional[ImageTk.PhotoImage] = None
    scale: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    selection_start: Optional[Tuple[int, int]] = None
    selection_rect_id: Optional[int] = None


class CanvasController:
    """
    Canvas操作を一元管理するコントローラ
    
    責務:
    - スクロール制御（マウスホイール、プログラム呼び出し）
    - ページナビゲーション
    - ドラッグ選択
    - 座標変換（coord_transform経由）
    """
    
    def __init__(self, canvas: tk.Canvas, source_type: str = "web"):
        """
        Args:
            canvas: tkinter.Canvas
            source_type: "web" または "pdf"
        """
        self.canvas = canvas
        self.source_type = source_type
        self.state = CanvasState()
        self._callbacks = {}
        
        # イベントをバインド
        self._bind_events()
    
    def _bind_events(self):
        """標準イベントをバインド"""
        # マウスホイールスクロール
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        
        # ドラッグ選択
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        
        print(f"[CanvasController] Events bound for {self.source_type}")
    
    # === スクロール制御 ===
    
    def _on_mousewheel(self, event):
        """マウスホイールでY方向スクロール"""
        # scrollregionが設定されているか確認
        scrollregion = self.canvas.cget('scrollregion')
        if not scrollregion:
            print(f"[CanvasController] No scrollregion set")
            return
        
        delta = int(-1 * (event.delta / 120))
        self.canvas.yview_scroll(delta, "units")
    
    def _on_shift_mousewheel(self, event):
        """Shift+マウスホイールでX方向スクロール"""
        delta = int(-1 * (event.delta / 120))
        self.canvas.xview_scroll(delta, "units")
    
    def scroll_to_position(self, y_fraction: float):
        """指定位置にスクロール（0.0〜1.0）"""
        self.canvas.yview_moveto(max(0, min(1, y_fraction)))
    
    def scroll_to_region(self, y_start: int, y_end: int, src_height: int):
        """指定領域が見えるようにスクロール（Source座標）"""
        if src_height <= 0:
            return
        
        center_y = (y_start + y_end) / 2
        fraction = max(0, min(1, center_y / src_height))
        self.canvas.yview_moveto(fraction)
    
    def get_scroll_position(self) -> Tuple[float, float]:
        """現在のスクロール位置を取得"""
        return (self.canvas.xview()[0], self.canvas.yview()[0])
    
    # === 画像表示 ===
    
    def display_image(self, image: Image.Image, mode: str = "fit"):
        """
        画像を表示
        
        Args:
            image: PIL Image
            mode: "fit" または "cover"
        """
        self.state.image = image
        
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        if canvas_w <= 1 or canvas_h <= 1:
            # キャンバスサイズ未確定時は後で再試行
            self.canvas.after(100, lambda: self.display_image(image, mode))
            return
        
        src_w, src_h = image.size
        
        # スケール計算
        scale_x = canvas_w / src_w
        scale_y = canvas_h / src_h
        
        if mode == "cover":
            self.state.scale = max(scale_x, scale_y)
        else:  # fit
            self.state.scale = min(scale_x, scale_y)
        
        new_w = int(src_w * self.state.scale)
        new_h = int(src_h * self.state.scale)
        
        # リサイズ
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.state.photo = ImageTk.PhotoImage(resized)
        
        # 描画
        self.canvas.delete("image")
        self.canvas.create_image(0, 0, anchor="nw", image=self.state.photo, tags="image")
        self.canvas.tag_lower("image")
        
        # scrollregionを画像サイズに設定（スクロール可能に）
        self.canvas.configure(scrollregion=(0, 0, new_w, new_h))
        self.canvas.yview_moveto(0)
        self.canvas.xview_moveto(0)
        
        # 参照保持
        self.canvas.image = self.state.photo
        
        print(f"[CanvasController] Image displayed: {new_w}x{new_h}, scale={self.state.scale:.3f}")
    
    # === ドラッグ選択 ===
    
    def _on_press(self, event):
        """選択開始"""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.state.selection_start = (x, y)
        
        # 既存の選択矩形を削除
        if self.state.selection_rect_id:
            self.canvas.delete(self.state.selection_rect_id)
            self.state.selection_rect_id = None
    
    def _on_drag(self, event):
        """選択範囲描画"""
        if not self.state.selection_start:
            return
        
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        x1, y1 = self.state.selection_start
        
        # 既存の矩形を削除して再描画
        if self.state.selection_rect_id:
            self.canvas.delete(self.state.selection_rect_id)
        
        self.state.selection_rect_id = self.canvas.create_rectangle(
            x1, y1, x, y,
            outline="#00FF00", width=2, dash=(4, 2),
            tags="selection_rect"
        )
    
    def _on_release(self, event):
        """選択完了"""
        if not self.state.selection_start:
            return
        
        x2 = self.canvas.canvasx(event.x)
        y2 = self.canvas.canvasy(event.y)
        x1, y1 = self.state.selection_start
        
        # 正規化
        rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        
        # 最小サイズチェック
        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            self.state.selection_start = None
            return
        
        # 選択完了を通知
        if self.state.selection_rect_id:
            self.canvas.itemconfig(self.state.selection_rect_id, outline="#4CAF50", dash=())
        
        # コールバック呼び出し
        if "on_select" in self._callbacks:
            self._callbacks["on_select"](rect, self.source_type)
        
        self.state.selection_start = None
    
    def on_select(self, callback: Callable[[Tuple[int,int,int,int], str], None]):
        """選択完了時のコールバックを設定"""
        self._callbacks["on_select"] = callback
    
    # === 座標変換 ===
    
    def view_to_src(self, vx: int, vy: int) -> Tuple[int, int]:
        """View座標→Source座標"""
        if self.state.scale == 0:
            return (0, 0)
        sx = int((vx + self.state.offset_x) / self.state.scale)
        sy = int((vy + self.state.offset_y) / self.state.scale)
        return (sx, sy)
    
    def src_to_view(self, sx: int, sy: int) -> Tuple[int, int]:
        """Source座標→View座標"""
        vx = int(sx * self.state.scale - self.state.offset_x)
        vy = int(sy * self.state.scale - self.state.offset_y)
        return (vx, vy)


class PageNavigator:
    """
    ページナビゲーション管理
    
    Web/PDFのページ切替を一元管理
    """
    
    def __init__(self):
        self.current_index = 0
        self.pages: List[dict] = []
        self.on_change: Optional[Callable[[int, dict], None]] = None
    
    def set_pages(self, pages: List[dict]):
        """ページリストを設定"""
        self.pages = pages
        self.current_index = 0
        print(f"[PageNavigator] {len(pages)} pages loaded")
    
    def prev(self):
        """前ページ"""
        if self.current_index > 0:
            self.current_index -= 1
            self._notify()
    
    def next(self):
        """次ページ"""
        if self.current_index < len(self.pages) - 1:
            self.current_index += 1
            self._notify()
    
    def goto(self, index: int):
        """指定ページへ移動"""
        if 0 <= index < len(self.pages):
            self.current_index = index
            self._notify()
    
    def _notify(self):
        """ページ変更を通知"""
        if self.on_change and self.pages:
            page = self.pages[self.current_index]
            self.on_change(self.current_index, page)
    
    def get_current(self) -> Optional[dict]:
        """現在のページを取得"""
        if 0 <= self.current_index < len(self.pages):
            return self.pages[self.current_index]
        return None
    
    def get_label(self) -> str:
        """ページラベルを取得"""
        return f"{self.current_index + 1}/{len(self.pages)}" if self.pages else "0/0"
