"""
Advanced Proofing System - Pydantic Schemas
統一データスキーマ定義

Created: 2026-01-11
"""
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


# =============== Enums ===============

class SourceType(str, Enum):
    WEB = "web"
    PDF = "pdf"


class ElementKind(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    IMAGE = "image"
    OTHER = "other"


class SourceChannel(str, Enum):
    DOM = "DOM"
    PDFTEXT = "PDFTEXT"
    OCR = "OCR"


class FieldType(str, Enum):
    PRICE = "price"
    DATE = "date"
    PERCENT = "percent"
    DIMENSION = "dimension"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    SKU = "sku"
    NUMBER = "number"
    LEGAL_REF = "legal_ref"
    OTHER = "other"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class DiffType(str, Enum):
    SAME = "SAME"
    TEXT_DIFF = "text_diff"
    FIELD_DIFF = "field_diff"
    TABLE_DIFF = "table_diff"
    MISSING = "missing"
    ADDED = "added"


class IssueStatus(str, Enum):
    OPEN = "OPEN"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


# =============== Core Models ===============

class BBox(BaseModel):
    """バウンディングボックス"""
    x1: float
    y1: float
    x2: float
    y2: float
    
    @property
    def width(self) -> float:
        return self.x2 - self.x1
    
    @property
    def height(self) -> float:
        return self.y2 - self.y1
    
    @property
    def center(self) -> tuple:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


class DocumentSource(BaseModel):
    """ドキュメントソース情報"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: SourceType
    uri: str  # URL or file path
    captured_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PageView(BaseModel):
    """ページビュー"""
    page_index: int
    image_path: Optional[str] = None
    width: int
    height: int
    dpi: int = 96
    source_id: str


class StructuredField(BaseModel):
    """構造化フィールド（価格/日付等）"""
    field_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: FieldType
    raw: str  # 元のテキスト
    value_norm: str  # 正規化済み値
    unit_norm: Optional[str] = None  # 正規化済み単位
    currency_norm: Optional[str] = None  # 正規化済み通貨
    bbox: Optional[BBox] = None
    char_span: Optional[tuple] = None  # (start, end)
    confidence: float = 1.0


class Element(BaseModel):
    """抽出要素（段落/見出し等）"""
    element_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    page_index: int = 0
    kind: ElementKind = ElementKind.PARAGRAPH
    text_raw: str = ""
    text_norm: str = ""
    bbox: BBox
    reading_order: int = 0
    source_channel: SourceChannel = SourceChannel.OCR
    confidence_text: float = 1.0
    fields: List[StructuredField] = Field(default_factory=list)
    parent_id: Optional[str] = None
    role: Optional[str] = None  # headline/body/caption/legal/price


class TableCell(BaseModel):
    """テーブルセル"""
    cell_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    row: int
    col: int
    bbox: Optional[BBox] = None
    text_raw: str = ""
    text_norm: str = ""
    confidence_text: float = 1.0
    fields: List[StructuredField] = Field(default_factory=list)


class Table(BaseModel):
    """テーブル構造"""
    table_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_index: int = 0
    bbox: BBox
    caption: Optional[str] = None
    surrounding_heading: Optional[str] = None
    header_rows: int = 1
    header_cols: int = 0
    grid: List[List[TableCell]] = Field(default_factory=list)


class Match(BaseModel):
    """マッチング結果"""
    match_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    left_id: str
    right_id: str
    kind: Literal["paragraph", "table", "cell"] = "paragraph"
    score_total: float = 0.0
    score_text: float = 0.0
    score_embed: float = 0.0
    score_layout: float = 0.0
    score_visual: float = 0.0
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class Issue(BaseModel):
    """差分Issue"""
    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: DiffType = DiffType.TEXT_DIFF
    left_id: Optional[str] = None
    right_id: Optional[str] = None
    severity: Severity = Severity.MINOR
    risk_reason: List[str] = Field(default_factory=list)
    diff_summary: str = ""
    evidence_paths: Dict[str, str] = Field(default_factory=dict)
    # left_crop, right_crop, overlay_crop, meta_json
    status: IssueStatus = IssueStatus.OPEN
    assignee: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


# =============== Run Context ===============

class RunContext(BaseModel):
    """実行コンテキスト"""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: Optional[str] = None
    job_id: Optional[str] = None
    left_source: Optional[DocumentSource] = None
    right_source: Optional[DocumentSource] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"  # pending/running/completed/failed


# =============== Config Models ===============

class FieldRule(BaseModel):
    """フィールド差分ルール"""
    field_type: FieldType
    tolerance: float = 0.0  # 許容差
    ignore_case: bool = True
    normalize_currency: bool = True
    normalize_tax: bool = True  # 税込/税抜の正規化


class SeverityRule(BaseModel):
    """重大度判定ルール"""
    name: str
    condition: str  # diff_type, field_type, keyword match等
    severity: Severity
    risk_reason: str


class RulesConfig(BaseModel):
    """ルール設定"""
    field_rules: List[FieldRule] = Field(default_factory=list)
    severity_rules: List[SeverityRule] = Field(default_factory=list)
    match_weights: Dict[str, float] = Field(default_factory=lambda: {
        "alpha_text": 0.4,
        "beta_embed": 0.2,
        "gamma_layout": 0.2,
        "delta_visual": 0.2
    })
