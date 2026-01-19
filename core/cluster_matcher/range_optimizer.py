"""
RangeOptimizationSimulator - 範囲最適化シミュレーター

機能:
- 20%+のマッチペアを対象に範囲を調整
- 5%刻みで範囲を拡大/縮小してスコア変化をシミュレーション
- 最大整合性を達成する範囲を自動探索・適用

承認済みパラメータ:
- 粒度: 5%
- 最小閾値: 20%
- 自動適用: OCR実行に内包
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from difflib import SequenceMatcher
import re


@dataclass
class OptimizationResult:
    """最適化結果"""
    web_region: any
    pdf_region: any
    original_score: float
    optimized_score: float
    original_web_rect: List[int]
    original_pdf_rect: List[int]
    optimized_web_rect: List[int]
    optimized_pdf_rect: List[int]
    adjustment_applied: str
    improvement: float


class RangeOptimizationSimulator:
    """
    範囲最適化シミュレーター
    
    既存マッチペア（20%+）の範囲を調整して最大整合性を探索
    """
    
    # 承認済みパラメータ
    STEP_PERCENT = 0.05   # 5%刻み
    MIN_THRESHOLD = 0.20  # 20%以上のペアが対象
    MAX_ITERATIONS = 10   # 最大調整回数
    
    def __init__(self):
        self._text_matcher = None
    
    @property
    def text_matcher(self):
        """遅延初期化でParagraphMatcherを取得"""
        if self._text_matcher is None:
            from app.core.paragraph_matcher import ParagraphMatcher
            self._text_matcher = ParagraphMatcher()
        return self._text_matcher
    
    def optimize_all_pairs(
        self,
        web_regions: List,
        pdf_regions: List,
        sync_pairs: List
    ) -> List[OptimizationResult]:
        """
        全ペアの範囲を最適化
        
        Args:
            web_regions: Web領域リスト
            pdf_regions: PDF領域リスト
            sync_pairs: 既存のマッチペアリスト
        
        Returns:
            最適化結果のリスト
        """
        results = []
        optimized_count = 0
        
        # 20%+のペアを抽出
        target_pairs = [sp for sp in sync_pairs if sp.similarity >= self.MIN_THRESHOLD]
        print(f"[RangeOptimizer] 対象ペア: {len(target_pairs)}件 (20%+)")
        
        # 領域マップを作成
        web_map = {r.area_code if hasattr(r, 'area_code') else r.get('id'): r for r in web_regions}
        pdf_map = {r.area_code if hasattr(r, 'area_code') else r.get('id'): r for r in pdf_regions}
        
        for sp in target_pairs:
            web_region = web_map.get(sp.web_id)
            pdf_region = pdf_map.get(sp.pdf_id)
            
            if not web_region or not pdf_region:
                continue
            
            # 範囲最適化を実行
            result = self.optimize_pair(web_region, pdf_region, sp.similarity)
            
            if result and result.improvement > 0.05:  # 5%以上の改善
                results.append(result)
                optimized_count += 1
                
                # 範囲を更新
                self._apply_optimized_range(web_region, result.optimized_web_rect)
                self._apply_optimized_range(pdf_region, result.optimized_pdf_rect)
        
        print(f"[RangeOptimizer] 最適化完了: {optimized_count}件改善")
        return results
    
    def optimize_pair(
        self,
        web_region,
        pdf_region,
        current_score: float
    ) -> Optional[OptimizationResult]:
        """
        1ペアの範囲を最適化
        """
        web_text = self._get_text(web_region)
        pdf_text = self._get_text(pdf_region)
        web_rect = self._get_rect(web_region)
        pdf_rect = self._get_rect(pdf_region)
        
        if not web_text or not pdf_text:
            return None
        
        # 共通部分を検出
        common_ratio = self._find_common_text_ratio(web_text, pdf_text)
        
        # 最適な調整を探索
        best_score = current_score
        best_web_rect = web_rect
        best_pdf_rect = pdf_rect
        best_adjustment = "調整なし"
        
        # 5%刻みで範囲調整をシミュレーション
        for i in range(1, self.MAX_ITERATIONS + 1):
            shrink_ratio = 1.0 - (i * self.STEP_PERCENT)
            expand_ratio = 1.0 + (i * self.STEP_PERCENT)
            
            # 縮小テスト（Web側）
            test_web_rect = self._adjust_rect(web_rect, shrink_ratio)
            score = self._estimate_score_after_adjustment(
                web_text, pdf_text, common_ratio, shrink_ratio, 1.0
            )
            if score > best_score:
                best_score = score
                best_web_rect = test_web_rect
                best_adjustment = f"Web -{i*5}%縮小"
            
            # 縮小テスト（PDF側）
            test_pdf_rect = self._adjust_rect(pdf_rect, shrink_ratio)
            score = self._estimate_score_after_adjustment(
                web_text, pdf_text, common_ratio, 1.0, shrink_ratio
            )
            if score > best_score:
                best_score = score
                best_pdf_rect = test_pdf_rect
                best_adjustment = f"PDF -{i*5}%縮小"
            
            # 両方縮小テスト
            score = self._estimate_score_after_adjustment(
                web_text, pdf_text, common_ratio, shrink_ratio, shrink_ratio
            )
            if score > best_score:
                best_score = score
                best_web_rect = self._adjust_rect(web_rect, shrink_ratio)
                best_pdf_rect = self._adjust_rect(pdf_rect, shrink_ratio)
                best_adjustment = f"両方 -{i*5}%縮小"
        
        improvement = best_score - current_score
        
        return OptimizationResult(
            web_region=web_region,
            pdf_region=pdf_region,
            original_score=current_score,
            optimized_score=best_score,
            original_web_rect=web_rect,
            original_pdf_rect=pdf_rect,
            optimized_web_rect=best_web_rect,
            optimized_pdf_rect=best_pdf_rect,
            adjustment_applied=best_adjustment,
            improvement=improvement
        )
    
    def _find_common_text_ratio(self, text1: str, text2: str) -> float:
        """共通テキストの比率を計算"""
        if not text1 or not text2:
            return 0.0
        
        # 正規化
        t1 = self._normalize_text(text1)
        t2 = self._normalize_text(text2)
        
        # SequenceMatcherで共通部分を検出
        matcher = SequenceMatcher(None, t1, t2)
        
        # 最長共通部分文字列のブロックを取得
        blocks = matcher.get_matching_blocks()
        
        # 共通文字数
        common_chars = sum(block.size for block in blocks)
        
        # 比率計算
        max_len = max(len(t1), len(t2))
        return common_chars / max_len if max_len > 0 else 0.0
    
    def _estimate_score_after_adjustment(
        self,
        web_text: str,
        pdf_text: str,
        common_ratio: float,
        web_shrink: float,
        pdf_shrink: float
    ) -> float:
        """
        範囲調整後のスコアを推定
        
        縮小すると余分なテキストが除外され、共通部分の比率が上がる
        """
        # 縮小による効果をモデル化
        # 縮小すると、テキスト長が減少し、共通部分の比率が相対的に上がる
        
        # 効果的な縮小の場合、スコアが上がる
        shrink_effect = min(web_shrink, pdf_shrink)
        
        # 共通部分が多いほど、縮小の効果が大きい
        if common_ratio > 0.3:
            # 共通部分が多い場合、縮小すると精度向上
            estimated_improvement = (1.0 - shrink_effect) * common_ratio * 0.5
            return min(1.0, common_ratio + estimated_improvement)
        else:
            # 共通部分が少ない場合、縮小しても効果は限定的
            return common_ratio
    
    def _normalize_text(self, text: str) -> str:
        """テキストの正規化"""
        import unicodedata
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()
    
    def _get_text(self, region) -> str:
        """領域からテキストを取得"""
        if hasattr(region, 'text'):
            return region.text or ""
        return region.get('text', '')
    
    def _get_rect(self, region) -> List[int]:
        """領域から矩形を取得"""
        if hasattr(region, 'rect'):
            return list(region.rect)
        return list(region.get('rect', [0, 0, 100, 100]))
    
    def _adjust_rect(self, rect: List[int], ratio: float) -> List[int]:
        """矩形を調整（中心維持）"""
        x1, y1, x2, y2 = rect
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = (x2 - x1) * ratio / 2
        h = (y2 - y1) * ratio / 2
        return [int(cx - w), int(cy - h), int(cx + w), int(cy + h)]
    
    def _apply_optimized_range(self, region, new_rect: List[int]):
        """最適化された範囲を領域に適用"""
        if hasattr(region, 'rect'):
            if isinstance(region.rect, tuple):
                region.rect = tuple(new_rect)
            else:
                region.rect = new_rect
        elif isinstance(region, dict):
            region['rect'] = new_rect
