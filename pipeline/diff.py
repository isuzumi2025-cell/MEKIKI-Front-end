"""
Diff Classification Module
テキスト/フィールド/テーブル差分の分類

Created: 2026-01-11
"""
import difflib
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid


class DiffType(str, Enum):
    SAME = "SAME"
    TEXT_DIFF = "text_diff"
    FIELD_DIFF = "field_diff"
    TABLE_DIFF = "table_diff"
    MISSING = "missing"
    ADDED = "added"


class DiffSubType(str, Enum):
    # Text diff subtypes
    WHITESPACE_ONLY = "whitespace_only"
    PUNCTUATION_ONLY = "punctuation_only"
    CASE_ONLY = "case_only"
    CONTENT_CHANGE = "content_change"
    
    # Field diff subtypes
    PRICE_CHANGE = "price_change"
    DATE_CHANGE = "date_change"
    URL_CHANGE = "url_change"
    
    # Table diff subtypes
    ROW_ADDED = "row_added"
    ROW_REMOVED = "row_removed"
    COL_ADDED = "col_added"
    COL_REMOVED = "col_removed"
    CELL_CHANGE = "cell_change"


@dataclass
class DiffResult:
    """差分結果"""
    diff_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    diff_type: DiffType = DiffType.SAME
    sub_type: Optional[DiffSubType] = None
    left_text: str = ""
    right_text: str = ""
    diff_html: str = ""
    changed_chars: int = 0
    similarity: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


class DiffClassifier:
    """
    差分分類器
    テキスト/フィールド/テーブルの差分を分類
    """
    
    def __init__(self):
        """初期化"""
        pass
    
    def classify_text_diff(
        self,
        left_text: str,
        right_text: str,
        normalize: bool = True
    ) -> DiffResult:
        """
        テキスト差分を分類
        
        Args:
            left_text: 左側テキスト
            right_text: 右側テキスト
            normalize: 事前正規化するか
            
        Returns:
            DiffResult
        """
        result = DiffResult(
            left_text=left_text,
            right_text=right_text
        )
        
        # 正規化
        if normalize:
            left_norm = self._normalize(left_text)
            right_norm = self._normalize(right_text)
        else:
            left_norm = left_text
            right_norm = right_text
        
        # 完全一致
        if left_norm == right_norm:
            result.diff_type = DiffType.SAME
            result.similarity = 1.0
            return result
        
        # 差分分類
        result.diff_type = DiffType.TEXT_DIFF
        result.similarity = difflib.SequenceMatcher(None, left_norm, right_norm).ratio()
        
        # サブタイプ判定
        if self._is_whitespace_only(left_text, right_text):
            result.sub_type = DiffSubType.WHITESPACE_ONLY
        elif self._is_punctuation_only(left_text, right_text):
            result.sub_type = DiffSubType.PUNCTUATION_ONLY
        elif self._is_case_only(left_text, right_text):
            result.sub_type = DiffSubType.CASE_ONLY
        else:
            result.sub_type = DiffSubType.CONTENT_CHANGE
        
        # 差分HTML生成
        result.diff_html = self._generate_diff_html(left_text, right_text)
        
        # 変更文字数
        result.changed_chars = self._count_changed_chars(left_text, right_text)
        
        return result
    
    def classify_field_diff(
        self,
        left_field: Dict[str, Any],
        right_field: Dict[str, Any]
    ) -> DiffResult:
        """
        フィールド差分を分類
        
        Args:
            left_field: 左側フィールド {type, raw, value_norm}
            right_field: 右側フィールド
            
        Returns:
            DiffResult
        """
        result = DiffResult(
            left_text=left_field.get("raw", ""),
            right_text=right_field.get("raw", "")
        )
        
        left_norm = left_field.get("value_norm", "")
        right_norm = right_field.get("value_norm", "")
        
        # 正規化済み値で比較
        if left_norm == right_norm:
            result.diff_type = DiffType.SAME
            result.similarity = 1.0
            return result
        
        result.diff_type = DiffType.FIELD_DIFF
        result.similarity = difflib.SequenceMatcher(None, left_norm, right_norm).ratio()
        
        # フィールドタイプに基づくサブタイプ
        field_type = left_field.get("type", right_field.get("type", ""))
        if field_type == "price":
            result.sub_type = DiffSubType.PRICE_CHANGE
        elif field_type == "date":
            result.sub_type = DiffSubType.DATE_CHANGE
        elif field_type == "url":
            result.sub_type = DiffSubType.URL_CHANGE
        else:
            result.sub_type = DiffSubType.CONTENT_CHANGE
        
        result.details = {
            "field_type": field_type,
            "left_norm": left_norm,
            "right_norm": right_norm
        }
        
        return result
    
    def classify_missing(self, left_text: str) -> DiffResult:
        """左にあって右にない（削除）"""
        return DiffResult(
            diff_type=DiffType.MISSING,
            left_text=left_text,
            right_text="",
            similarity=0.0
        )
    
    def classify_added(self, right_text: str) -> DiffResult:
        """右にあって左にない（追加）"""
        return DiffResult(
            diff_type=DiffType.ADDED,
            left_text="",
            right_text=right_text,
            similarity=0.0
        )
    
    def _normalize(self, text: str) -> str:
        """簡易正規化"""
        # 空白・改行を統一
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _is_whitespace_only(self, text1: str, text2: str) -> bool:
        """空白のみの差分か"""
        return re.sub(r'\s+', '', text1) == re.sub(r'\s+', '', text2)
    
    def _is_punctuation_only(self, text1: str, text2: str) -> bool:
        """句読点のみの差分か"""
        pattern = r'[、。,.!?！？・：:；;「」『』（）()【】\[\]{}]'
        return re.sub(pattern, '', text1) == re.sub(pattern, '', text2)
    
    def _is_case_only(self, text1: str, text2: str) -> bool:
        """英字の大文字小文字のみの差分か"""
        return text1.lower() == text2.lower()
    
    def _generate_diff_html(self, text1: str, text2: str) -> str:
        """差分HTML生成"""
        differ = difflib.HtmlDiff()
        
        # 簡易版: 行単位ではなく文字単位
        matcher = difflib.SequenceMatcher(None, text1, text2)
        
        html_parts = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                html_parts.append(text1[i1:i2])
            elif tag == 'replace':
                html_parts.append(f'<del style="background:#fcc">{text1[i1:i2]}</del>')
                html_parts.append(f'<ins style="background:#cfc">{text2[j1:j2]}</ins>')
            elif tag == 'delete':
                html_parts.append(f'<del style="background:#fcc">{text1[i1:i2]}</del>')
            elif tag == 'insert':
                html_parts.append(f'<ins style="background:#cfc">{text2[j1:j2]}</ins>')
        
        return ''.join(html_parts)
    
    def _count_changed_chars(self, text1: str, text2: str) -> int:
        """変更文字数をカウント"""
        matcher = difflib.SequenceMatcher(None, text1, text2)
        changed = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                changed += max(i2 - i1, j2 - j1)
        return changed


