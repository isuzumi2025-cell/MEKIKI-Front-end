"""
TextFilter - 文字種対応のインテリジェントフィルタ

Phase 1.9.1: 5文字フィルタの置換
- 文字種×信頼度×bbox の複合条件
- 日本語は2-3文字、ラテン文字は4-5文字を基本閾値
- 高信頼度/大面積の短語は保持

Phase 2.0-P0: ひらがな長文対応
- ひらがな優位テキスト検知
- 特別なマッチングロジック適用のトリガー
"""
import re
from dataclasses import dataclass
from typing import Tuple, Optional, List


@dataclass
class FilterConfig:
    """フィルタ設定"""
    min_chars_ja: int = 2        # 日本語最小文字数
    min_chars_latin: int = 4     # ラテン文字最小文字数
    min_confidence: float = 0.5  # 最小信頼度
    min_bbox_area: int = 500     # 最小bbox面積 (px^2)
    high_confidence: float = 0.85  # 高信頼度閾値（短くても保持）
    large_area_multiplier: float = 2.0  # 大面積判定倍率


class TextFilter:
    """
    文字種対応のインテリジェントテキストフィルタ
    
    単純な文字数閾値ではなく、以下を考慮:
    - 文字種（日本語 vs ラテン文字）
    - OCR信頼度
    - bbox面積（大きく表示されている = 重要）
    
    Phase 2.0-P0: ひらがな優位テキスト検知
    - ひらがなが50%以上を占める場合、特別なマッチング適用
    """
    
    # 日本語文字パターン（ひらがな、カタカナ、漢字）
    JA_PATTERN = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
    
    # ひらがなのみパターン（Phase 2.0-P0）
    HIRAGANA_PATTERN = re.compile(r'[\u3041-\u3096]')
    
    # ノイズパターン（数字・記号のみ）
    NOISE_PATTERN = re.compile(r'^[\d\s\-_.,:;()【】「」『』（）\[\]<>]+$')
    
    # 型番・日付パターン（ノイズから除外）
    VALID_PATTERN = re.compile(r'\d{2,}[-/]\d+|[A-Z]{2,}-?\d+')
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
    
    @classmethod
    def detect_hiragana_dominant(cls, text: str) -> bool:
        """
        ひらがな優位テキストを検知
        
        Phase 2.0-P0: ひらがなが50%以上を占めるテキストを検出
        これにより、特別なマッチングロジック（サブストリングマッチ等）を適用
        
        Args:
            text: 判定対象テキスト
            
        Returns:
            True if hiragana ratio > 50%
        """
        if not text:
            return False
        
        # 空白・句読点を除外して純粋な文字のみカウント
        chars_only = re.sub(r'[\s\u3000。、．，.!?！？「」『』（）\(\)\n\r]', '', text)
        if not chars_only:
            return False
        
        hiragana_count = len(cls.HIRAGANA_PATTERN.findall(chars_only))
        total_chars = len(chars_only)
        
        return (hiragana_count / total_chars) > 0.5
    
    def should_keep(
        self, 
        text: str, 
        confidence: float, 
        bbox: Tuple[int, int, int, int]
    ) -> Tuple[bool, Optional[str]]:
        """
        テキストを保持すべきか判定
        
        Args:
            text: 対象テキスト
            confidence: OCR信頼度 (0.0-1.0)
            bbox: バウンディングボックス [x1, y1, x2, y2]
        
        Returns:
            (should_keep, drop_reason): 保持ならTrue, 落とすならFalseとその理由
        """
        text = text.strip()
        
        # 空テキストチェック
        if not text:
            return False, "empty"
        
        # ノイズパターン（数字・記号のみ）
        if self.NOISE_PATTERN.match(text):
            # ただし型番・日付パターンは許可
            if not self.VALID_PATTERN.search(text):
                return False, "noise_only"
        
        # bbox面積計算
        x1, y1, x2, y2 = bbox
        area = max(0, (x2 - x1) * (y2 - y1))
        
        # 高信頼度なら短くても保持
        if confidence >= self.config.high_confidence:
            return True, None
        
        # 大面積なら短くても保持（大きく表示されている = 重要）
        if area >= self.config.min_bbox_area * self.config.large_area_multiplier:
            return True, None
        
        # 文字種判定
        ja_chars = len(self.JA_PATTERN.findall(text))
        total_chars = len(text)
        
        if total_chars == 0:
            return False, "empty_after_strip"
        
        ja_ratio = ja_chars / total_chars
        
        if ja_ratio >= 0.5:
            # 日本語主体
            min_len = self.config.min_chars_ja
            char_type = "ja"
        else:
            # ラテン文字主体
            min_len = self.config.min_chars_latin
            char_type = "latin"
        
        # 文字数チェック
        if total_chars < min_len:
            return False, f"min_length_{char_type}_{min_len}"
        
        # 信頼度チェック
        if confidence < self.config.min_confidence:
            return False, "low_confidence"
        
        return True, None
    
    def filter_tokens(
        self, 
        tokens: List[dict]
    ) -> Tuple[List[dict], List[dict]]:
        """
        トークンリストをフィルタリング
        
        Args:
            tokens: [{"text": str, "rect": [x1,y1,x2,y2], "confidence": float}, ...]
        
        Returns:
            (kept_tokens, dropped_tokens)
        """
        kept = []
        dropped = []
        
        for token in tokens:
            text = token.get("text", "")
            confidence = token.get("confidence", 0.8)  # デフォルト信頼度
            bbox = token.get("rect", [0, 0, 100, 100])
            
            should_keep, reason = self.should_keep(text, confidence, tuple(bbox))
            
            if should_keep:
                kept.append(token)
            else:
                dropped.append({**token, "drop_reason": reason})
        
        return kept, dropped


# デフォルトインスタンス
_default_filter: Optional[TextFilter] = None

def get_text_filter() -> TextFilter:
    """デフォルトTextFilterを取得"""
    global _default_filter
    if _default_filter is None:
        _default_filter = TextFilter()
    return _default_filter
