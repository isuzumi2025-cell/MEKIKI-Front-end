"""
SDK Auto Matcher - Gemini意味ベース自動パラグラフマッチング

Phase 1.6: 手動選択テキストから対向ソースの類似パラグラフを自動検出

Usage:
    from app.sdk.similarity import GeminiAutoMatcher
    
    matcher = GeminiAutoMatcher()
    results = matcher.find_matching_paragraphs(
        query_text="鎮國寺",
        target_paragraphs=pdf_paragraphs,
        threshold=0.7
    )
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import threading


@dataclass
class MatchResult:
    """マッチング結果"""
    paragraph_id: int
    paragraph_text: str
    similarity_score: float
    rect: Optional[Tuple[int, int, int, int]] = None  # バウンディングボックス


class GeminiAutoMatcher:
    """
    Gemini意味ベース自動マッチング
    
    Web選択 → PDF内から類似パラグラフ検出
    PDF選択 → Web内から類似パラグラフ検出
    """
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self._client = None
        
    def _get_client(self):
        """遅延初期化でGeminiClientを取得"""
        if self._client is None:
            try:
                from app.sdk.llm import GeminiClient
                self._client = GeminiClient(model=self.model)
            except Exception as e:
                print(f"[AutoMatcher] Failed to init client: {e}")
        return self._client
    
    def find_matching_paragraphs(
        self,
        query_text: str,
        target_paragraphs: List[dict],
        threshold: float = 0.5,
        top_k: int = 5
    ) -> List[MatchResult]:
        """
        クエリテキストに類似するパラグラフを検出
        
        Args:
            query_text: 選択されたテキスト
            target_paragraphs: 対象パラグラフリスト [{"id": int, "text": str, "rect": tuple}, ...]
            threshold: 類似度閾値 (0.0-1.0)
            top_k: 返す最大件数
            
        Returns:
            類似度順にソートされたMatchResultリスト
        """
        if not query_text.strip():
            return []
        
        if not target_paragraphs:
            return []
        
        # まずdifflibで高速フィルタリング
        from difflib import SequenceMatcher
        
        candidates = []
        for para in target_paragraphs:
            para_text = para.get("text", "")
            if not para_text.strip():
                continue
            
            # 文字列マッチングスコア
            ratio = SequenceMatcher(None, query_text, para_text).ratio()
            
            # 部分一致ボーナス
            if query_text in para_text or para_text in query_text:
                ratio = max(ratio, 0.7)
            
            if ratio >= threshold:
                candidates.append(MatchResult(
                    paragraph_id=para.get("id", 0),
                    paragraph_text=para_text,
                    similarity_score=ratio,
                    rect=para.get("rect")
                ))
        
        # スコア順にソート
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Geminiで精度向上（上位候補のみ）
        if candidates and len(candidates) <= 10:
            candidates = self._refine_with_gemini(query_text, candidates)
        
        return candidates[:top_k]
    
    def _refine_with_gemini(
        self, 
        query_text: str, 
        candidates: List[MatchResult]
    ) -> List[MatchResult]:
        """Geminiで類似度を精緻化"""
        client = self._get_client()
        if not client:
            return candidates
        
        try:
            # プロンプト構築
            candidate_texts = "\n".join([
                f"[{i}] {c.paragraph_text[:100]}"
                for i, c in enumerate(candidates)
            ])
            
            prompt = f"""以下のクエリテキストに最も意味的に類似するパラグラフを選んでください。
類似度が高い順に番号を出力してください（カンマ区切り）。

クエリ: {query_text}

候補:
{candidate_texts}

回答形式: 0,2,1 (番号のみ)"""

            result = client.generate(prompt)
            if not result:
                return candidates
            
            # 結果をパース
            try:
                indices = [int(x.strip()) for x in result.split(",") if x.strip().isdigit()]
                
                # インデックス順に並べ替え
                reordered = []
                for idx in indices:
                    if 0 <= idx < len(candidates):
                        reordered.append(candidates[idx])
                
                # 残りを追加
                for c in candidates:
                    if c not in reordered:
                        reordered.append(c)
                
                return reordered
                
            except:
                return candidates
                
        except Exception as e:
            print(f"[AutoMatcher] Gemini refine error: {e}")
            return candidates
    
    def find_matching_async(
        self,
        query_text: str,
        target_paragraphs: List[dict],
        callback,
        threshold: float = 0.5
    ):
        """
        非同期でマッチング実行
        
        Args:
            callback: 結果を受け取るコールバック関数 (results: List[MatchResult]) -> None
        """
        def _run():
            results = self.find_matching_paragraphs(query_text, target_paragraphs, threshold)
            callback(results)
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread
