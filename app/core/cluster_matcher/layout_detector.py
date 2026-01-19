"""
LayoutPatternDetector - レイアウトパターン検出器

機能:
- 繰り返しレイアウトパターンの検出
- 相対位置関係のグルーピング
- サイズ・縦横比の類似性分析
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np


@dataclass
class LayoutFeatureVector:
    """レイアウト特徴ベクトル"""
    aspect_ratio: float      # 縦横比
    relative_x: float        # ページ内相対X位置 (0-1)
    relative_y: float        # ページ内相対Y位置 (0-1)
    relative_width: float    # ページ幅に対する比率
    relative_height: float   # ページ高さに対する比率
    text_density: float      # テキスト密度 (文字数/面積)
    
    def to_vector(self) -> np.ndarray:
        """numpy配列に変換"""
        return np.array([
            self.aspect_ratio,
            self.relative_x,
            self.relative_y,
            self.relative_width,
            self.relative_height,
            self.text_density
        ])


@dataclass
class LayoutPatternGroup:
    """類似レイアウトパターングループ"""
    pattern_id: str
    regions: List[any]  # EditableRegion リスト
    centroid: LayoutFeatureVector
    similarity_scores: List[float]


class LayoutPatternDetector:
    """
    レイアウトパターン検出器
    
    Web/PDFの両方をスキャンして、類似したレイアウトパターンを検出
    """
    
    def __init__(self, similarity_threshold: float = 0.6):
        """
        Args:
            similarity_threshold: 類似度閾値 (承認済み: 0.6)
        """
        self.similarity_threshold = similarity_threshold
        self.page_width = 1
        self.page_height = 1
    
    def set_page_dimensions(self, width: int, height: int):
        """ページサイズを設定"""
        self.page_width = max(1, width)
        self.page_height = max(1, height)
    
    def extract_layout_features(self, region) -> LayoutFeatureVector:
        """
        領域からレイアウト特徴量を抽出
        
        Args:
            region: EditableRegion または dict with 'rect' and 'text'
        """
        # rect取得
        if hasattr(region, 'rect'):
            rect = region.rect
            text = region.text if hasattr(region, 'text') else ""
        else:
            rect = region.get('rect', [0, 0, 100, 100])
            text = region.get('text', "")
        
        x1, y1, x2, y2 = rect
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        
        return LayoutFeatureVector(
            aspect_ratio=width / height if height > 0 else 1.0,
            relative_x=(x1 + x2) / 2 / self.page_width,
            relative_y=(y1 + y2) / 2 / self.page_height,
            relative_width=width / self.page_width,
            relative_height=height / self.page_height,
            text_density=len(text) / area if area > 0 else 0
        )
    
    def calculate_layout_similarity(
        self, 
        features1: LayoutFeatureVector, 
        features2: LayoutFeatureVector
    ) -> float:
        """
        2つのレイアウト特徴ベクトル間の類似度を計算
        
        Returns:
            0.0-1.0 の類似度スコア
        """
        v1 = features1.to_vector()
        v2 = features2.to_vector()
        
        # 各次元の重み (位置とサイズを重視)
        weights = np.array([
            0.15,  # aspect_ratio
            0.20,  # relative_x
            0.20,  # relative_y
            0.20,  # relative_width
            0.20,  # relative_height
            0.05   # text_density
        ])
        
        # 正規化された差分
        diff = np.abs(v1 - v2)
        
        # 重み付き類似度 (差分が小さいほど高スコア)
        weighted_diff = np.sum(diff * weights)
        similarity = max(0.0, 1.0 - weighted_diff)
        
        return similarity
    
    def detect_repeating_patterns(
        self, 
        regions: List,
        min_group_size: int = 2
    ) -> List[LayoutPatternGroup]:
        """
        繰り返しパターンを検出
        
        Args:
            regions: 領域リスト
            min_group_size: グループ最小サイズ
        
        Returns:
            類似パターングループのリスト
        """
        if not regions:
            return []
        
        # 特徴量抽出
        features = [self.extract_layout_features(r) for r in regions]
        
        # 類似度マトリクス計算
        n = len(regions)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = self.calculate_layout_similarity(features[i], features[j])
                similarity_matrix[i, j] = sim
                similarity_matrix[j, i] = sim
        
        # 貪欲クラスタリング
        groups = []
        used = set()
        
        for i in range(n):
            if i in used:
                continue
            
            # i と類似する要素を収集
            group_indices = [i]
            group_scores = [1.0]
            
            for j in range(n):
                if j != i and j not in used:
                    if similarity_matrix[i, j] >= self.similarity_threshold:
                        group_indices.append(j)
                        group_scores.append(similarity_matrix[i, j])
            
            if len(group_indices) >= min_group_size:
                # グループ確定
                for idx in group_indices:
                    used.add(idx)
                
                group_regions = [regions[idx] for idx in group_indices]
                group_features = [features[idx] for idx in group_indices]
                
                # 重心計算
                centroid = self._calculate_centroid(group_features)
                
                groups.append(LayoutPatternGroup(
                    pattern_id=f"LP-{len(groups)+1}",
                    regions=group_regions,
                    centroid=centroid,
                    similarity_scores=group_scores
                ))
        
        print(f"[LayoutDetector] {len(regions)}領域から{len(groups)}グループを検出")
        return groups
    
    def _calculate_centroid(self, features: List[LayoutFeatureVector]) -> LayoutFeatureVector:
        """特徴ベクトルの重心を計算"""
        if not features:
            return LayoutFeatureVector(1, 0, 0, 0, 0, 0)
        
        vectors = [f.to_vector() for f in features]
        centroid = np.mean(vectors, axis=0)
        
        return LayoutFeatureVector(
            aspect_ratio=centroid[0],
            relative_x=centroid[1],
            relative_y=centroid[2],
            relative_width=centroid[3],
            relative_height=centroid[4],
            text_density=centroid[5]
        )
    
    def find_matching_pattern_groups(
        self,
        web_groups: List[LayoutPatternGroup],
        pdf_groups: List[LayoutPatternGroup]
    ) -> List[Tuple[LayoutPatternGroup, LayoutPatternGroup, float]]:
        """
        Web/PDF間で対応するパターングループを発見
        
        Returns:
            (web_group, pdf_group, similarity) のリスト
        """
        matches = []
        
        for wg in web_groups:
            best_match = None
            best_score = 0.0
            
            for pg in pdf_groups:
                # 重心間の類似度
                sim = self.calculate_layout_similarity(wg.centroid, pg.centroid)
                
                if sim > best_score and sim >= self.similarity_threshold:
                    best_score = sim
                    best_match = pg
            
            if best_match:
                matches.append((wg, best_match, best_score))
        
        print(f"[LayoutDetector] {len(matches)}個のパターンマッチを発見")
        return matches
