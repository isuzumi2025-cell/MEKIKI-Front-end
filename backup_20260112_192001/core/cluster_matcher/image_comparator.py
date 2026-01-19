"""
ImageRegionComparator - 画像領域比較器

機能:
- テンプレートマッチング
- ヒストグラム比較
- 構造類似性 (SSIM)

Weight: 20% (承認済み)
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from PIL import Image
import numpy as np


@dataclass
class ImageComparisonResult:
    """画像比較結果"""
    similarity: float
    method: str
    details: dict


class ImageRegionComparator:
    """
    画像領域比較器
    
    2つの画像領域を比較し、類似度を計算
    """
    
    def __init__(self):
        self.target_size = (100, 100)  # 比較用正規化サイズ
    
    def compare_regions(
        self,
        img1: Image.Image,
        rect1: List[int],
        img2: Image.Image,
        rect2: List[int]
    ) -> float:
        """
        2つの画像領域を比較
        
        Args:
            img1: 画像1
            rect1: 領域1 [x1, y1, x2, y2]
            img2: 画像2
            rect2: 領域2 [x1, y1, x2, y2]
        
        Returns:
            0.0-1.0 の類似度スコア
        """
        try:
            # 領域を切り出し
            crop1 = self._safe_crop(img1, rect1)
            crop2 = self._safe_crop(img2, rect2)
            
            if crop1 is None or crop2 is None:
                return 0.0
            
            # サイズ正規化
            norm1 = crop1.resize(self.target_size, Image.Resampling.LANCZOS)
            norm2 = crop2.resize(self.target_size, Image.Resampling.LANCZOS)
            
            # グレースケール変換
            gray1 = norm1.convert('L')
            gray2 = norm2.convert('L')
            
            # SSIM計算
            ssim = self._calculate_ssim(gray1, gray2)
            
            return ssim
            
        except Exception as e:
            print(f"[ImageComparator] 比較エラー: {e}")
            return 0.0
    
    def _safe_crop(self, img: Image.Image, rect: List[int]) -> Optional[Image.Image]:
        """安全な画像切り出し"""
        try:
            x1, y1, x2, y2 = rect
            
            # 範囲チェック
            x1 = max(0, min(x1, img.width - 1))
            y1 = max(0, min(y1, img.height - 1))
            x2 = max(x1 + 1, min(x2, img.width))
            y2 = max(y1 + 1, min(y2, img.height))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            return img.crop((x1, y1, x2, y2))
        except:
            return None
    
    def _calculate_ssim(self, img1: Image.Image, img2: Image.Image) -> float:
        """
        構造類似性 (SSIM) を計算
        
        簡易実装: numpy のみ使用
        """
        # numpy配列に変換
        arr1 = np.array(img1, dtype=np.float64)
        arr2 = np.array(img2, dtype=np.float64)
        
        # 定数
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2
        
        # 平均
        mu1 = np.mean(arr1)
        mu2 = np.mean(arr2)
        
        # 分散
        sigma1_sq = np.var(arr1)
        sigma2_sq = np.var(arr2)
        
        # 共分散
        sigma12 = np.mean((arr1 - mu1) * (arr2 - mu2))
        
        # SSIM計算
        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2)
        
        ssim = numerator / denominator if denominator > 0 else 0.0
        
        return max(0.0, min(1.0, ssim))
    
    def calculate_histogram_similarity(
        self, 
        img1: Image.Image, 
        img2: Image.Image
    ) -> float:
        """
        ヒストグラム類似度を計算 (補助メソッド)
        """
        try:
            hist1 = img1.histogram()
            hist2 = img2.histogram()
            
            # 正規化
            total1 = sum(hist1) or 1
            total2 = sum(hist2) or 1
            
            hist1 = [h / total1 for h in hist1]
            hist2 = [h / total2 for h in hist2]
            
            # 相関係数的な類似度
            min_sum = sum(min(h1, h2) for h1, h2 in zip(hist1, hist2))
            
            return min_sum
        except:
            return 0.0
    
    def find_similar_image_regions(
        self,
        source_img: Image.Image,
        source_rect: List[int],
        target_img: Image.Image,
        target_regions: List,
        threshold: float = 0.6
    ) -> List[Tuple[any, float]]:
        """
        ソース領域に類似するターゲット領域を発見
        
        Args:
            source_img: ソース画像
            source_rect: ソース領域
            target_img: ターゲット画像
            target_regions: ターゲット領域リスト
            threshold: 類似度閾値
        
        Returns:
            (領域, 類似度) のリスト
        """
        matches = []
        
        for tr in target_regions:
            rect = tr.rect if hasattr(tr, 'rect') else tr.get('rect', [0, 0, 100, 100])
            sim = self.compare_regions(source_img, source_rect, target_img, rect)
            
            if sim >= threshold:
                matches.append((tr, sim))
        
        # 類似度でソート
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches
