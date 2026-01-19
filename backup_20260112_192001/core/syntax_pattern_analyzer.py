"""
構文パターン分析器

テキストの構文パターンを抽出し、類似度を計算
マルチシグナル融合の補助シグナル (10%)
"""

import re
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class SyntaxPattern:
    """構文パターン"""
    length_class: str       # "short", "medium", "long"
    punct_pattern: str      # 句読点パターン (例: ".,!")
    has_numbers: bool       # 数字を含むか
    has_date: bool          # 日付パターンを含むか
    structure_type: str     # "heading", "body", "list", "caption"
    word_count: int         # 単語/文節数


class SyntaxPatternAnalyzer:
    """
    構文パターン分析器
    
    テキストの構造的特徴を抽出し、パターン比較で類似度を計算
    """
    
    # 文長分類の閾値
    LENGTH_THRESHOLD_SHORT = 20   # 20文字以下 = 短文
    LENGTH_THRESHOLD_MEDIUM = 100  # 100文字以下 = 中文
    
    # 日付パターン
    DATE_PATTERNS = [
        r'\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2}',  # 2024年1月1日 or 2024/1/1
        r'\d{1,2}[月/]\d{1,2}[日]?',            # 1月1日 or 1/1
        r'令和\d+年',                           # 令和5年
        r'平成\d+年',                           # 平成31年
    ]
    
    # 見出しパターン
    HEADING_PATTERNS = [
        r'^[■●◆▶▼★☆]\s*',           # 記号で始まる
        r'^第\d+[章節条項]',           # 第1章
        r'^\d+[\.．]\s*[^\d]',       # 1. で始まる
        r'^[①②③④⑤⑥⑦⑧⑨⑩]',        # 丸数字
    ]
    
    def extract_pattern(self, text: str) -> SyntaxPattern:
        """テキストから構文パターンを抽出"""
        if not text:
            return SyntaxPattern(
                length_class="short",
                punct_pattern="",
                has_numbers=False,
                has_date=False,
                structure_type="body",
                word_count=0
            )
        
        # 文長分類
        length_class = self._classify_length(text)
        
        # 句読点パターン
        punct_pattern = self._extract_punct_pattern(text)
        
        # 数字有無
        has_numbers = bool(re.search(r'\d', text))
        
        # 日付パターン有無
        has_date = self._has_date_pattern(text)
        
        # 構造タイプ
        structure_type = self._detect_structure_type(text)
        
        # 単語数 (日本語は文字数ベースで推定)
        word_count = self._count_words(text)
        
        return SyntaxPattern(
            length_class=length_class,
            punct_pattern=punct_pattern,
            has_numbers=has_numbers,
            has_date=has_date,
            structure_type=structure_type,
            word_count=word_count
        )
    
    def _classify_length(self, text: str) -> str:
        """文長を分類"""
        length = len(text)
        if length <= self.LENGTH_THRESHOLD_SHORT:
            return "short"
        elif length <= self.LENGTH_THRESHOLD_MEDIUM:
            return "medium"
        else:
            return "long"
    
    def _extract_punct_pattern(self, text: str) -> str:
        """句読点パターンを抽出 (順序付き、重複除去)"""
        punct_chars = []
        seen = set()
        for char in text:
            if char in '。、.,:;!?！？…':
                if char not in seen:
                    punct_chars.append(char)
                    seen.add(char)
        return ''.join(punct_chars[:5])  # 最初の5種類まで
    
    def _has_date_pattern(self, text: str) -> bool:
        """日付パターンを含むか"""
        for pattern in self.DATE_PATTERNS:
            if re.search(pattern, text):
                return True
        return False
    
    def _detect_structure_type(self, text: str) -> str:
        """構造タイプを検出"""
        text_stripped = text.strip()
        
        # 見出しパターンをチェック
        for pattern in self.HEADING_PATTERNS:
            if re.match(pattern, text_stripped):
                return "heading"
        
        # リスト項目 (短くて句点なし)
        if len(text_stripped) < 50 and '。' not in text_stripped and '.' not in text_stripped:
            return "list"
        
        # キャプション (短くて括弧を含む)
        if len(text_stripped) < 30 and ('(' in text or '（' in text):
            return "caption"
        
        return "body"
    
    def _count_words(self, text: str) -> int:
        """単語数を推定 (日本語対応)"""
        # スペース区切りがあればそれを使用
        if ' ' in text:
            return len(text.split())
        # なければ文字数を3で割って推定 (日本語の平均単語長)
        return max(1, len(text) // 3)
    
    def compare_patterns(self, pattern1: SyntaxPattern, pattern2: SyntaxPattern) -> float:
        """
        2つのパターン間の類似度を計算 (0.0-1.0)
        """
        scores = []
        
        # 1. 文長分類の一致 (25%)
        if pattern1.length_class == pattern2.length_class:
            scores.append(1.0)
        elif abs(["short", "medium", "long"].index(pattern1.length_class) - 
                 ["short", "medium", "long"].index(pattern2.length_class)) == 1:
            scores.append(0.5)  # 隣接クラスは半分のスコア
        else:
            scores.append(0.0)
        
        # 2. 句読点パターンの類似度 (25%)
        if pattern1.punct_pattern and pattern2.punct_pattern:
            set1 = set(pattern1.punct_pattern)
            set2 = set(pattern2.punct_pattern)
            if set1 | set2:
                punct_score = len(set1 & set2) / len(set1 | set2)
            else:
                punct_score = 1.0
        elif not pattern1.punct_pattern and not pattern2.punct_pattern:
            punct_score = 1.0  # 両方なし = 一致
        else:
            punct_score = 0.0
        scores.append(punct_score)
        
        # 3. 数字/日付の一致 (25%)
        num_match = 1.0 if pattern1.has_numbers == pattern2.has_numbers else 0.0
        date_match = 1.0 if pattern1.has_date == pattern2.has_date else 0.0
        scores.append((num_match + date_match) / 2)
        
        # 4. 構造タイプの一致 (25%)
        if pattern1.structure_type == pattern2.structure_type:
            scores.append(1.0)
        else:
            scores.append(0.0)
        
        # 平均
        return sum(scores) / len(scores)


def compare_syntax(text1: str, text2: str) -> float:
    """
    2つのテキストの構文類似度を計算 (ショートカット関数)
    """
    analyzer = SyntaxPatternAnalyzer()
    p1 = analyzer.extract_pattern(text1)
    p2 = analyzer.extract_pattern(text2)
    return analyzer.compare_patterns(p1, p2)
