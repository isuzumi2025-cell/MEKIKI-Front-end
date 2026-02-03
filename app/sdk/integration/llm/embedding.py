"""
SDK LLM Embedding - Gemini Embedding API Client
テキストのベクトル表現（埋め込み）を生成するクライアント

Usage:
    from app.sdk.llm import GeminiEmbeddingClient
    
    client = GeminiEmbeddingClient()
    
    # 単一テキストの埋め込み
    vector = client.embed_text("鎮國寺は福岡県宗像市にある寺院です")
    
    # 複数テキストの一括埋め込み
    vectors = client.embed_texts(["テキスト1", "テキスト2"])
    
    # コサイン類似度計算
    score = client.cosine_similarity(vector1, vector2)
"""

from typing import List, Optional
from dataclasses import dataclass
import os
import math


@dataclass
class EmbeddingResult:
    """埋め込み結果"""
    vector: List[float]
    text: str
    model: str
    dimensions: int


class GeminiEmbeddingClient:
    """
    Gemini Embedding API Client
    
    Supported models:
    - gemini-embedding-001 (default, latest)
    - text-embedding-004 (legacy, deprecated)
    
    Features:
    - 768次元ベクトル生成
    - 日本語対応
    - バッチ処理対応
    """
    
    DEFAULT_MODEL = "gemini-embedding-001"
    
    def __init__(self, model: str = "gemini-embedding-001"):
        self.model_name = model
        self._client = None
        self._initialized = False
        
        try:
            import google.generativeai as genai
            
            # Try multiple ways to get API key
            api_key = None
            
            # Method 1: Try Config class
            try:
                from config import Config
                if hasattr(Config, 'load_keys'):
                    Config.load_keys()
                api_key = getattr(Config, 'GEMINI_API_KEY', None)
            except Exception:
                pass
            
            # Method 2: Try api_manager directly
            if not api_key:
                try:
                    from app.config.api_manager import get_api_manager
                    manager = get_api_manager()
                    keys = manager.load()
                    api_key = keys.gemini_api_key
                except Exception:
                    pass
            
            # Method 3: Environment variable  
            if not api_key:
                api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            
            # Method 4: Try service_account.json for Vertex AI style auth
            if not api_key:
                from pathlib import Path
                sa_path = Path(__file__).resolve().parent.parent.parent.parent / "service_account.json"
                if sa_path.exists():
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_path)
                    print(f"[Embedding] Using service account: {sa_path}")
                    # With service account, we don't need API key for some operations
                    # Try to use default application credentials
                    genai.configure()  # Uses ADC
                    self._client = genai
                    self._initialized = True
                    print(f"✅ Gemini Embedding Client (ADC): {model}")
                    return
            
            if not api_key:
                print("⚠️ GEMINI_API_KEY not set for Embedding")
                return
            
            genai.configure(api_key=api_key)
            self._client = genai
            self._initialized = True
            print(f"✅ Gemini Embedding Client: {model}")
        except Exception as e:
            print(f"❌ Gemini Embedding init error: {e}")


    
    def embed_text(self, text: str, task_type: str = "SEMANTIC_SIMILARITY") -> Optional[List[float]]:
        """
        単一テキストの埋め込みベクトルを生成
        
        Args:
            text: 埋め込み対象テキスト
            task_type: タスク種別 (SEMANTIC_SIMILARITY, RETRIEVAL_QUERY, RETRIEVAL_DOCUMENT, etc.)
            
        Returns:
            768次元のベクトル (List[float])
        """
        if not self._initialized or not self._client:
            return None
        
        if not text or not text.strip():
            print("[Embedding] Empty text provided")
            return None
        
        try:
            result = self._client.embed_content(
                model=f"models/{self.model_name}",
                content=text,
                task_type=task_type
            )
            
            # Result is an object with 'embedding' attribute
            if result is not None:
                embedding = getattr(result, 'embedding', None)
                if embedding is None and isinstance(result, dict):
                    embedding = result.get('embedding')
                
                if embedding:
                    print(f"[Embedding] Generated {len(embedding)}-dim vector for text ({len(text)} chars)")
                    return list(embedding)
            
            print("[Embedding] No embedding in response")
            return None
                
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def embed_texts(self, texts: List[str], task_type: str = "SEMANTIC_SIMILARITY") -> List[Optional[List[float]]]:
        """
        複数テキストの埋め込みベクトルを一括生成
        
        Args:
            texts: テキストリスト
            task_type: タスク種別
            
        Returns:
            ベクトルのリスト
        """
        if not self._initialized or not self._client:
            return [None] * len(texts)
        
        results = []
        for text in texts:
            vector = self.embed_text(text, task_type)
            results.append(vector)
        
        print(f"[Embedding] Batch processed {len(texts)} texts, {sum(1 for v in results if v)} successful")
        return results
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        コサイン類似度を計算
        
        Args:
            vec1: ベクトル1
            vec2: ベクトル2
            
        Returns:
            類似度スコア (0.0 ~ 1.0)
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        # ドット積
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # ノルム
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの意味的類似度を計算
        
        Args:
            text1: テキスト1
            text2: テキスト2
            
        Returns:
            類似度スコア (0.0 ~ 1.0)
        """
        vec1 = self.embed_text(text1)
        vec2 = self.embed_text(text2)
        
        if vec1 is None or vec2 is None:
            return 0.0
        
        return self.cosine_similarity(vec1, vec2)
    
    def is_available(self) -> bool:
        """クライアントが利用可能かどうか"""
        return self._initialized and self._client is not None


# ========== Convenience exports ==========
__all__ = ["GeminiEmbeddingClient", "EmbeddingResult"]
