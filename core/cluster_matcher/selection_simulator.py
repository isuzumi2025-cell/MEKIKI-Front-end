"""
SelectionSimulator - 範囲選択シミュレーター

機能:
- マッチング結果から最適な選択範囲を提案
- 完全一致を目指した範囲調整
- ユーザーへのサジェスション表示
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

from .cross_aligner import AlignmentResult, AlignmentPair
from .syntax_matcher import SyntaxType


@dataclass
class SelectionSuggestion:
    """選択範囲サジェスト"""
    web_region: any
    pdf_region: any
    current_similarity: float
    suggested_web_rect: List[int]
    suggested_pdf_rect: List[int]
    predicted_similarity: float
    adjustment_reason: str
    syntax_type: SyntaxType
    priority: int  # 1=高優先度, 2=中, 3=低


class SelectionSimulator:
    """
    範囲選択シミュレーター
    
    マッチングペアから最適な選択範囲を提案し、
    完全一致を目指した調整をシミュレーション
    """
    
    def __init__(self, target_similarity: float = 0.9):
        """
        Args:
            target_similarity: 目標類似度 (デフォルト 90%)
        """
        self.target_similarity = target_similarity
        
        # テキスト類似度計算用
        self._text_matcher = None
    
    @property
    def text_matcher(self):
        """遅延初期化でParagraphMatcherを取得"""
        if self._text_matcher is None:
            from app.core.paragraph_matcher import ParagraphMatcher
            self._text_matcher = ParagraphMatcher()
        return self._text_matcher
    
    def simulate_optimal_selections(
        self,
        alignment_result: AlignmentResult
    ) -> List[SelectionSuggestion]:
        """
        最適選択範囲をシミュレーション
        
        Args:
            alignment_result: アライメント結果
        
        Returns:
            選択範囲サジェストのリスト
        """
        suggestions = []
        
        for pair in alignment_result.pairs:
            suggestion = self._analyze_pair_for_improvement(pair)
            if suggestion:
                suggestions.append(suggestion)
        
        # 優先度でソート
        suggestions.sort(key=lambda s: (s.priority, -s.predicted_similarity))
        
        print(f"[SelectionSim] {len(suggestions)}件のサジェストを生成")
        return suggestions
    
    def _analyze_pair_for_improvement(
        self, 
        pair: AlignmentPair
    ) -> Optional[SelectionSuggestion]:
        """
        ペアを分析して改善サジェストを生成
        """
        # 既に高スコアなら調整不要
        if pair.fusion_score >= self.target_similarity:
            return SelectionSuggestion(
                web_region=pair.web_region,
                pdf_region=pair.pdf_region,
                current_similarity=pair.fusion_score,
                suggested_web_rect=self._get_rect(pair.web_region),
                suggested_pdf_rect=self._get_rect(pair.pdf_region),
                predicted_similarity=pair.fusion_score,
                adjustment_reason="既に高スコア - 調整不要",
                syntax_type=pair.dominant_syntax_type,
                priority=3
            )
        
        # テキスト取得
        web_text = self._get_text(pair.web_region)
        pdf_text = self._get_text(pair.pdf_region)
        web_rect = self._get_rect(pair.web_region)
        pdf_rect = self._get_rect(pair.pdf_region)
        
        # 改善戦略を決定
        reason, new_web_rect, new_pdf_rect, predicted = self._determine_improvement_strategy(
            web_text, pdf_text, web_rect, pdf_rect, pair
        )
        
        # 優先度計算
        improvement = predicted - pair.fusion_score
        if improvement >= 0.2:
            priority = 1
        elif improvement >= 0.1:
            priority = 2
        else:
            priority = 3
        
        return SelectionSuggestion(
            web_region=pair.web_region,
            pdf_region=pair.pdf_region,
            current_similarity=pair.fusion_score,
            suggested_web_rect=new_web_rect,
            suggested_pdf_rect=new_pdf_rect,
            predicted_similarity=predicted,
            adjustment_reason=reason,
            syntax_type=pair.dominant_syntax_type,
            priority=priority
        )
    
    def _determine_improvement_strategy(
        self,
        web_text: str,
        pdf_text: str,
        web_rect: List[int],
        pdf_rect: List[int],
        pair: AlignmentPair
    ) -> Tuple[str, List[int], List[int], float]:
        """
        改善戦略を決定
        
        Returns:
            (理由, 新Web矩形, 新PDF矩形, 予測スコア)
        """
        # 戦略1: テキスト長の不一致
        len_ratio = len(web_text) / len(pdf_text) if pdf_text else 0
        if len_ratio > 1.5 or len_ratio < 0.67:
            # テキスト長が大きく異なる → 範囲調整が必要
            if len_ratio > 1:
                # Webが長い → Web範囲を縮小
                new_web_rect = self._shrink_rect(web_rect, 0.8)
                predicted = min(1.0, pair.fusion_score * 1.2)
                return ("Web側テキストが長い - 範囲縮小を推奨", new_web_rect, pdf_rect, predicted)
            else:
                # PDFが長い → PDF範囲を縮小
                new_pdf_rect = self._shrink_rect(pdf_rect, 0.8)
                predicted = min(1.0, pair.fusion_score * 1.2)
                return ("PDF側テキストが長い - 範囲縮小を推奨", web_rect, new_pdf_rect, predicted)
        
        # 戦略2: レイアウトスコアが低い
        if pair.layout_score < 0.5:
            # 位置/サイズが異なる → サイズ統一を推奨
            avg_width = (web_rect[2] - web_rect[0] + pdf_rect[2] - pdf_rect[0]) // 2
            avg_height = (web_rect[3] - web_rect[1] + pdf_rect[3] - pdf_rect[1]) // 2
            
            new_web_rect = self._resize_rect(web_rect, avg_width, avg_height)
            new_pdf_rect = self._resize_rect(pdf_rect, avg_width, avg_height)
            
            predicted = min(1.0, pair.fusion_score + 0.15)
            return ("レイアウト不一致 - サイズ統一を推奨", new_web_rect, new_pdf_rect, predicted)
        
        # 戦略3: 画像スコアが低い
        if pair.image_score < 0.4 and pair.text_score > 0.6:
            predicted = pair.fusion_score + 0.1
            return ("テキスト一致だが画像不一致 - 視覚確認を推奨", web_rect, pdf_rect, predicted)
        
        # 戦略4: 構文パターン特化
        if pair.dominant_syntax_type in [SyntaxType.ADDRESS, SyntaxType.PHONE, SyntaxType.PRICE]:
            # 構造化データ → 完全一致が期待できる
            predicted = min(1.0, pair.fusion_score * 1.15)
            return (f"{pair.dominant_syntax_type.name}パターン - 高精度マッチ可能", web_rect, pdf_rect, predicted)
        
        # デフォルト
        return ("微調整で改善可能", web_rect, pdf_rect, min(1.0, pair.fusion_score * 1.1))
    
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
    
    def _shrink_rect(self, rect: List[int], ratio: float) -> List[int]:
        """矩形を縮小"""
        x1, y1, x2, y2 = rect
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = (x2 - x1) * ratio / 2
        h = (y2 - y1) * ratio / 2
        return [int(cx - w), int(cy - h), int(cx + w), int(cy + h)]
    
    def _resize_rect(self, rect: List[int], width: int, height: int) -> List[int]:
        """矩形をリサイズ（中心維持）"""
        x1, y1, x2, y2 = rect
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return [cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2]
    
    def refine_selection_for_match(
        self,
        web_region,
        pdf_region,
        max_iterations: int = 5
    ) -> Tuple[List[int], List[int], float]:
        """
        完全一致を目指して選択範囲を反復微調整
        
        Returns:
            (調整後Web矩形, 調整後PDF矩形, 最終類似度)
        """
        web_rect = self._get_rect(web_region)
        pdf_rect = self._get_rect(pdf_region)
        
        best_score = 0.0
        best_web_rect = web_rect
        best_pdf_rect = pdf_rect
        
        for i in range(max_iterations):
            # 現在のスコア計算
            web_text = self._get_text(web_region)
            pdf_text = self._get_text(pdf_region)
            score = self.text_matcher.calculate_similarity(web_text, pdf_text)
            
            if score > best_score:
                best_score = score
                best_web_rect = web_rect.copy()
                best_pdf_rect = pdf_rect.copy()
            
            if score >= self.target_similarity:
                break
            
            # 微調整試行
            # (実際には領域内テキスト再抽出が必要だが、ここでは範囲のみ調整)
            web_rect = self._shrink_rect(web_rect, 0.95)
            pdf_rect = self._shrink_rect(pdf_rect, 0.95)
        
        return best_web_rect, best_pdf_rect, best_score
