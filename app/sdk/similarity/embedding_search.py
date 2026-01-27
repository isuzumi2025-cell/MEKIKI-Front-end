"""
SDK Similarity - Embedding-Based Semantic Search
Gemini Embeddingを使用した高精度セマンティック類似検索

Usage:
    from app.sdk.similarity import EmbeddingSimilarSearch
    
    search = EmbeddingSimilarSearch(threshold=0.75)
    
    # 類似検索
    results = search.find_similar(
        query="鎮國寺は福岡県宗像市にある",
        candidates=[
            {"id": "P001", "text": "鎮國寺について"},
            {"id": "P002", "text": "全く関係ないテキスト"}
        ]
    )
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingSearchResult:
    """Embedding類似検索結果"""
    candidate_id: str
    candidate_text: str
    similarity_score: float
    rank: int


class EmbeddingSimilarSearch:
    """
    Embedding-Based セマンティック類似検索
    
    ★ 特徴:
    - Gemini Embedding APIによる高精度ベクトル類似度
    - コサイン類似度によるスコアリング
    - バッチ処理による効率化
    """
    
    def __init__(self, threshold: float = 0.70, model: str = "gemini-embedding-001"):
        """
        Args:
            threshold: 類似度閾値 (0.0-1.0)
            model: Embeddingモデル名
        """
        self.threshold = threshold
        self.model = model
        self._client = None
        self._stats = {
            "queries": 0,
            "candidates_processed": 0,
            "matches_found": 0
        }
        
        logger.info(f"EmbeddingSimilarSearch initialized (threshold={threshold}, model={model})")
    
    def _get_client(self):
        """遅延初期化でEmbeddingClientを取得"""
        if self._client is None:
            try:
                from app.sdk.llm import GeminiEmbeddingClient
                self._client = GeminiEmbeddingClient(model=self.model)
                if not self._client.is_available():
                    logger.warning("EmbeddingClient not available")
                    self._client = None
            except Exception as e:
                logger.error(f"Failed to init EmbeddingClient: {e}")
                self._client = None
        return self._client
    
    def find_similar(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[EmbeddingSearchResult]:
        """
        クエリに類似する候補を検索
        
        Args:
            query: 検索クエリテキスト
            candidates: 候補リスト [{"id": str, "text": str, ...}, ...]
            top_k: 返す最大件数
            
        Returns:
            類似度降順のEmbeddingSearchResultリスト
        """
        if not query.strip():
            return []
        
        if not candidates:
            return []
        
        self._stats["queries"] += 1
        self._stats["candidates_processed"] += len(candidates)
        
        client = self._get_client()
        if not client:
            logger.warning("No embedding client, falling back to difflib")
            return self._fallback_difflib(query, candidates, top_k)
        
        try:
            # クエリの埋め込みを生成
            query_vec = client.embed_text(query, task_type="RETRIEVAL_QUERY")
            if query_vec is None:
                return self._fallback_difflib(query, candidates, top_k)
            
            # 候補テキストの埋め込みを生成
            candidate_texts = [c.get("text", "") for c in candidates]
            candidate_vecs = client.embed_texts(candidate_texts, task_type="RETRIEVAL_DOCUMENT")
            
            # 類似度計算
            results = []
            for i, (candidate, vec) in enumerate(zip(candidates, candidate_vecs)):
                if vec is None:
                    continue
                
                score = client.cosine_similarity(query_vec, vec)
                
                if score >= self.threshold:
                    results.append(EmbeddingSearchResult(
                        candidate_id=candidate.get("id", f"C{i:03d}"),
                        candidate_text=candidate.get("text", ""),
                        similarity_score=score,
                        rank=0  # 後で設定
                    ))
            
            # スコア順にソート
            results.sort(key=lambda x: x.similarity_score, reverse=True)
            
            # ランク付け
            for i, r in enumerate(results):
                r.rank = i + 1
            
            self._stats["matches_found"] += len(results[:top_k])
            
            logger.info(f"Embedding search: {len(results)} matches from {len(candidates)} candidates")
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Embedding search error: {e}")
            return self._fallback_difflib(query, candidates, top_k)
    
    def _fallback_difflib(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int
    ) -> List[EmbeddingSearchResult]:
        """difflibによるフォールバック"""
        from difflib import SequenceMatcher
        
        results = []
        for i, candidate in enumerate(candidates):
            text = candidate.get("text", "")
            if not text:
                continue
            
            ratio = SequenceMatcher(None, query, text).ratio()
            
            # 部分一致ボーナス
            if query in text or text in query:
                ratio = max(ratio, 0.7)
            
            if ratio >= self.threshold:
                results.append(EmbeddingSearchResult(
                    candidate_id=candidate.get("id", f"C{i:03d}"),
                    candidate_text=text,
                    similarity_score=ratio,
                    rank=0
                ))
        
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1
        
        logger.info(f"Fallback difflib search: {len(results)} matches")
        return results[:top_k]
    
    def compute_similarity_matrix(
        self, 
        texts1: List[str], 
        texts2: List[str]
    ) -> List[List[float]]:
        """
        2つのテキストリスト間の類似度行列を計算
        
        Args:
            texts1: テキストリスト1 (行)
            texts2: テキストリスト2 (列)
            
        Returns:
            類似度行列 [len(texts1)][len(texts2)]
        """
        client = self._get_client()
        if not client:
            # フォールバック: difflib
            from difflib import SequenceMatcher
            return [
                [SequenceMatcher(None, t1, t2).ratio() for t2 in texts2]
                for t1 in texts1
            ]
        
        try:
            vecs1 = client.embed_texts(texts1)
            vecs2 = client.embed_texts(texts2)
            
            matrix = []
            for v1 in vecs1:
                row = []
                for v2 in vecs2:
                    if v1 is None or v2 is None:
                        row.append(0.0)
                    else:
                        row.append(client.cosine_similarity(v1, v2))
                matrix.append(row)
            
            return matrix
            
        except Exception as e:
            logger.error(f"Similarity matrix error: {e}")
            from difflib import SequenceMatcher
            return [
                [SequenceMatcher(None, t1, t2).ratio() for t2 in texts2]
                for t1 in texts1
            ]
    
    def get_stats(self) -> Dict[str, int]:
        """統計情報を取得"""
        return self._stats.copy()


# ========== Convenience exports ==========
__all__ = ["EmbeddingSimilarSearch", "EmbeddingSearchResult"]
