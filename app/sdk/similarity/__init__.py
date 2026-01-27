"""
MEKIKI SDK - Similarity Module
類似検出機能 (テキストマッチング + Gemini AI + Embedding)
"""

from .detector import SimilarityDetector, SimilarityResult
from .gemini_search import GeminiSimilarSearch, GeminiSearchResult
from .auto_matcher import GeminiAutoMatcher, MatchResult
from .embedding_search import EmbeddingSimilarSearch, EmbeddingSearchResult

__all__ = [
    "SimilarityDetector", 
    "SimilarityResult",
    "GeminiSimilarSearch",
    "GeminiSearchResult",
    "GeminiAutoMatcher",
    "MatchResult",
    "EmbeddingSimilarSearch",
    "EmbeddingSearchResult"
]
