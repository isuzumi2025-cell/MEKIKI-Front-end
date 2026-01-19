"""
CrossDocumentAligner - クロスドキュメントアライナー

機能:
- Web/PDF間のレイアウト対応付け
- マルチシグナル融合スコアリング
- RAGプロファイル保存 (マッチング成功時)

融合スコア重み配分:
- テキスト類似度: 40%
- レイアウト位置類似度: 25%
- 構文パターン一致: 15%
- 画像テンプレート類似度: 20%
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from PIL import Image

from .layout_detector import LayoutPatternDetector, LayoutPatternGroup
from .syntax_matcher import SyntaxPatternMatcher, SyntaxType
from .image_comparator import ImageRegionComparator


@dataclass
class AlignmentPair:
    """アライメントペア"""
    web_region: any
    pdf_region: any
    fusion_score: float
    text_score: float
    layout_score: float
    syntax_score: float
    image_score: float
    dominant_syntax_type: SyntaxType


@dataclass
class AlignmentResult:
    """アライメント結果"""
    pairs: List[AlignmentPair]
    web_pattern_groups: List[LayoutPatternGroup]
    pdf_pattern_groups: List[LayoutPatternGroup]
    overall_score: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class CrossDocumentAligner:
    """
    クロスドキュメントアライナー
    
    Web/PDF両方をスキャンして類似パターンを発見し、
    完全一致を目指した範囲選択シミュレーション用データを生成
    """
    
    # 融合スコア重み (承認済み)
    WEIGHT_TEXT = 0.40
    WEIGHT_LAYOUT = 0.25
    WEIGHT_SYNTAX = 0.15
    WEIGHT_IMAGE = 0.20
    
    def __init__(self, rag_save_path: Optional[str] = None):
        """
        Args:
            rag_save_path: RAGプロファイル保存パス (Noneなら保存しない)
        """
        self.layout_detector = LayoutPatternDetector(similarity_threshold=0.6)
        self.syntax_matcher = SyntaxPatternMatcher()
        self.image_comparator = ImageRegionComparator()
        self.rag_save_path = rag_save_path or os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'rag_profiles'
        )
        
        # テキスト類似度計算用
        self._text_matcher = None
    
    @property
    def text_matcher(self):
        """遅延初期化でParagraphMatcherを取得"""
        if self._text_matcher is None:
            from app.core.paragraph_matcher import ParagraphMatcher
            self._text_matcher = ParagraphMatcher()
        return self._text_matcher
    
    def align_documents(
        self,
        web_image: Image.Image,
        pdf_image: Image.Image,
        web_regions: List,
        pdf_regions: List
    ) -> AlignmentResult:
        """
        文書間アライメント実行
        
        Args:
            web_image: Web画像
            pdf_image: PDF画像
            web_regions: Web領域リスト
            pdf_regions: PDF領域リスト
        
        Returns:
            AlignmentResult: アライメント結果
        """
        print(f"[CrossAligner] アライメント開始: Web {len(web_regions)}件, PDF {len(pdf_regions)}件")
        
        # ページサイズ設定
        if web_image:
            self.layout_detector.set_page_dimensions(web_image.width, web_image.height)
        
        # Phase 1: レイアウトパターン検出
        web_groups = self.layout_detector.detect_repeating_patterns(web_regions)
        
        if pdf_image:
            self.layout_detector.set_page_dimensions(pdf_image.width, pdf_image.height)
        pdf_groups = self.layout_detector.detect_repeating_patterns(pdf_regions)
        
        # Phase 2: マルチシグナル融合スコアリング
        pairs = []
        used_web = set()
        used_pdf = set()
        
        # 全ペアのスコアを計算
        all_scores = []
        for i, wr in enumerate(web_regions):
            for j, pr in enumerate(pdf_regions):
                fusion = self.compute_fusion_alignment_score(
                    wr, pr, web_image, pdf_image
                )
                if fusion['fusion_score'] > 0.1:
                    all_scores.append((i, j, fusion))
        
        # 融合スコアでソート
        all_scores.sort(key=lambda x: x[2]['fusion_score'], reverse=True)
        
        # 貪欲マッチング
        for i, j, fusion in all_scores:
            if i in used_web or j in used_pdf:
                continue
            
            used_web.add(i)
            used_pdf.add(j)
            
            pair = AlignmentPair(
                web_region=web_regions[i],
                pdf_region=pdf_regions[j],
                fusion_score=fusion['fusion_score'],
                text_score=fusion['text_score'],
                layout_score=fusion['layout_score'],
                syntax_score=fusion['syntax_score'],
                image_score=fusion['image_score'],
                dominant_syntax_type=fusion['syntax_type']
            )
            pairs.append(pair)
        
        # 全体スコア計算
        overall = sum(p.fusion_score for p in pairs) / len(pairs) if pairs else 0.0
        
        result = AlignmentResult(
            pairs=pairs,
            web_pattern_groups=web_groups,
            pdf_pattern_groups=pdf_groups,
            overall_score=overall
        )
        
        print(f"[CrossAligner] 完了: {len(pairs)}ペア, 全体スコア {overall*100:.1f}%")
        
        # RAG保存 (マッチング成功時)
        if pairs and overall >= 0.3:
            self._save_rag_profile(result, web_regions, pdf_regions)
        
        return result
    
    def compute_fusion_alignment_score(
        self,
        web_region,
        pdf_region,
        web_image: Optional[Image.Image],
        pdf_image: Optional[Image.Image]
    ) -> dict:
        """
        融合アライメントスコア計算
        
        Returns:
            {
                'fusion_score': float,
                'text_score': float,
                'layout_score': float,
                'syntax_score': float,
                'image_score': float,
                'syntax_type': SyntaxType
            }
        """
        scores = {}
        weights_used = 0.0
        
        # テキスト取得
        web_text = web_region.text if hasattr(web_region, 'text') else web_region.get('text', '')
        pdf_text = pdf_region.text if hasattr(pdf_region, 'text') else pdf_region.get('text', '')
        
        # rect取得
        web_rect = web_region.rect if hasattr(web_region, 'rect') else web_region.get('rect', [0,0,100,100])
        pdf_rect = pdf_region.rect if hasattr(pdf_region, 'rect') else pdf_region.get('rect', [0,0,100,100])
        
        # 1. テキスト類似度 (40%)
        text_score = self.text_matcher.calculate_similarity(web_text, pdf_text)
        scores['text_score'] = text_score
        weights_used += self.WEIGHT_TEXT
        
        # 2. レイアウト類似度 (25%)
        web_features = self.layout_detector.extract_layout_features(web_region)
        pdf_features = self.layout_detector.extract_layout_features(pdf_region)
        layout_score = self.layout_detector.calculate_layout_similarity(web_features, pdf_features)
        scores['layout_score'] = layout_score
        weights_used += self.WEIGHT_LAYOUT
        
        # 3. 構文パターン類似度 (15%)
        syntax_score = self.syntax_matcher.calculate_syntax_similarity(web_text, pdf_text)
        scores['syntax_score'] = syntax_score
        weights_used += self.WEIGHT_SYNTAX
        
        # 支配的構文タイプ
        web_sig = self.syntax_matcher.extract_syntax_signature(web_text)
        pdf_sig = self.syntax_matcher.extract_syntax_signature(pdf_text)
        if web_sig.confidence >= pdf_sig.confidence:
            scores['syntax_type'] = web_sig.dominant_type
        else:
            scores['syntax_type'] = pdf_sig.dominant_type
        
        # 4. 画像類似度 (20%)
        if web_image and pdf_image:
            image_score = self.image_comparator.compare_regions(
                web_image, list(web_rect),
                pdf_image, list(pdf_rect)
            )
            scores['image_score'] = image_score
            weights_used += self.WEIGHT_IMAGE
        else:
            scores['image_score'] = 0.0
        
        # 融合スコア計算
        fusion = (
            scores['text_score'] * self.WEIGHT_TEXT +
            scores['layout_score'] * self.WEIGHT_LAYOUT +
            scores['syntax_score'] * self.WEIGHT_SYNTAX +
            scores['image_score'] * self.WEIGHT_IMAGE
        )
        
        # 正規化
        if weights_used > 0:
            fusion = fusion / weights_used * (self.WEIGHT_TEXT + self.WEIGHT_LAYOUT + self.WEIGHT_SYNTAX + self.WEIGHT_IMAGE)
        
        scores['fusion_score'] = min(1.0, fusion)
        
        return scores
    
    def _save_rag_profile(
        self, 
        result: AlignmentResult,
        web_regions: List,
        pdf_regions: List
    ):
        """
        RAGプロファイル保存 (マッチング成功時)
        """
        try:
            os.makedirs(self.rag_save_path, exist_ok=True)
            
            # ファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"profile_{timestamp}.json"
            filepath = os.path.join(self.rag_save_path, filename)
            
            # プロファイルデータ
            profile = {
                'timestamp': result.timestamp,
                'overall_score': result.overall_score,
                'pair_count': len(result.pairs),
                'web_pattern_groups': len(result.web_pattern_groups),
                'pdf_pattern_groups': len(result.pdf_pattern_groups),
                'pairs': [
                    {
                        'web_id': p.web_region.area_code if hasattr(p.web_region, 'area_code') else str(p.web_region.get('id', '')),
                        'pdf_id': p.pdf_region.area_code if hasattr(p.pdf_region, 'area_code') else str(p.pdf_region.get('id', '')),
                        'fusion_score': p.fusion_score,
                        'text_score': p.text_score,
                        'layout_score': p.layout_score,
                        'syntax_score': p.syntax_score,
                        'image_score': p.image_score,
                        'syntax_type': p.dominant_syntax_type.name
                    }
                    for p in result.pairs
                ]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            
            print(f"[RAG] プロファイル保存: {filepath}")
            
        except Exception as e:
            print(f"[RAG] 保存エラー: {e}")
