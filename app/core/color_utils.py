"""
色比較ユーティリティ - CIE LAB 色空間による知覚的色比較

テキスト前景色の抽出（Otsu閾値法）と
Delta-E (CIE76) による色差計算を提供する。
"""

import math
import numpy as np
from typing import Tuple, Optional


# ---------------------------------------------------------------------------
# RGB / LAB 変換
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """#RRGGBB → (R, G, B)"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (128, 128, 128)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    RGB → CIE LAB 変換
    sRGB (D65照明) を使用
    """
    r, g, b = [x / 255.0 for x in rgb]

    # リニア化（逆ガンマ補正）
    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = linearize(r)
    g_lin = linearize(g)
    b_lin = linearize(b)

    # XYZ (D65 基準白: X=0.95047, Y=1.00000, Z=1.08883)
    x = r_lin * 0.4124564 + g_lin * 0.3575761 + b_lin * 0.1804375
    y = r_lin * 0.2126729 + g_lin * 0.7151522 + b_lin * 0.0721750
    z = r_lin * 0.0193339 + g_lin * 0.1191920 + b_lin * 0.9503041

    x /= 0.95047
    y /= 1.00000
    z /= 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)

    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b_val = 200.0 * (fy - fz)
    return (L, a, b_val)


# ---------------------------------------------------------------------------
# Delta-E 計算
# ---------------------------------------------------------------------------

def delta_e_cie76(hex1: str, hex2: str) -> float:
    """
    2色間の知覚的色差を CIE76 Delta-E で計算する。

    目安:
      < 1  : 知覚不能
      < 5  : 実質同一色
      < 15 : 類似色
      >= 30: 明確に異なる色
    """
    lab1 = rgb_to_lab(hex_to_rgb(hex1))
    lab2 = rgb_to_lab(hex_to_rgb(hex2))
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def colors_are_same(hex1: str, hex2: str) -> bool:
    """Delta-E < 5 → 同一色"""
    return delta_e_cie76(hex1, hex2) < 5.0


def colors_are_similar(hex1: str, hex2: str) -> bool:
    """Delta-E < 15 → 類似色（同一カードと見なせる）"""
    return delta_e_cie76(hex1, hex2) < 15.0


def colors_are_different(hex1: str, hex2: str) -> bool:
    """Delta-E >= 30 → 明確に異なる色（カード境界候補）"""
    return delta_e_cie76(hex1, hex2) >= 30.0


# ---------------------------------------------------------------------------
# テキスト前景色の抽出（Otsu 閾値法）
# ---------------------------------------------------------------------------

def extract_text_foreground_color(
    cv_image: "np.ndarray",
    rect,
    padding: int = 2
) -> str:
    """
    OpenCV BGR 画像から rect=[x0,y0,x1,y1] 領域のテキスト前景色を抽出する。

    1. 領域をクロップ
    2. グレースケール → Otsu 閾値で前景マスクを作成
    3. 前景ピクセルの平均 BGR を #RRGGBB に変換して返す

    Args:
        cv_image: BGR OpenCV 画像 (numpy ndarray)
        rect: [x0, y0, x1, y1]（整数）
        padding: クロップ時のパディング (px)

    Returns:
        "#RRGGBB" 形式の色文字列。失敗時は "#000000"
    """
    try:
        import cv2

        x0, y0, x1, y1 = [int(v) for v in rect]
        h_img, w_img = cv_image.shape[:2]

        # パディング付きクロップ（境界チェック）
        x0c = max(0, x0 - padding)
        y0c = max(0, y0 - padding)
        x1c = min(w_img, x1 + padding)
        y1c = min(h_img, y1 + padding)

        roi = cv_image[y0c:y1c, x0c:x1c]
        if roi.size == 0:
            return "#000000"

        # グレースケール変換
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Otsu 閾値で前景（テキスト）マスク
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 前景ピクセルが少なすぎる場合はフォールバック
        fg_count = int(thresh.sum() / 255)
        if fg_count < 5:
            return "#000000"

        # 前景ピクセルの平均 BGR
        mask_bool = thresh > 0
        fg_pixels = roi[mask_bool]  # shape: (N, 3)
        avg_bgr = fg_pixels.mean(axis=0)

        b, g, r = int(avg_bgr[0]), int(avg_bgr[1]), int(avg_bgr[2])
        return f"#{r:02X}{g:02X}{b:02X}"

    except Exception:
        return "#000000"
