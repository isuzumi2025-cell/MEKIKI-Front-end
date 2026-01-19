"""
空間比率によるパラグラフクラスタリングモジュール

- 文字ウエイト対行間比率によるクラスター認識
- テンプレートマッチングによる繰り返しレイアウト検出
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from PIL import Image


@dataclass
class TextBlock:
    """テキストブロック情報"""
    rect: Tuple[int, int, int, int]  # x1, y1, x2, y2
    text: str
    font_height: float  # 推定フォント高さ (ピクセル)
    cluster_id: Optional[int] = None


@dataclass
class LayoutBlock:
    """レイアウトブロック (繰り返しパターン検出用)"""
    rect: Tuple[int, int, int, int]
    template_id: int  # 同じテンプレートのブロックは同じID
    confidence: float


class SpatialClusterAnalyzer:
    """
    空間比率によるパラグラフクラスタリング
    
    既存のOCRロジックへの追加として機能
    """
    
    def __init__(self, 
                 line_spacing_ratio_threshold: float = 1.5,
                 horizontal_gap_ratio_threshold: float = 3.0,
                 template_match_threshold: float = 0.7):
        """
        Args:
            line_spacing_ratio_threshold: 行間/フォント高さ比率の閾値
                                          これ以下なら同一パラグラフ
            horizontal_gap_ratio_threshold: 水平間隔/フォント高さ比率の閾値
            template_match_threshold: テンプレートマッチングの類似度閾値
        """
        self.line_spacing_ratio = line_spacing_ratio_threshold
        self.horizontal_gap_ratio = horizontal_gap_ratio_threshold
        self.template_threshold = template_match_threshold
    
    def estimate_font_height(self, text_blocks: List[Dict]) -> List[TextBlock]:
        """
        OCR結果からフォント高さを推定
        
        Args:
            text_blocks: OCR結果のテキストブロックリスト
                         各ブロックは {'text': str, 'rect': [x1,y1,x2,y2]} を持つ
        
        Returns:
            TextBlockリスト (フォント高さ推定付き)
        """
        result = []
        for block in text_blocks:
            rect = tuple(block.get('rect', [0, 0, 0, 0]))
            text = block.get('text', '')
            
            # フォント高さを矩形高さから推定 (改行数で除算)
            x1, y1, x2, y2 = rect
            height = y2 - y1
            lines = max(1, text.count('\n') + 1)
            font_height = height / lines
            
            result.append(TextBlock(
                rect=rect,
                text=text,
                font_height=font_height
            ))
        
        return result
    
    def cluster_by_spatial_ratio(self, text_blocks: List[TextBlock]) -> List[List[TextBlock]]:
        """
        空間比率でテキストブロックをクラスタリング
        
        アルゴリズム:
        1. ブロックをY座標でソート
        2. 隣接ブロック間の垂直距離を計算
        3. 距離/フォント高さ比率が閾値以下なら同一クラスター
        
        Returns:
            クラスターされたブロックのリスト
        """
        if not text_blocks:
            return []
        
        # Y座標でソート
        sorted_blocks = sorted(text_blocks, key=lambda b: b.rect[1])
        
        clusters = []
        current_cluster = [sorted_blocks[0]]
        
        for i in range(1, len(sorted_blocks)):
            prev = current_cluster[-1]
            curr = sorted_blocks[i]
            
            # 垂直距離を計算 (現在のブロックの上端 - 前のブロックの下端)
            vertical_gap = curr.rect[1] - prev.rect[3]
            
            # 平均フォント高さ
            avg_font_height = (prev.font_height + curr.font_height) / 2
            
            # 比率を計算
            if avg_font_height > 0:
                ratio = vertical_gap / avg_font_height
            else:
                ratio = float('inf')
            
            # 水平方向の重なりも確認
            x_overlap = self._calculate_x_overlap(prev.rect, curr.rect)
            
            # 同一クラスターの条件:
            # 1. 垂直距離/フォント高さ比率が閾値以下
            # 2. 水平方向に50%以上重なっている
            if ratio <= self.line_spacing_ratio and x_overlap > 0.5:
                current_cluster.append(curr)
            else:
                clusters.append(current_cluster)
                current_cluster = [curr]
        
        # 最後のクラスター
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    def _calculate_x_overlap(self, rect1: Tuple, rect2: Tuple) -> float:
        """水平方向の重なり率を計算 (0.0-1.0)"""
        x1_start, _, x1_end, _ = rect1
        x2_start, _, x2_end, _ = rect2
        
        overlap_start = max(x1_start, x2_start)
        overlap_end = min(x1_end, x2_end)
        
        if overlap_end <= overlap_start:
            return 0.0
        
        overlap_width = overlap_end - overlap_start
        min_width = min(x1_end - x1_start, x2_end - x2_start)
        
        if min_width <= 0:
            return 0.0
        
        return overlap_width / min_width
    
    def detect_repeating_layouts(self, image: Image.Image, min_block_size: int = 50) -> List[LayoutBlock]:
        """
        テンプレートマッチングで繰り返しレイアウトパターンを検出 (高精度版)
        
        アルゴリズム:
        1. 適応的閾値処理とモルフォロジー変換で構造抽出
        2. 階層的輪郭検出で候補ブロック抽出
        3. 複数メトリクスで類似度判定 (SSIM + ヒストグラム + アスペクト比)
        4. 繰り返しパターンとして返す
        
        Args:
            image: PIL Image
            min_block_size: 最小ブロックサイズ (ピクセル)
        
        Returns:
            検出されたレイアウトブロックのリスト
        """
        # PIL Image -> OpenCV形式
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # ガウシアンブラーでノイズ除去
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 適応的閾値処理 (背景分離の改善)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 21, 5)
        
        # モルフォロジー変換で構造を強調
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        # 輪郭検出 (階層的)
        contours, hierarchy = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # 候補ブロック抽出 (アスペクト比とサイズフィルタリング)
        candidates = []
        img_area = gray.shape[0] * gray.shape[1]
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            aspect_ratio = w / h if h > 0 else 0
            
            # フィルタリング条件
            if (w >= min_block_size and h >= min_block_size and
                area < img_area * 0.5 and  # 画像の50%未満
                area > img_area * 0.001 and  # 画像の0.1%以上
                0.2 < aspect_ratio < 5.0):  # 極端なアスペクト比を除外
                candidates.append({
                    'rect': (x, y, x + w, y + h),
                    'aspect_ratio': aspect_ratio,
                    'area': area
                })
        
        if len(candidates) < 2:
            return []
        
        # サイズでグループ化 (類似サイズのブロック群)
        size_groups = self._group_by_size(candidates)
        
        layout_blocks = []
        template_id = 0
        
        for group in size_groups:
            if len(group) < 2:
                continue
            
            # グループ内で類似度比較
            similar_pairs = []
            for i, cand1 in enumerate(group):
                for j, cand2 in enumerate(group):
                    if i >= j:
                        continue
                    
                    similarity = self._calculate_block_similarity(gray, cand1['rect'], cand2['rect'])
                    if similarity >= self.template_threshold:
                        similar_pairs.append((i, j, similarity))
            
            # 類似ブロックをグループ化
            if similar_pairs:
                matched_indices = set()
                for i, j, sim in similar_pairs:
                    matched_indices.add(i)
                    matched_indices.add(j)
                
                for idx in matched_indices:
                    cand = group[idx]
                    avg_sim = sum(s for i, j, s in similar_pairs if i == idx or j == idx) / max(1, sum(1 for i, j, s in similar_pairs if i == idx or j == idx))
                    layout_blocks.append(LayoutBlock(
                        rect=cand['rect'],
                        template_id=template_id,
                        confidence=avg_sim
                    ))
                
                if matched_indices:
                    template_id += 1
        
        return layout_blocks
    
    def _group_by_size(self, candidates: List[Dict], tolerance: float = 0.3) -> List[List[Dict]]:
        """サイズが類似するブロックをグループ化"""
        if not candidates:
            return []
        
        # 面積でソート
        sorted_cands = sorted(candidates, key=lambda c: c['area'])
        groups = []
        current_group = [sorted_cands[0]]
        
        for cand in sorted_cands[1:]:
            base_area = current_group[0]['area']
            if abs(cand['area'] - base_area) / base_area <= tolerance:
                # アスペクト比も近いか確認
                base_aspect = current_group[0]['aspect_ratio']
                if abs(cand['aspect_ratio'] - base_aspect) / max(base_aspect, 0.1) <= tolerance:
                    current_group.append(cand)
                    continue
            
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [cand]
        
        if len(current_group) >= 2:
            groups.append(current_group)
        
        return groups
    
    def _calculate_block_similarity(self, gray_image, rect1: Tuple, rect2: Tuple) -> float:
        """ブロック間の類似度を計算 (複合スコア)"""
        x1_1, y1_1, x2_1, y2_1 = rect1
        x1_2, y1_2, x2_2, y2_2 = rect2
        
        block1 = gray_image[y1_1:y2_1, x1_1:x2_1]
        block2 = gray_image[y1_2:y2_2, x1_2:x2_2]
        
        if block1.size == 0 or block2.size == 0:
            return 0.0
        
        try:
            # 同じサイズにリサイズ
            target_size = (max(block1.shape[1], block2.shape[1]), max(block1.shape[0], block2.shape[0]))
            block1_resized = cv2.resize(block1, target_size)
            block2_resized = cv2.resize(block2, target_size)
            
            # 1. SSIM (Structural Similarity)
            ssim_score = self._compute_ssim(block1_resized, block2_resized)
            
            # 2. ヒストグラム相関
            hist1 = cv2.calcHist([block1_resized], [0], None, [64], [0, 256])
            hist2 = cv2.calcHist([block2_resized], [0], None, [64], [0, 256])
            cv2.normalize(hist1, hist1)
            cv2.normalize(hist2, hist2)
            hist_score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            
            # 3. エッジパターン類似度
            edge1 = cv2.Canny(block1_resized, 50, 150)
            edge2 = cv2.Canny(block2_resized, 50, 150)
            edge_hist1 = cv2.calcHist([edge1], [0], None, [32], [0, 256])
            edge_hist2 = cv2.calcHist([edge2], [0], None, [32], [0, 256])
            cv2.normalize(edge_hist1, edge_hist1)
            cv2.normalize(edge_hist2, edge_hist2)
            edge_score = cv2.compareHist(edge_hist1, edge_hist2, cv2.HISTCMP_CORREL)
            
            # 複合スコア (重み付き平均)
            combined_score = 0.5 * ssim_score + 0.3 * hist_score + 0.2 * edge_score
            return max(0, combined_score)
            
        except Exception:
            return 0.0
    
    def _compute_ssim(self, img1, img2) -> float:
        """SSIM (Structural Similarity Index) を計算"""
        C1 = 6.5025
        C2 = 58.5225
        
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)
        
        mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
        mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
        
        mu1_sq = mu1 ** 2
        mu2_sq = mu2 ** 2
        mu1_mu2 = mu1 * mu2
        
        sigma1_sq = cv2.GaussianBlur(img1 ** 2, (11, 11), 1.5) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2 ** 2, (11, 11), 1.5) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2
        
        ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
        
        return float(np.mean(ssim_map))
    
    def merge_clusters_with_layout(self, 
                                    text_clusters: List[List[TextBlock]], 
                                    layout_blocks: List[LayoutBlock]) -> List[Dict]:
        """
        テキストクラスターとレイアウトブロックをマージ
        
        レイアウトブロック内のテキストは同一パラグラフとして扱う
        
        Returns:
            統合されたパラグラフリスト
        """
        paragraphs = []
        
        # テキストクラスターからパラグラフを作成
        for cluster in text_clusters:
            if not cluster:
                continue
            
            # クラスター全体のバウンディングボックス
            x1 = min(b.rect[0] for b in cluster)
            y1 = min(b.rect[1] for b in cluster)
            x2 = max(b.rect[2] for b in cluster)
            y2 = max(b.rect[3] for b in cluster)
            
            # テキストを結合
            text = ' '.join(b.text for b in cluster)
            
            paragraphs.append({
                'rect': (x1, y1, x2, y2),
                'text': text,
                'source': 'spatial_cluster',
                'block_count': len(cluster)
            })
        
        # レイアウトブロックの情報を追加
        for block in layout_blocks:
            paragraphs.append({
                'rect': block.rect,
                'text': '',  # テキストは含まない (レイアウト情報のみ)
                'source': 'template_match',
                'template_id': block.template_id,
                'confidence': block.confidence
            })
        
        return paragraphs


def enhance_paragraph_detection(ocr_results: List[Dict], image: Image.Image) -> List[Dict]:
    """
    既存のOCR結果に空間クラスタリングを適用
    
    この関数を既存のパラグラフ検出ロジックに追加で呼び出す
    
    Args:
        ocr_results: OCR結果のリスト ({'text': str, 'rect': [x1,y1,x2,y2]})
        image: 元画像 (PIL Image)
    
    Returns:
        クラスタリングされたパラグラフリスト
    """
    analyzer = SpatialClusterAnalyzer()
    
    # フォント高さを推定
    text_blocks = analyzer.estimate_font_height(ocr_results)
    
    # 空間比率でクラスタリング
    text_clusters = analyzer.cluster_by_spatial_ratio(text_blocks)
    
    # 繰り返しレイアウト検出
    layout_blocks = analyzer.detect_repeating_layouts(image)
    
    # 統合
    paragraphs = analyzer.merge_clusters_with_layout(text_clusters, layout_blocks)
    
    return paragraphs
