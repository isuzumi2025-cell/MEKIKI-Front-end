"""
MEKIKI SDK - Enhanced Paragraph Matcher
Web/PDFパラグラフマッチングシステム (精度向上版)

改善点:
- 文字単位の完全一致部分を抽出
- 部分一致と完全一致を区別
- より正確な類似度計算
- 同一文言の二重計上を防止

Created: 2026-01-28
"""

import logging
import difflib
import re
from typing import List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class MatchDetail:
    """マッチ詳細情報"""
    matched_phrases: List[str] = field(default_factory=list)  # 完全一致フレーズ
    web_only_phrases: List[str] = field(default_factory=list)  # Webのみ
    pdf_only_phrases: List[str] = field(default_factory=list)  # PDFのみ
    char_match_ratio: float = 0.0  # 文字レベル一致率


@dataclass
class SyncPair:
    """マッチングペア (拡張版)"""
    web_id: str
    pdf_id: str
    web_text: str
    pdf_text: str
    similarity: float
    web_bbox: Optional[tuple] = None
    pdf_bbox: Optional[tuple] = None
    match_detail: Optional[MatchDetail] = None
    sync_color: str = "#808080"  # 表示色


class EnhancedParagraphMatcher:
    """
    精度向上版 パラグラフマッチャー
    
    改善点:
    1. 文字単位の厳密な一致率計算
    2. フレーズ抽出による詳細分析
    3. 閾値の動的調整
    4. 類似度に基づく色分け
    """
    
    # 色パレット (類似度レベル別)
    COLOR_EXACT = "#4CAF50"     # 90%+  緑
    COLOR_HIGH = "#8BC34A"      # 70-90% 黄緑
    COLOR_MEDIUM = "#FFEB3B"    # 50-70% 黄
    COLOR_LOW = "#FF9800"       # 30-50% オレンジ
    COLOR_MISMATCH = "#F44336"  # 30%未満 赤
    COLOR_UNMATCHED = "#808080" # 未マッチ 灰
    
    def __init__(self, threshold: float = 0.40):
        """
        Args:
            threshold: マッチング閾値 (0.0-1.0), デフォルト0.40 (旧0.25より厳格)
        """
        self.threshold = threshold
        logger.info(f"EnhancedParagraphMatcher initialized (threshold={threshold})")
    
    def match(
        self, 
        web_regions: List[Any], 
        pdf_regions: List[Any]
    ) -> List[SyncPair]:
        """
        Web/PDF領域をマッチング
        """
        print(f"\n{'='*50}")
        print(f"🔗 精度向上版マッチング開始")
        print(f"  Web: {len(web_regions)}件, PDF: {len(pdf_regions)}件")
        print(f"  閾値: {self.threshold:.0%}")
        print(f"{'='*50}")
        
        if not web_regions or not pdf_regions:
            print("⚠️ マッチング: 入力が不足しています")
            return []
        
        # Step 1: 類似度行列を計算
        similarity_matrix, detail_matrix = self._compute_similarity_matrix(
            web_regions, pdf_regions
        )
        
        # Step 2: 貪欲法で最適マッチを選択
        matches = self._greedy_match(
            web_regions, pdf_regions, 
            similarity_matrix, detail_matrix
        )
        
        # Step 3: 色を設定
        self._assign_colors(matches)
        
        print(f"\n✅ マッチング完了: {len(matches)}ペア生成")
        return matches
    
    def _compute_similarity_matrix(
        self, 
        web_regions: List[Any], 
        pdf_regions: List[Any]
    ) -> Tuple[List[List[float]], List[List[MatchDetail]]]:
        """類似度行列と詳細情報を計算"""
        print(f"📊 類似度行列計算: {len(web_regions)} x {len(pdf_regions)}")
        
        similarity_matrix = []
        detail_matrix = []
        
        for i, web in enumerate(web_regions):
            sim_row = []
            detail_row = []
            web_text = self._get_text(web)
            
            for j, pdf in enumerate(pdf_regions):
                pdf_text = self._get_text(pdf)
                score, detail = self._calculate_enhanced_similarity(web_text, pdf_text)
                sim_row.append(score)
                detail_row.append(detail)
            
            similarity_matrix.append(sim_row)
            detail_matrix.append(detail_row)
            
            if (i + 1) % 10 == 0 or i == len(web_regions) - 1:
                print(f"  進捗: {i+1}/{len(web_regions)}")
        
        return similarity_matrix, detail_matrix
    
    def _calculate_enhanced_similarity(
        self, 
        text1: str, 
        text2: str
    ) -> Tuple[float, MatchDetail]:
        """
        精度向上版の類似度計算
        
        改善点:
        - 正規化処理の強化
        - 文字単位の厳密計算
        - 共通フレーズ抽出
        """
        detail = MatchDetail()
        
        if not text1 or not text2:
            return 0.0, detail
        
        # 正規化 (空白・改行統一、大文字小文字統一)
        t1 = self._normalize_text(text1)
        t2 = self._normalize_text(text2)
        
        if not t1 or not t2:
            return 0.0, detail
        
        # 完全一致チェック
        if t1 == t2:
            detail.char_match_ratio = 1.0
            detail.matched_phrases = [t1]
            return 1.0, detail
        
        # SequenceMatcherで詳細分析
        matcher = difflib.SequenceMatcher(None, t1, t2)
        
        # 一致ブロックを抽出
        matched_chars = 0
        matched_phrases = []
        
        for block in matcher.get_matching_blocks():
            if block.size > 0:
                matched_chars += block.size
                phrase = t1[block.a:block.a + block.size]
                if len(phrase) >= 3:  # 3文字以上のフレーズのみ
                    matched_phrases.append(phrase)
        
        # 文字レベル一致率 (より大きいテキストを基準)
        max_len = max(len(t1), len(t2))
        char_ratio = matched_chars / max_len if max_len > 0 else 0
        
        detail.char_match_ratio = char_ratio
        detail.matched_phrases = matched_phrases
        
        # 不一致部分を抽出
        detail.web_only_phrases = self._extract_unique_parts(t1, t2)
        detail.pdf_only_phrases = self._extract_unique_parts(t2, t1)
        
        # 最終スコア (SequenceMatcher ratio と文字一致率の平均)
        sm_ratio = matcher.ratio()
        final_score = (sm_ratio + char_ratio) / 2
        
        return final_score, detail
    
    def _normalize_text(self, text: str) -> str:
        """テキスト正規化"""
        if not text:
            return ""
        
        # 改行・タブを空白に
        result = re.sub(r'[\r\n\t]+', ' ', text)
        
        # 連続空白を単一に
        result = re.sub(r'\s+', ' ', result)
        
        # 前後の空白除去
        result = result.strip()
        
        # 全角英数を半角に
        result = self._zen_to_han(result)
        
        return result.lower()
    
    def _zen_to_han(self, text: str) -> str:
        """全角英数を半角に変換"""
        result = []
        for char in text:
            code = ord(char)
            # 全角英数字 (Ａ-Ｚ, ａ-ｚ, ０-９)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(char)
        return ''.join(result)
    
    def _extract_unique_parts(self, text1: str, text2: str) -> List[str]:
        """text1にあってtext2にない部分を抽出"""
        unique = []
        matcher = difflib.SequenceMatcher(None, text1, text2)
        
        prev_end = 0
        for block in matcher.get_matching_blocks():
            if block.a > prev_end:
                part = text1[prev_end:block.a].strip()
                if len(part) >= 2:  # 2文字以上
                    unique.append(part)
            prev_end = block.a + block.size
        
        return unique
    
    def _greedy_match(
        self,
        web_regions: List[Any],
        pdf_regions: List[Any],
        similarity_matrix: List[List[float]],
        detail_matrix: List[List[MatchDetail]]
    ) -> List[SyncPair]:
        """貪欲法で最適マッチを選択"""
        print(f"🎯 貪欲法マッチング (閾値: {self.threshold:.0%})")
        
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
            detail = detail_matrix[web_idx][pdf_idx]
            
            pair = SyncPair(
                web_id=self._get_id(web),
                pdf_id=self._get_id(pdf),
                web_text=self._get_text(web),
                pdf_text=self._get_text(pdf),
                similarity=score,
                web_bbox=self._get_bbox(web),
                pdf_bbox=self._get_bbox(pdf),
                match_detail=detail
            )
            matches.append(pair)
            used_web.add(web_idx)
            used_pdf.add(pdf_idx)
            
            print(f"  ✓ {pair.web_id} ↔ {pair.pdf_id}: {score:.1%}")
        
        # マッチしなかった領域も追加
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
    
    def _assign_colors(self, matches: List[SyncPair]):
        """類似度に基づいて色を設定"""
        for pair in matches:
            if pair.similarity >= 0.90:
                pair.sync_color = self.COLOR_EXACT
            elif pair.similarity >= 0.70:
                pair.sync_color = self.COLOR_HIGH
            elif pair.similarity >= 0.50:
                pair.sync_color = self.COLOR_MEDIUM
            elif pair.similarity >= 0.30:
                pair.sync_color = self.COLOR_LOW
            elif pair.similarity > 0:
                pair.sync_color = self.COLOR_MISMATCH
            else:
                pair.sync_color = self.COLOR_UNMATCHED
    
    def _get_text(self, region: Any) -> str:
        if hasattr(region, 'text'):
            return region.text or ""
        return str(region)
    
    def _get_id(self, region: Any) -> str:
        if hasattr(region, 'area_code'):
            return region.area_code or ""
        if hasattr(region, 'id'):
            return str(region.id)
        return ""
    
    def _get_bbox(self, region: Any) -> Optional[tuple]:
        if hasattr(region, 'rect'):
            return region.rect
        if hasattr(region, 'bbox'):
            return region.bbox
        return None
    
    def set_threshold(self, threshold: float):
        self.threshold = threshold
        logger.info(f"Threshold updated to {threshold}")
    
    def __repr__(self):
        return f"EnhancedParagraphMatcher(threshold={self.threshold})"


# 後方互換性のためのエイリアス
ParagraphMatcher = EnhancedParagraphMatcher

__all__ = ["EnhancedParagraphMatcher", "ParagraphMatcher", "SyncPair", "MatchDetail"]
