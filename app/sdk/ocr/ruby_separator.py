"""
RubySeparator - ルビ(ふりがな)分離ノーマライザー

Phase 2.0-P0: ルビを本文から分離してマッチング精度を向上
- 括弧形式: 漢字（ふりがな）、漢字《ふりがな》
- HTML形式: <ruby>漢字<rt>ふりがな</rt></ruby>
- PDF抽出時の縦書きルビ推定
"""
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class RubyAnnotation:
    """ルビ情報"""
    base_text: str      # 親文字（漢字等）
    ruby_text: str      # ルビ（ふりがな）
    start_pos: int      # 原文での開始位置
    end_pos: int        # 原文での終了位置


@dataclass
class SeparationResult:
    """分離結果"""
    plain_text: str                 # ルビを除去した本文
    rubies: List[RubyAnnotation]    # 抽出されたルビ一覧
    ruby_included_text: str         # ルビを括弧形式で含めた文


class RubySeparator:
    """
    ルビ（ふりがな）を本文から分離するノーマライザー
    
    対応形式:
    - 括弧形式: 漢字（ふりがな）、漢字《ふりがな》、漢字(ふりがな)
    - HTML ruby形式: <ruby>漢字<rt>ふりがな</rt></ruby>
    - OCR推定: 小さいひらがなが漢字の上/右に配置されている場合
    """
    
    # 括弧形式のルビパターン
    PAREN_RUBY_PATTERNS = [
        # 全角丸括弧: 漢字（ふりがな）
        re.compile(r'([一-龯々]{1,10})（([ぁ-んァ-ヶー]+)）'),
        # 二重山括弧: 漢字《ふりがな》
        re.compile(r'([一-龯々]{1,10})《([ぁ-んァ-ヶー]+)》'),
        # 半角丸括弧: 漢字(ふりがな)
        re.compile(r'([一-龯々]{1,10})\(([ぁ-んァ-ヶー]+)\)'),
        # 隅付き括弧: 漢字【ふりがな】（稀）
        re.compile(r'([一-龯々]{1,10})【([ぁ-んァ-ヶー]+)】'),
    ]
    
    # HTML rubyパターン
    HTML_RUBY_PATTERN = re.compile(
        r'<ruby>([^<]+)<r[pt]>([^<]+)</r[pt]></ruby>',
        re.IGNORECASE
    )
    
    # ひらがなパターン
    HIRAGANA_PATTERN = re.compile(r'[\u3041-\u3096]')
    
    # カタカナパターン
    KATAKANA_PATTERN = re.compile(r'[\u30A1-\u30F6]')
    
    # 漢字パターン
    KANJI_PATTERN = re.compile(r'[一-龯々]')
    
    def __init__(self, detect_ocr_ruby: bool = False):
        """
        Args:
            detect_ocr_ruby: OCRによる位置ベースルビ推定を有効にするか
        """
        self.detect_ocr_ruby = detect_ocr_ruby
    
    def separate(self, text: str) -> SeparationResult:
        """
        テキストからルビを分離
        
        Args:
            text: 処理対象テキスト
        
        Returns:
            SeparationResult: 分離結果
        """
        if not text:
            return SeparationResult(
                plain_text="",
                rubies=[],
                ruby_included_text=""
            )
        
        rubies: List[RubyAnnotation] = []
        working_text = text
        
        # 1. HTML ruby形式の処理
        working_text, html_rubies = self._extract_html_ruby(working_text)
        rubies.extend(html_rubies)
        
        # 2. 括弧形式のルビ処理
        working_text, paren_rubies = self._extract_paren_ruby(working_text)
        rubies.extend(paren_rubies)
        
        # プレーンテキストの正規化（余分な空白を削除）
        plain_text = re.sub(r'\s+', ' ', working_text).strip()
        
        # ルビ込みテキストを再構築（括弧形式）
        ruby_included = self._rebuild_with_ruby(plain_text, rubies)
        
        return SeparationResult(
            plain_text=plain_text,
            rubies=rubies,
            ruby_included_text=ruby_included
        )
    
    def _extract_html_ruby(self, text: str) -> Tuple[str, List[RubyAnnotation]]:
        """HTML ruby形式を抽出"""
        rubies = []
        
        def replace_ruby(match):
            base = match.group(1)
            ruby = match.group(2)
            rubies.append(RubyAnnotation(
                base_text=base,
                ruby_text=ruby,
                start_pos=match.start(),
                end_pos=match.end()
            ))
            return base  # 親文字のみ残す
        
        result = self.HTML_RUBY_PATTERN.sub(replace_ruby, text)
        return result, rubies
    
    def _extract_paren_ruby(self, text: str) -> Tuple[str, List[RubyAnnotation]]:
        """括弧形式のルビを抽出"""
        rubies = []
        result = text
        
        for pattern in self.PAREN_RUBY_PATTERNS:
            matches = list(pattern.finditer(result))
            # 後ろからマッチを処理（位置ズレ防止）
            for match in reversed(matches):
                base = match.group(1)
                ruby = match.group(2)
                rubies.append(RubyAnnotation(
                    base_text=base,
                    ruby_text=ruby,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
                # 親文字のみに置換
                result = result[:match.start()] + base + result[match.end():]
        
        return result, rubies
    
    def _rebuild_with_ruby(self, plain_text: str, rubies: List[RubyAnnotation]) -> str:
        """ルビを括弧形式で再付与"""
        if not rubies:
            return plain_text
        
        # 簡易実装: 元のテキストにルビが含まれていた場合、
        # 親文字を見つけてルビを再付与
        result = plain_text
        for ruby in rubies:
            # 親文字を探してルビを付与
            base = ruby.base_text
            ruby_text = ruby.ruby_text
            if base in result:
                result = result.replace(base, f"{base}（{ruby_text}）", 1)
        
        return result
    
    def get_plain_text(self, text: str) -> str:
        """ルビを除去したプレーンテキストを取得（簡易API）"""
        return self.separate(text).plain_text
    
    def normalize_for_matching(self, text: str) -> str:
        """
        マッチング用に正規化
        - ルビを除去
        - 空白を正規化
        - 全角/半角を統一
        """
        result = self.get_plain_text(text)
        
        # 空白の正規化
        result = re.sub(r'\s+', '', result)
        
        # 全角英数を半角に
        result = self._normalize_width(result)
        
        return result
    
    def _normalize_width(self, text: str) -> str:
        """全角英数を半角に変換"""
        # 全角英字 → 半角
        result = ""
        for char in text:
            code = ord(char)
            # 全角英大文字 (Ａ-Ｚ)
            if 0xFF21 <= code <= 0xFF3A:
                result += chr(code - 0xFF21 + 0x41)
            # 全角英小文字 (ａ-ｚ)
            elif 0xFF41 <= code <= 0xFF5A:
                result += chr(code - 0xFF41 + 0x61)
            # 全角数字 (０-９)
            elif 0xFF10 <= code <= 0xFF19:
                result += chr(code - 0xFF10 + 0x30)
            else:
                result += char
        return result
    
    def detect_hiragana_dominant(self, text: str) -> bool:
        """
        ひらがな優位テキストを検知
        
        Returns:
            True if hiragana ratio > 50%
        """
        if not text:
            return False
        
        # 空白・句読点を除いた文字数
        chars_only = re.sub(r'[\s\u3000。、．，.!?！？「」『』（）\(\)]', '', text)
        if not chars_only:
            return False
        
        hiragana_count = len(self.HIRAGANA_PATTERN.findall(chars_only))
        total_chars = len(chars_only)
        
        return (hiragana_count / total_chars) > 0.5


# ====== ユーティリティ関数 ======

_default_separator: Optional[RubySeparator] = None

def get_ruby_separator() -> RubySeparator:
    """デフォルトのRubySeparatorを取得"""
    global _default_separator
    if _default_separator is None:
        _default_separator = RubySeparator()
    return _default_separator


def separate_ruby(text: str) -> SeparationResult:
    """ルビを分離（ショートカット）"""
    return get_ruby_separator().separate(text)


def normalize_for_matching(text: str) -> str:
    """マッチング用に正規化（ショートカット）"""
    return get_ruby_separator().normalize_for_matching(text)


def detect_hiragana_dominant(text: str) -> bool:
    """ひらがな優位テキストを検知（ショートカット）"""
    return get_ruby_separator().detect_hiragana_dominant(text)
