"""
MEKIKI SDK - Similarity Module
類似検出機能 (テキストマッチング + Gemini AI)
"""

from .detector import SimilarityDetector, SimilarityResult
from .gemini_search import GeminiSimilarSearch, GeminiSearchResult

__all__ = [
    "SimilarityDetector", 
    "SimilarityResult",
    "GeminiSimilarSearch",
    "GeminiSearchResult"
]