# ========== Convenience Functions ==========

def classify_diff(
    left_text: str,
    right_text: str,
    is_field: bool = False,
    field_type: Optional[str] = None
) -> DiffResult:
    """
    差分分類（簡易インターフェース）
    """
    classifier = DiffClassifier()
    
    if is_field:
        return classifier.classify_field_diff(
            {"type": field_type, "raw": left_text, "value_norm": left_text},
            {"type": field_type, "raw": right_text, "value_norm": right_text}
        )
    else:
        return classifier.classify_text_diff(left_text, right_text)


def get_diff_summary(result: DiffResult) -> str:
    """差分サマリー文字列を生成"""
    if result.diff_type == DiffType.SAME:
        return "一致"
    elif result.diff_type == DiffType.MISSING:
        return f"削除: {result.left_text[:30]}..."
    elif result.diff_type == DiffType.ADDED:
        return f"追加: {result.right_text[:30]}..."
    elif result.sub_type == DiffSubType.WHITESPACE_ONLY:
        return "空白のみの差分"
    elif result.sub_type == DiffSubType.PUNCTUATION_ONLY:
        return "句読点のみの差分"
    else:
        return f"差分あり ({result.similarity:.0%}一致)"


if __name__ == "__main__":
    # テスト
    classifier = DiffClassifier()
    
    test_cases = [
        ("完全に同じテキスト", "完全に同じテキスト"),
        ("価格：1,980円", "価格：1,880円"),
        ("サンプル テキスト", "サンプルテキスト"),
        ("テスト。テスト", "テストテスト"),
    ]
    
    for left, right in test_cases:
        result = classifier.classify_text_diff(left, right)
        print(f"'{left}' vs '{right}'")
        print(f"  Type: {result.diff_type.value}, Sub: {result.sub_type}")
        print(f"  Similarity: {result.similarity:.2f}")
        print()
