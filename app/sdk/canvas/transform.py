"""
coord_transform.py - 座標変換SDK

画像座標（Source）とCanvas座標（View）の変換を一元化。
Cover/Fit モード、リサイズ、スクロールに対応。

使用例:
    # _display_image実行後にTransformを保存
    canvas._coord_tf = CanvasTransform(scale_x, scale_y, offset_x, offset_y)
    
    # 領域描画時
    vx, vy = canvas._coord_tf.src_to_view(region.rect[0], region.rect[1])
    
    # クリックイベント処理時
    cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
    sx, sy = canvas._coord_tf.view_to_src(cx, cy)
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class CanvasTransform:
    """
    座標変換情報を保持するデータクラス
    
    Attributes:
        scale_x: X方向のスケール（src * scale = view）
        scale_y: Y方向のスケール（src * scale = view）
        offset_x: X方向のオフセット（Cover時に負になり得る）
        offset_y: Y方向のオフセット（Cover時に負になり得る）
    """
    scale_x: float
    scale_y: float
    offset_x: int = 0
    offset_y: int = 0
    
    def src_to_view(self, sx: int, sy: int) -> Tuple[int, int]:
        """
        Source座標（元画像）→ View座標（Canvas表示）に変換
        
        Args:
            sx: Source X座標
            sy: Source Y座標
            
        Returns:
            (vx, vy): View座標のタプル
        """
        vx = int(sx * self.scale_x - self.offset_x)
        vy = int(sy * self.scale_y - self.offset_y)
        return (vx, vy)
    
    def view_to_src(self, vx: int, vy: int) -> Tuple[int, int]:
        """
        View座標（Canvas表示）→ Source座標（元画像）に変換
        
        Args:
            vx: View X座標
            vy: View Y座標
            
        Returns:
            (sx, sy): Source座標のタプル
        """
        sx = int((vx + self.offset_x) / self.scale_x) if self.scale_x != 0 else 0
        sy = int((vy + self.offset_y) / self.scale_y) if self.scale_y != 0 else 0
        return (sx, sy)
    
    def src_rect_to_view(self, x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
        """
        Source矩形 → View矩形に変換
        
        Args:
            x1, y1: 左上座標（Source）
            x2, y2: 右下座標（Source）
            
        Returns:
            (vx1, vy1, vx2, vy2): View矩形
        """
        vx1, vy1 = self.src_to_view(x1, y1)
        vx2, vy2 = self.src_to_view(x2, y2)
        return (vx1, vy1, vx2, vy2)
    
    def round_trip_error(self, sx: int, sy: int) -> Tuple[float, float]:
        """
        round-trip検証: src → view → src の誤差を計算
        
        Args:
            sx: Source X座標
            sy: Source Y座標
            
        Returns:
            (error_x, error_y): 誤差（ピクセル単位）
        """
        vx, vy = self.src_to_view(sx, sy)
        sx_back, sy_back = self.view_to_src(vx, vy)
        return (abs(sx - sx_back), abs(sy - sy_back))
    
    @classmethod
    def from_fit_mode(cls, src_w: int, src_h: int, view_w: int, view_h: int) -> "CanvasTransform":
        """
        Fitモード用のTransformを生成（全体表示、余白あり）
        
        Args:
            src_w, src_h: Source画像サイズ
            view_w, view_h: Canvas表示サイズ
            
        Returns:
            CanvasTransform インスタンス
        """
        scale_x = view_w / src_w if src_w > 0 else 1.0
        scale_y = view_h / src_h if src_h > 0 else 1.0
        scale = min(scale_x, scale_y)  # Fit: 小さい方のスケール
        return cls(scale_x=scale, scale_y=scale, offset_x=0, offset_y=0)
    
    @classmethod
    def from_cover_mode(cls, src_w: int, src_h: int, view_w: int, view_h: int) -> "CanvasTransform":
        """
        Coverモード用のTransformを生成（余白なし、はみ出しあり）
        
        Args:
            src_w, src_h: Source画像サイズ
            view_w, view_h: Canvas表示サイズ
            
        Returns:
            CanvasTransform インスタンス
        """
        scale_x = view_w / src_w if src_w > 0 else 1.0
        scale_y = view_h / src_h if src_h > 0 else 1.0
        scale = max(scale_x, scale_y)  # Cover: 大きい方のスケール
        
        # 中央配置用オフセット（はみ出し分）
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        offset_x = (new_w - view_w) // 2 if new_w > view_w else 0
        offset_y = (new_h - view_h) // 2 if new_h > view_h else 0
        
        return cls(scale_x=scale, scale_y=scale, offset_x=offset_x, offset_y=offset_y)


# ★ デフォルトTransform（未初期化時のフォールバック）
DEFAULT_TRANSFORM = CanvasTransform(scale_x=1.0, scale_y=1.0, offset_x=0, offset_y=0)


def get_canvas_transform(canvas) -> CanvasTransform:
    """
    Canvasから座標変換情報を取得（安全なゲッター）
    
    Args:
        canvas: tkinter.Canvas オブジェクト
        
    Returns:
        CanvasTransform インスタンス
    """
    return getattr(canvas, '_coord_tf', DEFAULT_TRANSFORM)
