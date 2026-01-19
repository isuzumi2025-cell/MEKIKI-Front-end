"""
AI-based Page Break Detector
長いスクリーンショット/PDFを論理的なA4ページに分割

Features:
- 空白行解析による区切り検出
- コンテンツ密度変化検出
- クラスタ間ギャップ分析
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from PIL import Image
import numpy as np


@dataclass
class PageRegion:
    """検出されたページ領域"""
    page_number: int
    y_start: int
    y_end: int
    height: int
    
    @property
    def bounds(self) -> Tuple[int, int]:
        return (self.y_start, self.y_end)


class PageBreakDetector:
    """
    AI-based page break detection
    長いスクリーンショット/PDFを論理的なページに分割
    """
    
    # A4横サイズ (96dpi基準)
    A4_LANDSCAPE_HEIGHT = 794  # px at 96dpi
    
    def __init__(
        self,
        min_page_height: int = 400,
        min_gap_for_break: int = 80,
        density_threshold: float = 0.1
    ):
        """
        Args:
            min_page_height: 最小ページ高さ (これより短いページは作らない)
            min_gap_for_break: ページ区切りと判定する最小ギャップ
            density_threshold: 空白行判定の閾値 (0-1)
        """
        self.min_page_height = min_page_height
        self.min_gap_for_break = min_gap_for_break
        self.density_threshold = density_threshold
    
    def detect_breaks(
        self,
        image: Image.Image,
        clusters: Optional[List[Dict]] = None
    ) -> List[PageRegion]:
        """
        画像とクラスタ情報からページ区切りを検出
        
        Args:
            image: 対象画像
            clusters: OCRクラスタ情報 (optional, あればより正確)
        
        Returns:
            List[PageRegion]: 検出されたページ領域のリスト
        """
        height = image.height
        
        # クラスタ情報がある場合はクラスタ間ギャップで分析
        if clusters:
            breaks = self._detect_from_clusters(clusters, height)
        else:
            # 画像の空白行解析
            breaks = self._detect_from_image(image)
        
        # ページ領域を生成
        pages = self._create_page_regions(breaks, height)
        
        return pages
    
    def _detect_from_clusters(
        self,
        clusters: List[Dict],
        total_height: int
    ) -> List[int]:
        """
        クラスタ間ギャップからページ区切りを検出
        """
        if not clusters:
            return []
        
        # クラスタをY座標でソート
        sorted_clusters = sorted(clusters, key=lambda c: c['rect'][1])
        
        breaks = []
        
        for i in range(len(sorted_clusters) - 1):
            current = sorted_clusters[i]
            next_cluster = sorted_clusters[i + 1]
            
            # 現在のクラスタの下端
            current_bottom = current['rect'][3]
            # 次のクラスタの上端
            next_top = next_cluster['rect'][1]
            
            # ギャップ計算
            gap = next_top - current_bottom
            
            # 大きなギャップがあればページ区切り候補
            if gap >= self.min_gap_for_break:
                # 区切り位置はギャップの中央
                break_y = current_bottom + gap // 2
                
                # 最小ページ高さチェック
                if not breaks or (break_y - breaks[-1]) >= self.min_page_height:
                    breaks.append(break_y)
        
        return breaks
    
    def _detect_from_image(self, image: Image.Image) -> List[int]:
        """
        画像の空白行解析でページ区切りを検出
        """
        # グレースケール変換
        gray = image.convert('L')
        pixels = np.array(gray)
        
        height, width = pixels.shape
        
        # 各行のコンテンツ密度を計算 (非白ピクセルの割合)
        # 白は255に近い値
        row_density = np.mean(pixels < 240, axis=1)
        
        # 空白行（密度が低い行）の連続区間を検出
        breaks = []
        in_gap = False
        gap_start = 0
        
        for y in range(height):
            is_empty = row_density[y] < self.density_threshold
            
            if is_empty and not in_gap:
                # ギャップ開始
                in_gap = True
                gap_start = y
            elif not is_empty and in_gap:
                # ギャップ終了
                gap_length = y - gap_start
                
                if gap_length >= self.min_gap_for_break:
                    # 区切り位置はギャップの中央
                    break_y = gap_start + gap_length // 2
                    
                    # 最小ページ高さチェック
                    if not breaks or (break_y - breaks[-1]) >= self.min_page_height:
                        breaks.append(break_y)
                
                in_gap = False
        
        return breaks
    
    def _create_page_regions(
        self,
        breaks: List[int],
        total_height: int
    ) -> List[PageRegion]:
        """
        区切り位置からページ領域を生成
        """
        pages = []
        
        # 区切りがない場合は全体を1ページとして扱う
        if not breaks:
            # 長い画像はA4サイズで自動分割
            if total_height > self.A4_LANDSCAPE_HEIGHT * 1.5:
                # A4サイズで均等分割
                num_pages = max(1, round(total_height / self.A4_LANDSCAPE_HEIGHT))
                page_height = total_height // num_pages
                
                for i in range(num_pages):
                    y_start = i * page_height
                    y_end = min((i + 1) * page_height, total_height)
                    pages.append(PageRegion(
                        page_number=i + 1,
                        y_start=y_start,
                        y_end=y_end,
                        height=y_end - y_start
                    ))
            else:
                pages.append(PageRegion(
                    page_number=1,
                    y_start=0,
                    y_end=total_height,
                    height=total_height
                ))
            return pages
        
        # 区切りからページを生成
        prev_y = 0
        for i, break_y in enumerate(breaks):
            pages.append(PageRegion(
                page_number=i + 1,
                y_start=prev_y,
                y_end=break_y,
                height=break_y - prev_y
            ))
            prev_y = break_y
        
        # 最後のページ
        if prev_y < total_height:
            pages.append(PageRegion(
                page_number=len(breaks) + 1,
                y_start=prev_y,
                y_end=total_height,
                height=total_height - prev_y
            ))
        
        return pages
    
    def split_image_by_pages(
        self,
        image: Image.Image,
        pages: List[PageRegion]
    ) -> List[Image.Image]:
        """
        ページ領域で画像を分割
        
        Returns:
            List[Image.Image]: ページごとの画像リスト
        """
        page_images = []
        
        for page in pages:
            cropped = image.crop((0, page.y_start, image.width, page.y_end))
            page_images.append(cropped)
        
        return page_images


# テスト用
if __name__ == "__main__":
    detector = PageBreakDetector()
    
    # テスト用クラスタ
    test_clusters = [
        {"rect": [0, 0, 100, 50], "text": "Header"},
        {"rect": [0, 60, 100, 200], "text": "Content 1"},
        {"rect": [0, 350, 100, 500], "text": "Content 2"},  # 大きなギャップ
        {"rect": [0, 510, 100, 700], "text": "Content 3"},
    ]
    
    # ダミー画像
    dummy_img = Image.new('RGB', (800, 1000), 'white')
    
    pages = detector.detect_breaks(dummy_img, test_clusters)
    for p in pages:
        print(f"Page {p.page_number}: y={p.y_start}-{p.y_end} (height={p.height})")
