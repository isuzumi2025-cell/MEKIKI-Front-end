"""
TextNormalizer - 日本語テキストの正規化

Phase 1.9.3: 日本語正規化レイヤ
- Unicode NFKC正規化
- 全角/半角統一
- 記号ゆれ統一
- マッチング用の積極的正規化
"""
import unicodedata
import re
from typing import Optional


class TextNormalizer:
    """
    日本語テキストの正規化
    
    マッチング精度向上のため、表記ゆれを吸収する
    """
    
    # 記号ゆれマッピング
    SYMBOL_MAP = {
        '～': '〜', '−': '-', '－': '-', '―': '-', '─': '-',
        '（': '(', '）': ')', '「': '"', '」': '"',
        '『': '"', '』': '"', '【': '[', '】': ']',
        '〈': '<', '〉': '>', '《': '<', '》': '>',
        '：': ':', '；': ';', '，': ',', '．': '.',
        '！': '!', '？': '?', '　': ' ',  # 全角スペース
        '･': '・', '／': '/', '＼': '\\',
    }
    
    # 句読点パターン
    PUNCTUATION_PATTERN = re.compile(r'[。、,.!?！？…]')
    
    # 日本語文字パターン
    JA_CHAR_PATTERN = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
    
    def __init__(self):
        # 置換テーブルを事前構築
        self._symbol_table = str.maketrans(self.SYMBOL_MAP)
    
    def normalize(self, text: str, mode: str = "default") -> str:
        """
        テキストを正規化
        
        Args:
            text: 入力テキスト
            mode: 
                - "default": スペース保持、基本正規化
                - "compact": 日本語間スペース除去
                - "strict": 全スペース除去
        
        Returns:
            正規化されたテキスト
        """
        if not text:
            return ""
        
        # 1. Unicode NFKC正規化（全角→半角、濁点結合など）
        text = unicodedata.normalize('NFKC', text)
        
        # 2. 記号ゆれ統一
        text = text.translate(self._symbol_table)
        
        # 3. 空白正規化
        if mode == "strict":
            # 全スペース除去
            text = re.sub(r'\s+', '', text)
        elif mode == "compact":
            # 日本語文字間のスペースを除去
            text = self._remove_ja_spaces(text)
            text = re.sub(r'\s+', ' ', text)
        else:
            # 連続スペースを1つに
            text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _remove_ja_spaces(self, text: str) -> str:
        """日本語文字間のスペースを除去"""
        # 日本語-スペース-日本語 のパターンを置換
        ja_space_pattern = re.compile(
            r'([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])'
            r'\s+'
            r'([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])'
        )
        
        # 複数回適用（ネストしたパターン対応）
        prev = None
        while prev != text:
            prev = text
            text = ja_space_pattern.sub(r'\1\2', text)
        
        return text
    
    def normalize_for_matching(self, text: str) -> str:
        """
        マッチング用の積極的正規化
        
        句読点や記号も除去し、純粋なテキスト比較を可能にする
        """
        # まず基本正規化
        text = self.normalize(text, mode="compact")
        
        # 句読点除去
        text = self.PUNCTUATION_PATTERN.sub('', text)
        
        # 括弧類も除去
        text = re.sub(r'[()（）\[\]【】「」『』<>〈〉《》]', '', text)
        
        # 残りのスペースも除去
        text = re.sub(r'\s+', '', text)
        
        return text
    
    def normalize_for_display(self, text: str) -> str:
        """
        表示用の緩やかな正規化
        
        読みやすさを維持しつつ、明らかな表記ゆれのみ吸収
        """
        return self.normalize(text, mode="default")
    
    def get_hiragana_ratio(self, text: str) -> float:
        """ひらがなの割合を取得"""
        if not text:
            return 0.0
        
        hiragana = len(re.findall(r'[\u3040-\u309F]', text))
        total = len(text.replace(' ', ''))
        
        return hiragana / max(total, 1)
    
    def is_hiragana_dominant(self, text: str, threshold: float = 0.7) -> bool:
        """ひらがな主体かどうか判定"""
        return self.get_hiragana_ratio(text) >= threshold


# デフォルトインスタンス
_default_normalizer: Optional[TextNormalizer] = None

def get_text_normalizer() -> TextNormalizer:
    """デフォルトTextNormalizerを取得"""
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = TextNormalizer()
    return _default_normalizer
