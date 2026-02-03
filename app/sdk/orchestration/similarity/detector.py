"""
MEKIKI SDK - Similarity Detector
類似領域検出システム

機能:
- テンプレート領域に類似した候補を自動検出
- テキスト類似度、視覚類似度の両方をサポート
- SDK化による再利用性とロギング

使用例:
    from app.sdk.similarity import SimilarityDetector
    
    detector = SimilarityDetector(threshold=0.8)
    results = detector.find_similar_text(template, candidates)
"""

import logging
import difflib
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass

# ロギング設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class SimilarityResult:
    """類似度検出結果"""
    candidate: Any
    similarity_score: float
    match_type: str  # "text", "visual", "combined"
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class SimilarityDetector:
    """
    類似領域検出 SDK
    
    ★ 機能:
    - テキストベースの類似度検出 (difflib SequenceMatcher)
    - 視覚的な類似度検出 (任意のコールバック)
    - 複合類似度によるランキング
    
    ★ ログ出力:
    - 検索開始/完了
    - 発見した類似領域数
    - 類似度スコア分布
    """
    
    def __init__(
        self, 
        threshold: float = 0.7,
        visual_detector: Optional[Callable] = None
    ):
        """
        Args:
            threshold: 類似度閾値 (0.0-1.0)
            visual_detector: 視覚類似度検出コールバック (image1, image2) -> float
        """
        self.threshold = threshold
        self.visual_detector = visual_detector
        
        logger.info(f"SimilarityDetector initialized (threshold={threshold})")
    
    def find_similar_text(
        self, 
        template_text: str, 
        candidates: List[Any],
        text_getter: Optional[Callable] = None
    ) -> List[SimilarityResult]:
        """
        テキスト類似度に基づいて類似領域を検出
        
        Args:
            template_text: テンプレートテキスト
            candidates: 候補リスト (各要素は.textまたはtext_getterで取得)
            text_getter: テキスト取得関数 (candidate) -> str
        
        Returns:
            SimilarityResultのリスト (類似度降順)
        """
        logger.info(f"Searching {len(candidates)} candidates for text similarity")
        logger.debug(f"Template text: '{template_text[:50]}...'")
        
        if not template_text or not candidates:
            return []
        
        results: List[SimilarityResult] = []
        
        for candidate in candidates:
            # テキスト取得
            if text_getter:
                candidate_text = text_getter(candidate)
            elif hasattr(candidate, 'text'):
                candidate_text = candidate.text
            else:
                candidate_text = str(candidate)
            
            if not candidate_text:
                continue
            
            # 類似度計算
            score = self._calculate_text_similarity(template_text, candidate_text)
            
            if score >= self.threshold:
                result = SimilarityResult(
                    candidate=candidate,
                    similarity_score=score,
                    match_type="text",
                    details={
                        'template_length': len(template_text),
                        'candidate_length': len(candidate_text),
                        'matching_blocks': self._get_matching_blocks(template_text, candidate_text)
                    }
                )
                results.append(result)
        
        # 類似度降順でソート
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        
        logger.info(f"Found {len(results)} similar regions (threshold={self.threshold})")
        if results:
            logger.debug(f"Top score: {results[0].similarity_score:.2%}")
        
        return results
    
    def find_similar_visual(
        self, 
        template_image: Any, 
        candidates: List[Any],
        image_getter: Optional[Callable] = None
    ) -> List[SimilarityResult]:
        """
        視覚類似度に基づいて類似領域を検出
        
        Args:
            template_image: テンプレート画像
            candidates: 候補リスト
            image_getter: 画像取得関数 (candidate) -> Image
        
        Returns:
            SimilarityResultのリスト
        """
        if not self.visual_detector:
            logger.warning("No visual detector configured, returning empty results")
            return []
        
        logger.info(f"Searching {len(candidates)} candidates for visual similarity")
        
        results: List[SimilarityResult] = []
        
        for candidate in candidates:
            # 画像取得
            if image_getter:
                candidate_image = image_getter(candidate)
            else:
                candidate_image = getattr(candidate, 'image', None)
            
            if candidate_image is None:
                continue
            
            try:
                score = self.visual_detector(template_image, candidate_image)
                
                if score >= self.threshold:
                    result = SimilarityResult(
                        candidate=candidate,
                        similarity_score=score,
                        match_type="visual"
                    )
                    results.append(result)
            except Exception as e:
                logger.warning(f"Visual similarity error: {e}")
                continue
        
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        
        logger.info(f"Found {len(results)} visually similar regions")
        return results
    
    def find_similar_combined(
        self,
        template_text: str,
        template_image: Any,
        candidates: List[Any],
        text_weight: float = 0.7,
        visual_weight: float = 0.3
    ) -> List[SimilarityResult]:
        """
        テキスト+視覚の複合類似度で検出
        
        Args:
            template_text: テンプレートテキスト
            template_image: テンプレート画像
            candidates: 候補リスト
            text_weight: テキスト類似度の重み
            visual_weight: 視覚類似度の重み
        
        Returns:
            SimilarityResultのリスト
        """
        logger.info(f"Combined similarity search (text_weight={text_weight}, visual_weight={visual_weight})")
        
        text_results = {
            id(r.candidate): r 
            for r in self.find_similar_text(template_text, candidates)
        }
        
        visual_results = {}
        if self.visual_detector and template_image:
            visual_results = {
                id(r.candidate): r 
                for r in self.find_similar_visual(template_image, candidates)
            }
        
        # 複合スコア計算
        combined_results: List[SimilarityResult] = []
        all_candidates = set(text_results.keys()) | set(visual_results.keys())
        
        for cid in all_candidates:
            text_score = text_results.get(cid).similarity_score if cid in text_results else 0.0
            visual_score = visual_results.get(cid).similarity_score if cid in visual_results else 0.0
            
            combined_score = text_score * text_weight + visual_score * visual_weight
            
            if combined_score >= self.threshold:
                candidate = text_results.get(cid) or visual_results.get(cid)
                result = SimilarityResult(
                    candidate=candidate.candidate,
                    similarity_score=combined_score,
                    match_type="combined",
                    details={
                        'text_score': text_score,
                        'visual_score': visual_score,
                        'weights': {'text': text_weight, 'visual': visual_weight}
                    }
                )
                combined_results.append(result)
        
        combined_results.sort(key=lambda r: r.similarity_score, reverse=True)
        
        logger.info(f"Combined search found {len(combined_results)} matches")
        return combined_results
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似度を計算"""
        if not text1 or not text2:
            return 0.0
        
        # 正規化
        t1 = text1.strip().lower()
        t2 = text2.strip().lower()
        
        # SequenceMatcherで計算
        matcher = difflib.SequenceMatcher(None, t1, t2)
        return matcher.ratio()
    
    def _get_matching_blocks(self, text1: str, text2: str) -> List[Tuple[int, int, int]]:
        """マッチングブロックを取得"""
        matcher = difflib.SequenceMatcher(None, text1.lower(), text2.lower())
        return list(matcher.get_matching_blocks())
    
    def set_threshold(self, threshold: float):
        """閾値を設定"""
        self.threshold = threshold
        logger.info(f"Threshold updated to {threshold}")
    
    def get_stats(self) -> dict:
        """統計情報を返却"""
        return {
            'threshold': self.threshold,
            'has_visual_detector': self.visual_detector is not None
        }
    
    def __repr__(self):
        return f"SimilarityDetector(threshold={self.threshold})"


# ========== Convenience exports ==========
__all__ = ["SimilarityDetector", "SimilarityResult"]
