"""
SDK OCR Module
Gemini / Vision API 対応OCRエンジン

Phase 1.9 追加:
- ocr_trace: パイプライントレース
- text_filter: 文字種対応フィルタ
- text_normalizer: 日本語正規化
"""

from .gemini_engine import GeminiOCREngine
from .paragraph import ParagraphDetector, Paragraph, TextBlock
from .ocr_trace import PipelineTrace, TokenTrace, TraceManager, get_trace_manager
from .text_filter import TextFilter, FilterConfig, get_text_filter
from .text_normalizer import TextNormalizer, get_text_normalizer

__all__ = [
    "GeminiOCREngine", 
    "ParagraphDetector", 
    "Paragraph", 
    "TextBlock",
    # Phase 1.9
    "PipelineTrace",
    "TokenTrace", 
    "TraceManager",
    "get_trace_manager",
    "TextFilter",
    "FilterConfig",
    "get_text_filter",
    "TextNormalizer",
    "get_text_normalizer",
]
