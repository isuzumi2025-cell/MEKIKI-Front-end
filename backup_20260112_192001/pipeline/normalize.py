"""
Text Normalization Module
全角半角・空白・記号の正規化

Created: 2026-01-11
"""
import re
import unicodedata
from typing import Optional


class TextNormalizer:
    """
    テキスト正規化クラス
    広告検版向けの統一正規化ルール
    """
    
    def __init__(
        self,
        fullwidth_to_halfwidth: bool = True,
        normalize_spaces: bool = True,
        normalize_newlines: bool = True,
        remove_zero_width: bool = True,
        normalize_punctuation: bool = True,
        remove_ruby: bool = False
    ):
        """
        初期化
        
        Args:
            fullwidth_to_halfwidth: 全角英数字を半角に変換
            normalize_spaces: 連続空白を1つに
            normalize_newlines: 改行を空白に
            remove_zero_width: ゼロ幅文字を除去
            normalize_punctuation: 句読点を統一
            remove_ruby: ルビを除去
        """
        self.fullwidth_to_halfwidth = fullwidth_to_halfwidth
        self.normalize_spaces = normalize_spaces
        self.normalize_newlines = normalize_newlines
        self.remove_zero_width = remove_zero_width
        self.normalize_punctuation = normalize_punctuation
        self.remove_ruby = remove_ruby
    
    def normalize(self, text: str) -> str:
        """
        テキストを正規化
        
        Args:
            text: 入力テキスト
            
        Returns:
            正規化されたテキスト
        """
        if not text:
            return ""
        
        result = text
        
        # 1. ゼロ幅文字除去
        if self.remove_zero_width:
            result = self._remove_zero_width(result)
        
        # 2. 全角→半角 (英数字・記号)
        if self.fullwidth_to_halfwidth:
            result = self._fullwidth_to_halfwidth(result)
        
        # 3. 改行正規化
        if self.normalize_newlines:
            result = self._normalize_newlines(result)
        
        # 4. 空白正規化
        if self.normalize_spaces:
            result = self._normalize_spaces(result)
        
        # 5. 句読点正規化
        if self.normalize_punctuation:
            result = self._normalize_punctuation(result)
        
        # 6. ルビ除去
        if self.remove_ruby:
            result = self._remove_ruby(result)
        
        return result.strip()
    
    def _remove_zero_width(self, text: str) -> str:
        """ゼロ幅文字を除去"""
        # Zero-width characters
        zero_width = [
            '\u200b',  # ZERO WIDTH SPACE
            '\u200c',  # ZERO WIDTH NON-JOINER
            '\u200d',  # ZERO WIDTH JOINER
            '\ufeff',  # ZERO WIDTH NO-BREAK SPACE (BOM)
            '\u00ad',  # SOFT HYPHEN
        ]
        for char in zero_width:
            text = text.replace(char, '')
        return text
    
    def _fullwidth_to_halfwidth(self, text: str) -> str:
        """全角英数字・記号を半角に変換"""
        result = []
        for char in text:
            code = ord(char)
            
            # 全角英数字 (！-～) → 半角 (!-~)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            # 全角スペース → 半角スペース
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(char)
        
        return ''.join(result)
    
    def _normalize_newlines(self, text: str) -> str:
        """改行を統一（空白に変換）"""
        # CRLF/CR → LF
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 連続改行を1つの空白に
        text = re.sub(r'\n+', ' ', text)
        return text
    
    def _normalize_spaces(self, text: str) -> str:
        """連続空白を1つに"""
        return re.sub(r'[ \t]+', ' ', text)
    
    def _normalize_punctuation(self, text: str) -> str:
        """句読点を統一"""
        # 全角カンマ・ピリオド → 読点・句点
        replacements = {
            '，': '、',
            '．': '。',
            '‐': '-',  # HYPHEN
            '–': '-',  # EN DASH
            '—': '-',  # EM DASH
            '〜': '～',
            '~': '～',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def _remove_ruby(self, text: str) -> str:
        """ルビ（ふりがな）を除去"""
        # HTML ruby タグ除去
        text = re.sub(r'<ruby>([^<]+)<rp>[（(]</rp><rt>[^<]+</rt><rp>[）)]</rp></ruby>', r'\1', text)
        text = re.sub(r'<ruby>([^<]+)<rt>[^<]+</rt></ruby>', r'\1', text)
        
        # 括弧内のふりがな除去（簡易）
        # 例: 漢字（かんじ） → 漢字
        text = re.sub(r'([一-龥]+)（[ぁ-んァ-ン]+）', r'\1', text)
        text = re.sub(r'([一-龥]+)\([ぁ-んァ-ン]+\)', r'\1', text)
        
        return text


# ========== Pre-configured Normalizers ==========

# 厳密正規化（比較用）
STRICT_NORMALIZER = TextNormalizer(
    fullwidth_to_halfwidth=True,
    normalize_spaces=True,
    normalize_newlines=True,
    remove_zero_width=True,
    normalize_punctuation=True,
    remove_ruby=True
)

# 緩い正規化（表示用）
LOOSE_NORMALIZER = TextNormalizer(
    fullwidth_to_halfwidth=False,
    normalize_spaces=True,
    normalize_newlines=False,
    remove_zero_width=True,
    normalize_punctuation=False,
    remove_ruby=False
)


# ========== Convenience Functions ==========

def normalize_text(text: str, strict: bool = True) -> str:
    """
    テキスト正規化（簡易インターフェース）
    
    Args:
        text: 入力テキスト
        strict: 厳密モード（比較用）
        
    Returns:
        正規化されたテキスト
    """
    normalizer = STRICT_NORMALIZER if strict else LOOSE_NORMALIZER
    return normalizer.normalize(text)


def normalize_for_comparison(text1: str, text2: str) -> tuple:
    """
    比較用に2つのテキストを正規化
    
    Returns:
        (normalized_text1, normalized_text2)
    """
    return normalize_text(text1, strict=True), normalize_text(text2, strict=True)


if __name__ == "__main__":
    # テスト
    test_cases = [
        "　全角スペース　あり",
        "ＡＢＣＤ１２３４",
        "価格：¥１，９８０（税込）",
        "改行\n\nあり\r\nテスト",
        "ゼロ幅\u200b文字\u200cテスト",
        "漢字（かんじ）のルビ",
    ]
    
    normalizer = TextNormalizer()
    
    for test in test_cases:
        normalized = normalizer.normalize(test)
        print(f"'{test}' → '{normalized}'")
