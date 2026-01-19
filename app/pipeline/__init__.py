"""
Pipeline package initialization
"""
from .ingest_web import WebIngestor, capture_web_page
from .ingest_pdf import PDFIngestor, capture_pdf
from .normalize import TextNormalizer, normalize_text
from .match import ElementMatcher, match_paragraphs
from .diff import DiffClassifier, classify_diff
from .spreadsheet_exporter import SpreadsheetExporter, export_issues

__all__ = [
    "WebIngestor", "capture_web_page",
    "PDFIngestor", "capture_pdf",
    "TextNormalizer", "normalize_text",
    "ElementMatcher", "match_paragraphs",
    "DiffClassifier", "classify_diff",
    "SpreadsheetExporter", "export_issues",
]
