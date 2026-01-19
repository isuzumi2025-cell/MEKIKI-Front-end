"""
SDK OCR Module
Gemini / Vision API 対応OCRエンジン
"""

from .gemini_engine import GeminiOCREngine
from .paragraph import ParagraphDetector, Paragraph, TextBlock

__all__ = ["GeminiOCREngine", "ParagraphDetector", "Paragraph", "TextBlock"]
