"""
構造化フィールド抽出
価格/日付/URL/割合/寸法/型番/電話等を個別抽出

Created: 2026-01-11
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ExtractedField:
    """抽出されたフィールド"""
    field_type: str  # price, date, percent, url, phone, sku, dimension, etc.
    raw: str         # 元のテキスト
    value_norm: str  # 正規化済み値
    unit_norm: Optional[str] = None
    currency_norm: Optional[str] = None
    span: Optional[tuple] = None  # (start, end) in original text
    confidence: float = 1.0


class FieldsExtractor:
    """
    構造化フィールド抽出器
    テキストから価格・日付・URL等を抽出し正規化
    """
    
    # ========== Regex Patterns ==========
    
    # 価格パターン
    PRICE_PATTERNS = [
        # ¥1,234 / ￥1234 / 1,234円
        r'[¥￥]\s*[\d,]+(?:\.\d+)?',
        r'[\d,]+\s*円',
        r'[\d,]+\s*(?:税込|税抜|税別)',
        # 1,234yen / 1234YEN
        r'[\d,]+\s*(?:yen|YEN)',
    ]
    
    # 日付パターン
    DATE_PATTERNS = [
        # 2024年1月15日
        r'\d{4}年\d{1,2}月\d{1,2}日',
        # 2024/1/15, 2024-01-15
        r'\d{4}[/\-]\d{1,2}[/\-]\d{1,2}',
        # 令和6年1月15日
        r'(?:令和|平成|昭和)\d{1,2}年\d{1,2}月\d{1,2}日',
        # 1月15日
        r'\d{1,2}月\d{1,2}日',
        # 1/15（月）
        r'\d{1,2}/\d{1,2}\s*[\(（][月火水木金土日][\)）]',
    ]
    
    # URL パターン
    URL_PATTERN = r'https?://[^\s<>"{}|\\^`\[\]]+'
    
    # メール パターン
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # 電話番号 パターン
    PHONE_PATTERNS = [
        r'\d{2,4}[\-\s]\d{2,4}[\-\s]\d{3,4}',  # 03-1234-5678
        r'0\d{9,10}',  # 0312345678
        r'\d{3}[\-\s]\d{4}',  # 0120-1234 (短縮)
    ]
    
    # 割合 パターン
    PERCENT_PATTERNS = [
        r'\d+(?:\.\d+)?%',
        r'\d+(?:\.\d+)?パーセント',
        r'\d+割(?:\d+分)?',
    ]
    
    # 寸法 パターン
    DIMENSION_PATTERNS = [
        r'\d+(?:\.\d+)?\s*(?:mm|cm|m|km|g|kg|ml|L|リットル)',
        r'W?\d+\s*[×xX]\s*H?\d+\s*(?:[×xX]\s*D?\d+)?(?:\s*mm)?',  # W100×H200mm
    ]
    
    # 型番 パターン
    SKU_PATTERNS = [
        r'[A-Z]{2,}\-?\d{3,}[A-Z]?',  # ABC-1234, XY5678
        r'\d{6,}',  # 長い数字列（JANコード等）
    ]
    
    # 法務参照 (※1, ※2 等)
    LEGAL_REF_PATTERN = r'※\d+'
    
    def __init__(self):
        """初期化"""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """正規表現をコンパイル"""
        self.price_re = re.compile('|'.join(self.PRICE_PATTERNS))
        self.date_re = re.compile('|'.join(self.DATE_PATTERNS))
        self.url_re = re.compile(self.URL_PATTERN)
        self.email_re = re.compile(self.EMAIL_PATTERN)
        self.phone_re = re.compile('|'.join(self.PHONE_PATTERNS))
        self.percent_re = re.compile('|'.join(self.PERCENT_PATTERNS))
        self.dimension_re = re.compile('|'.join(self.DIMENSION_PATTERNS))
        self.sku_re = re.compile('|'.join(self.SKU_PATTERNS))
        self.legal_ref_re = re.compile(self.LEGAL_REF_PATTERN)
    
    def extract_all(self, text: str) -> List[ExtractedField]:
        """
        テキストから全ての構造化フィールドを抽出
        
        Args:
            text: 入力テキスト
            
        Returns:
            ExtractedFieldのリスト
        """
        fields = []
        
        # 価格
        fields.extend(self._extract_prices(text))
        
        # 日付
        fields.extend(self._extract_dates(text))
        
        # URL
        fields.extend(self._extract_urls(text))
        
        # メール
        fields.extend(self._extract_emails(text))
        
        # 電話
        fields.extend(self._extract_phones(text))
        
        # 割合
        fields.extend(self._extract_percents(text))
        
        # 寸法
        fields.extend(self._extract_dimensions(text))
        
        # 型番
        fields.extend(self._extract_skus(text))
        
        # 法務参照
        fields.extend(self._extract_legal_refs(text))
        
        return fields
    
    def _extract_prices(self, text: str) -> List[ExtractedField]:
        """価格抽出"""
        results = []
        for match in self.price_re.finditer(text):
            raw = match.group()
            value_norm, currency = self._normalize_price(raw)
            results.append(ExtractedField(
                field_type="price",
                raw=raw,
                value_norm=value_norm,
                currency_norm=currency,
                span=(match.start(), match.end())
            ))
        return results
    
    def _normalize_price(self, raw: str) -> tuple:
        """価格正規化"""
        # 通貨記号除去、カンマ除去
        value = re.sub(r'[¥￥円,\s]', '', raw)
        value = re.sub(r'(?:税込|税抜|税別|yen|YEN)', '', value)
        
        # 通貨判定
        currency = "JPY"
        
        return value, currency
    
    def _extract_dates(self, text: str) -> List[ExtractedField]:
        """日付抽出"""
        results = []
        for match in self.date_re.finditer(text):
            raw = match.group()
            value_norm = self._normalize_date(raw)
            results.append(ExtractedField(
                field_type="date",
                raw=raw,
                value_norm=value_norm,
                span=(match.start(), match.end())
            ))
        return results
    
    def _normalize_date(self, raw: str) -> str:
        """日付正規化（西暦ISO形式へ）"""
        # 和暦変換
        wareki_map = {"令和": 2018, "平成": 1988, "昭和": 1925}
        for era, base in wareki_map.items():
            if era in raw:
                year_match = re.search(rf'{era}(\d+)年', raw)
                if year_match:
                    year = base + int(year_match.group(1))
                    raw = raw.replace(f'{era}{year_match.group(1)}年', f'{year}年')
        
        # YYYY年MM月DD日 → YYYY-MM-DD
        match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', raw)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        
        # YYYY/MM/DD → YYYY-MM-DD
        match = re.search(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', raw)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        
        return raw
    
    def _extract_urls(self, text: str) -> List[ExtractedField]:
        """URL抽出"""
        results = []
        for match in self.url_re.finditer(text):
            raw = match.group()
            # 正規化: trailing slashを除去
            value_norm = raw.rstrip('/')
            results.append(ExtractedField(
                field_type="url",
                raw=raw,
                value_norm=value_norm,
                span=(match.start(), match.end())
            ))
        return results
    
    def _extract_emails(self, text: str) -> List[ExtractedField]:
        """メール抽出"""
        results = []
        for match in self.email_re.finditer(text):
            raw = match.group()
            results.append(ExtractedField(
                field_type="email",
                raw=raw,
                value_norm=raw.lower(),  # 小文字化
                span=(match.start(), match.end())
            ))
        return results
    
    def _extract_phones(self, text: str) -> List[ExtractedField]:
        """電話番号抽出"""
        results = []
        for match in self.phone_re.finditer(text):
            raw = match.group()
            # ハイフン・スペース除去で正規化
            value_norm = re.sub(r'[\-\s]', '', raw)
            results.append(ExtractedField(
                field_type="phone",
                raw=raw,
                value_norm=value_norm,
                span=(match.start(), match.end())
            ))
        return results
    
    def _extract_percents(self, text: str) -> List[ExtractedField]:
        """割合抽出"""
        results = []
        for match in self.percent_re.finditer(text):
            raw = match.group()
            value_norm = self._normalize_percent(raw)
            results.append(ExtractedField(
                field_type="percent",
                raw=raw,
                value_norm=value_norm,
                unit_norm="%",
                span=(match.start(), match.end())
            ))
        return results
    
    def _normalize_percent(self, raw: str) -> str:
        """割合正規化"""
        # XX% → XX
        if '%' in raw or 'パーセント' in raw:
            return re.sub(r'[%パーセント]', '', raw)
        
        # X割Y分 → XX
        match = re.search(r'(\d+)割(?:(\d+)分)?', raw)
        if match:
            wari = int(match.group(1)) * 10
            bu = int(match.group(2)) if match.group(2) else 0
            return str(wari + bu)
        
        return raw
    
    def _extract_dimensions(self, text: str) -> List[ExtractedField]:
        """寸法抽出"""
        results = []
        for match in self.dimension_re.finditer(text):
            raw = match.group()
            # 単位を抽出
            unit_match = re.search(r'(mm|cm|m|km|g|kg|ml|L|リットル)', raw)
            unit = unit_match.group(1) if unit_match else None
            
            results.append(ExtractedField(
                field_type="dimension",
                raw=raw,
                value_norm=raw,
                unit_norm=unit,
                span=(match.start(), match.end())
            ))
        return results
    
    def _extract_skus(self, text: str) -> List[ExtractedField]:
        """型番抽出"""
        results = []
        for match in self.sku_re.finditer(text):
            raw = match.group()
            results.append(ExtractedField(
                field_type="sku",
                raw=raw,
                value_norm=raw.upper(),  # 大文字化
                span=(match.start(), match.end())
            ))
        return results
    
    def _extract_legal_refs(self, text: str) -> List[ExtractedField]:
        """法務参照（※1等）抽出"""
        results = []
        for match in self.legal_ref_re.finditer(text):
            raw = match.group()
            results.append(ExtractedField(
                field_type="legal_ref",
                raw=raw,
                value_norm=raw,
                span=(match.start(), match.end())
            ))
        return results


# ========== Convenience Function ==========

def extract_fields(text: str) -> List[Dict[str, Any]]:
    """
    テキストからフィールドを抽出（辞書形式で返す）
    
    Args:
        text: 入力テキスト
        
    Returns:
        フィールド辞書のリスト
    """
    extractor = FieldsExtractor()
    fields = extractor.extract_all(text)
    
    return [
        {
            "type": f.field_type,
            "raw": f.raw,
            "value_norm": f.value_norm,
            "unit_norm": f.unit_norm,
            "currency_norm": f.currency_norm,
            "span": f.span,
            "confidence": f.confidence
        }
        for f in fields
    ]


if __name__ == "__main__":
    # テスト
    test_text = """
    キャンペーン価格: ¥1,980（税込）
    通常価格: 2,500円（税抜）
    期間: 2024年1月15日〜2024年2月28日
    詳細: https://example.com/campaign/
    お問い合わせ: 03-1234-5678
    型番: ABC-1234
    ※1 一部対象外商品あり
    送料: 30%OFF
    サイズ: W100×H200mm
    """
    
    fields = extract_fields(test_text)
    for f in fields:
        print(f"{f['type']:12} | {f['raw']:25} → {f['value_norm']}")
