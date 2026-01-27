"""
MEKIKI SDK - Paragraph Matcher
Web/PDFパラグラフマッチングシステム

機能:
- Web選択とPDF選択の最適マッチング
- テキスト類似度による自動ペアリング
- 貪欲法による高速マッチング

使用例:
    from app.sdk.similarity.paragraph_matcher import ParagraphMatcher
    
    matcher = ParagraphMatcher(threshold=0.25)
    sync_pairs = matcher.match(web_regions, pdf_regions)
"""

import logging
import difflib
from typing import List, Any, Optional
from dataclasses import dataclass

# ロギング設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class SyncPair:
    """マッチングペア"""
    web_id: str
    pdf_id: str
    web_text: str
    pdf_text: str
    similarity: float
    web_bbox: Optional[tuple] = None
    pdf_bbox: Optional[tuple] = None


class ParagraphMatcher:
    """
    Web/PDFパラグラフマッチング SDK
    
    ★ 機能:
    - 全組み合わせの類似度計算
    - 貪欲法による最適マッチング
    - 閾値フィルタリング
    
    ★ ログ出力:
    - マッチング開始/完了
    - 類似度行列サイズ
    - マッチペア数
    """
    
    def __init__(self, threshold: float = 0.25):
        """
        Args:
            threshold: マッチング閾値 (0.0-1.0)
        """
        self.threshold = threshold
        logger.info(f"ParagraphMatcher initialized (threshold={threshold})")
    
    def match(
        self, 
        web_regions: List[Any], 
        pdf_regions: List[Any]
    ) -> List[SyncPair]:
        """
        Web/PDF領域をマッチング
        
        Args:
            web_regions: Web側の選択領域リスト
            pdf_regions: PDF側の選択領域リスト
        
        Returns:
            SyncPairのリスト
        """
        print(f"\n{'='*50}")
        print(f"🔗 パラグラフマッチング開始")
        print(f"  Web: {len(web_regions)}件, PDF: {len(pdf_regions)}件")
        print(f"{'='*50}")
        
        if not web_regions or not pdf_regions:
            print("⚠️ マッチング: 入力が不足しています")
            return []
        
        # Step 1: 類似度行列を計算
        similarity_matrix = self._compute_similarity_matrix(web_regions, pdf_regions)
        
        # Step 2: 貪欲法で最適マッチを選択
        matches = self._greedy_match(web_regions, pdf_regions, similarity_matrix)
        
        print(f"\n✅ マッチング完了: {len(matches)}ペア生成")
        return matches
    
    def _compute_similarity_matrix(
        self, 
        web_regions: List[Any], 
        pdf_regions: List[Any]
    ) -> List[List[float]]:
        """全組み合わせの類似度行列を計算"""
        print(f"📊 類似度行列計算: {len(web_regions)} x {len(pdf_regions)}")
        
        matrix = []
        for i, web in enumerate(web_regions):
            row = []
            web_text = self._get_text(web)
            
            for j, pdf in enumerate(pdf_regions):
                pdf_text = self._get_text(pdf)
                score = self._calculate_similarity(web_text, pdf_text)
                row.append(score)
            
            matrix.append(row)
            
            # 進捗表示
            if (i + 1) % 5 == 0 or i == len(web_regions) - 1:
                print(f"  進捗: {i+1}/{len(web_regions)}")
        
        return matrix
    
    def _greedy_match(
        self,
        web_regions: List[Any],
        pdf_regions: List[Any],
        similarity_matrix: List[List[float]]
    ) -> List[SyncPair]:
        """貪欲法で最適マッチを選択"""
        print(f"🎯 貪欲法マッチング (閾値: {self.threshold})")
        
        matches = []
        used_web = set()
        used_pdf = set()
        
        # 全ペアをスコア降順でソート
        all_pairs = []
        for i in range(len(web_regions)):
            for j in range(len(pdf_regions)):
                score = similarity_matrix[i][j]
                if score >= self.threshold:
                    all_pairs.append((score, i, j))
        
        all_pairs.sort(reverse=True, key=lambda x: x[0])
        
        # 貪欲に選択
        for score, web_idx, pdf_idx in all_pairs:
            if web_idx in used_web or pdf_idx in used_pdf:
                continue
            
            web = web_regions[web_idx]
            pdf = pdf_regions[pdf_idx]
            
            pair = SyncPair(
                web_id=self._get_id(web),
                pdf_id=self._get_id(pdf),
                web_text=self._get_text(web),
                pdf_text=self._get_text(pdf),
                similarity=score,
                web_bbox=self._get_bbox(web),
                pdf_bbox=self._get_bbox(pdf)
            )
            matches.append(pair)
            used_web.add(web_idx)
            used_pdf.add(pdf_idx)
            
            print(f"  ✓ {pair.web_id} ↔ {pair.pdf_id}: {score:.1%}")
        
        # マッチしなかった領域も追加 (score=0)
        for i, web in enumerate(web_regions):
            if i not in used_web:
                pair = SyncPair(
                    web_id=self._get_id(web),
                    pdf_id="",
                    web_text=self._get_text(web),
                    pdf_text="",
                    similarity=0.0,
                    web_bbox=self._get_bbox(web),
                    pdf_bbox=None
                )
                matches.append(pair)
        
        for j, pdf in enumerate(pdf_regions):
            if j not in used_pdf:
                pair = SyncPair(
                    web_id="",
                    pdf_id=self._get_id(pdf),
                    web_text="",
                    pdf_text=self._get_text(pdf),
                    similarity=0.0,
                    web_bbox=None,
                    pdf_bbox=self._get_bbox(pdf)
                )
                matches.append(pair)
        
        return matches
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似度を計算 (difflib SequenceMatcher)"""
        if not text1 or not text2:
            return 0.0
        
        # 正規化
        t1 = text1.strip().lower()
        t2 = text2.strip().lower()
        
        # SequenceMatcherで計算
        matcher = difflib.SequenceMatcher(None, t1, t2)
        return matcher.ratio()
    
    def _get_text(self, region: Any) -> str:
        """領域からテキストを取得"""
        if hasattr(region, 'text'):
            return region.text or ""
        return str(region)
    
    def _get_id(self, region: Any) -> str:
        """領域からIDを取得"""
        if hasattr(region, 'area_code'):
            return region.area_code or ""
        if hasattr(region, 'id'):
            return str(region.id)
        return ""
    
    def _get_bbox(self, region: Any) -> Optional[tuple]:
        """領域から座標を取得"""
        if hasattr(region, 'rect'):
            return region.rect
        if hasattr(region, 'bbox'):
            return region.bbox
        return None
    
    def set_threshold(self, threshold: float):
        """閾値を設定"""
        self.threshold = threshold
        logger.info(f"Threshold updated to {threshold}")
    
    def __repr__(self):
        return f"ParagraphMatcher(threshold={self.threshold})"


# ========== Convenience exports ==========
__all__ = ["ParagraphMatcher", "SyncPair"]
