"""
SDK-03: 画像フィット計算ユーティリティ
Cover/Fitモードの表示ロジック一元化
"""
from typing import Tuple
from dataclasses import dataclass


@dataclass
class FitResult:
    """フィット計算結果"""
    scale: float
    offset_x: int
    offset_y: int
    display_width: int
    display_height: int


def compute_cover(
    src_w: int, src_h: int,
    dst_w: int, dst_h: int
) -> FitResult:
    """
    Cover表示計算（余白ゼロ、クロップあり）
    画像が表示領域を完全にカバーするようスケール
    
    Args:
        src_w, src_h: ソース画像サイズ
        dst_w, dst_h: 表示領域サイズ
    
    Returns:
        FitResult: スケール、オフセット、表示サイズ
    """
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        return FitResult(1.0, 0, 0, src_w, src_h)
    
    scale_w = dst_w / src_w
    scale_h = dst_h / src_h
    scale = max(scale_w, scale_h)  # 大きい方を採用（クロップ）
    
    display_width = int(src_w * scale)
    display_height = int(src_h * scale)
    
    # センタリング
    offset_x = (display_width - dst_w) // 2
    offset_y = (display_height - dst_h) // 2
    
    return FitResult(scale, offset_x, offset_y, display_width, display_height)


def compute_fit(
    src_w: int, src_h: int,
    dst_w: int, dst_h: int
) -> FitResult:
    """
    Fit/Contain表示計算（余白あり、クロップなし）
    画像全体が表示領域に収まるようスケール
    
    Args:
        src_w, src_h: ソース画像サイズ
        dst_w, dst_h: 表示領域サイズ
    
    Returns:
        FitResult: スケール、オフセット、表示サイズ
    """
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        return FitResult(1.0, 0, 0, src_w, src_h)
    
    scale_w = dst_w / src_w
    scale_h = dst_h / src_h
    scale = min(scale_w, scale_h)  # 小さい方を採用（全体表示）
    
    display_width = int(src_w * scale)
    display_height = int(src_h * scale)
    
    # センタリング（余白計算）
    offset_x = (dst_w - display_width) // 2
    offset_y = (dst_h - display_height) // 2
    
    # Fitモードではオフセットは負にならない
    return FitResult(scale, max(0, offset_x), max(0, offset_y), display_width, display_height)


def compute_fit_for_mode(
    src_w: int, src_h: int,
    dst_w: int, dst_h: int,
    mode: str = "cover"
) -> FitResult:
    """
    モード指定でフィット計算
    
    Args:
        src_w, src_h: ソース画像サイズ
        dst_w, dst_h: 表示領域サイズ
        mode: "cover" または "fit"
    
    Returns:
        FitResult
    """
    if mode == "cover":
        return compute_cover(src_w, src_h, dst_w, dst_h)
    else:
        return compute_fit(src_w, src_h, dst_w, dst_h)
