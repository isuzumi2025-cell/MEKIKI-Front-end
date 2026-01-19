"""
視覚要素解析エンジン
OpenCVを使用した罫線・背景色・装飾検出

Created: 2026-01-11
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from PIL import Image
from collections import Counter


class VisualAnalyzer:
    """
    画像から視覚的要素を検出するクラス
    - 罫線（水平・垂直）
    - 背景色ブロック
    - テキスト装飾（太字、色付き）
    """
    
    def __init__(self):
        self.min_line_length = 50  # 最小罫線長
        self.color_block_min_area = 1000  # 最小カラーブロック面積
    
    def analyze_image(self, image: Image.Image) -> Dict:
        """
        画像を総合解析
        
        Args:
            image: PIL Image
            
        Returns:
            {
                "borders": [...],       # 罫線リスト
                "color_blocks": [...],  # 背景色ブロック
                "dominant_colors": [...] # 主要色
            }
        """
        # PIL -> OpenCV変換
        cv_image = self._pil_to_cv(image)
        
        # 各検出を実行
        borders = self.detect_borders(cv_image)
        color_blocks = self.detect_color_blocks(cv_image)
        dominant_colors = self.get_dominant_colors(cv_image, n=5)
        
        return {
            "borders": borders,
            "color_blocks": color_blocks,
            "dominant_colors": dominant_colors
        }
    
    def _pil_to_cv(self, pil_image: Image.Image) -> np.ndarray:
        """PIL Image -> OpenCV format"""
        if pil_image.mode == 'RGBA':
            pil_image = pil_image.convert('RGB')
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    def detect_borders(self, image: np.ndarray) -> List[Dict]:
        """
        罫線（水平・垂直線）を検出
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            [{"type": "horizontal"|"vertical", "start": (x,y), "end": (x,y), "length": int}, ...]
        """
        borders = []
        
        # グレースケール変換
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # エッジ検出
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Hough変換で直線検出
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi/180,
            threshold=100,
            minLineLength=self.min_line_length,
            maxLineGap=10
        )
        
        if lines is None:
            return borders
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            
            # 水平/垂直判定（±5度の許容）
            angle = np.abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
            
            if angle < 5 or angle > 175:
                line_type = "horizontal"
            elif 85 < angle < 95:
                line_type = "vertical"
            else:
                continue  # 斜め線は無視
            
            borders.append({
                "type": line_type,
                "start": (int(x1), int(y1)),
                "end": (int(x2), int(y2)),
                "length": int(length)
            })
        
        # 重複を除去（近接線をマージ）
        borders = self._merge_nearby_lines(borders)
        
        return borders
    
    def _merge_nearby_lines(self, lines: List[Dict], threshold: int = 10) -> List[Dict]:
        """近接する線をマージ"""
        if not lines:
            return lines
        
        merged = []
        used = set()
        
        for i, line1 in enumerate(lines):
            if i in used:
                continue
            
            # 同じタイプの近接線を探す
            group = [line1]
            for j, line2 in enumerate(lines[i+1:], start=i+1):
                if j in used:
                    continue
                if line1["type"] != line2["type"]:
                    continue
                
                # 距離計算
                if line1["type"] == "horizontal":
                    dist = abs(line1["start"][1] - line2["start"][1])
                else:
                    dist = abs(line1["start"][0] - line2["start"][0])
                
                if dist < threshold:
                    group.append(line2)
                    used.add(j)
            
            # グループをマージ
            if group:
                all_x = [l["start"][0] for l in group] + [l["end"][0] for l in group]
                all_y = [l["start"][1] for l in group] + [l["end"][1] for l in group]
                
                merged.append({
                    "type": line1["type"],
                    "start": (min(all_x), min(all_y)),
                    "end": (max(all_x), max(all_y)),
                    "length": max(l["length"] for l in group)
                })
        
        return merged
    
    def detect_color_blocks(self, image: np.ndarray) -> List[Dict]:
        """
        背景色ブロックを検出
        
        Args:
            image: OpenCV image (BGR)
            
        Returns:
            [{"rect": [x,y,w,h], "color": "#RRGGBB", "area": int}, ...]
        """
        blocks = []
        
        # HSV変換
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 彩度でマスク（背景色は通常低彩度 or 高彩度の均一領域）
        # ここでは輪郭ベースで検出
        
        # グレースケール + 二値化
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 適応的二値化
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11, 2
        )
        
        # 膨張・収縮でノイズ除去
        kernel = np.ones((5, 5), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        
        # 輪郭検出
        contours, _ = cv2.findContours(
            cleaned,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.color_block_min_area:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            
            # 領域内の平均色を取得
            roi = image[y:y+h, x:x+w]
            avg_color = roi.mean(axis=(0, 1))
            hex_color = self._bgr_to_hex(avg_color)
            
            blocks.append({
                "rect": [int(x), int(y), int(w), int(h)],
                "color": hex_color,
                "area": int(area)
            })
        
        # 面積でソート（大きい順）
        blocks.sort(key=lambda b: b["area"], reverse=True)
        
        return blocks[:20]  # 上位20件
    
    def get_dominant_colors(self, image: np.ndarray, n: int = 5) -> List[Dict]:
        """
        画像の主要色を取得
        
        Args:
            image: OpenCV image (BGR)
            n: 取得する色の数
            
        Returns:
            [{"color": "#RRGGBB", "percentage": float}, ...]
        """
        # リサイズして処理高速化
        small = cv2.resize(image, (100, 100))
        
        # ピクセルを1次元配列に
        pixels = small.reshape(-1, 3)
        
        # 色を量子化（16段階に）
        pixels = (pixels // 16) * 16
        
        # 色をカウント
        color_counts = Counter(tuple(p) for p in pixels)
        
        # 上位n色を取得
        total_pixels = len(pixels)
        dominant = []
        
        for color, count in color_counts.most_common(n):
            hex_color = self._bgr_to_hex(color)
            percentage = count / total_pixels
            dominant.append({
                "color": hex_color,
                "percentage": round(percentage, 3)
            })
        
        return dominant
    
    def _bgr_to_hex(self, bgr: Tuple) -> str:
        """BGR色をHEXに変換"""
        b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
        return f"#{r:02X}{g:02X}{b:02X}"
    
    def analyze_text_region(
        self,
        image: np.ndarray,
        rect: List[int]
    ) -> Dict:
        """
        テキスト領域の視覚特性を分析
        
        Args:
            image: OpenCV image
            rect: [x0, y0, x1, y1]
            
        Returns:
            {
                "background_color": "#RRGGBB",
                "has_border": bool,
                "border_sides": ["top", "left", ...],
                "is_highlighted": bool
            }
        """
        x0, y0, x1, y1 = rect
        roi = image[y0:y1, x0:x1]
        
        if roi.size == 0:
            return {
                "background_color": "#FFFFFF",
                "has_border": False,
                "border_sides": [],
                "is_highlighted": False
            }
        
        # 背景色（エッジを除いた中央部分）
        h, w = roi.shape[:2]
        margin = max(5, min(h, w) // 10)
        center = roi[margin:h-margin, margin:w-margin] if h > margin*2 and w > margin*2 else roi
        bg_color = self._bgr_to_hex(center.mean(axis=(0, 1)))
        
        # 罫線検出（各辺をチェック）
        border_sides = []
        edge_width = 3
        
        # 上辺
        top_edge = roi[:edge_width, :].mean()
        if top_edge < 100:  # 暗い（線がある）
            border_sides.append("top")
        
        # 下辺
        bottom_edge = roi[-edge_width:, :].mean()
        if bottom_edge < 100:
            border_sides.append("bottom")
        
        # 左辺
        left_edge = roi[:, :edge_width].mean()
        if left_edge < 100:
            border_sides.append("left")
        
        # 右辺
        right_edge = roi[:, -edge_width:].mean()
        if right_edge < 100:
            border_sides.append("right")
        
        # ハイライト判定（背景が白以外）
        is_highlighted = not self._is_near_white(bg_color)
        
        return {
            "background_color": bg_color,
            "has_border": len(border_sides) > 0,
            "border_sides": border_sides,
            "is_highlighted": is_highlighted
        }
    
    def _is_near_white(self, hex_color: str, threshold: int = 230) -> bool:
        """白に近いかチェック"""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return r > threshold and g > threshold and b > threshold


def enhance_blocks_with_visual_info(
    blocks: List[Dict],
    image: Image.Image
) -> List[Dict]:
    """
    BlockExtractorの出力にVisualAnalyzerの情報を追加
    
    Args:
        blocks: [{text, rect, ...}, ...]
        image: PIL Image
        
    Returns:
        拡張されたblocks
    """
    analyzer = VisualAnalyzer()
    cv_image = analyzer._pil_to_cv(image)
    
    enhanced = []
    for block in blocks:
        rect = block.get("rect", [0, 0, 100, 100])
        visual_info = analyzer.analyze_text_region(cv_image, rect)
        
        enhanced_block = block.copy()
        enhanced_block.update({
            "background_color": visual_info["background_color"],
            "has_border": visual_info["has_border"],
            "border_sides": visual_info["border_sides"],
            "is_highlighted": visual_info["is_highlighted"]
        })
        enhanced.append(enhanced_block)
    
    return enhanced
