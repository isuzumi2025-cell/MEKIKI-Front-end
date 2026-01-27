"""
SDK Auto Matcher - 多信号マッチング

Phase 1.9.4: n-gram + LCS + Embedding rerank のハイブリッドアプローチ

特徴:
- Stage 1: n-gram Jaccard で TopK 候補生成（安価）
- Stage 2: LCS + difflib で再スコアリング
- Stage 3: Embedding rerank（オプション, 高コスト候補のみ）
- ひらがな長文への専用ブースト

Usage:
    from app.sdk.similarity import GeminiAutoMatcher
    
    matcher = GeminiAutoMatcher()
    results = matcher.find_matching_paragraphs(
        query_text="ちくぜんのくにいちのみやすみよしじんじゃ",
        target_paragraphs=pdf_paragraphs,
        threshold=0.4
    )
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import threading
import re


@dataclass
class MatchResult:
    """マッチング結果"""
    paragraph_id: int
    paragraph_text: str
    similarity_score: float
    rect: Optional[Tuple[int, int, int, int]] = None  # バウンディングボックス


class GeminiAutoMatcher:
    """
    多信号マッチング (Phase 1.9.4)
    
    Stage 1: n-gram Jaccard で TopK 候補生成
    Stage 2: LCS + difflib で再スコアリング
    Stage 3: Embedding rerank (オプション, 高コスト候補のみ)
    
    ひらがな長文の場合はn-gramを優先し、difflibは参照程度に
    """
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self._client = None
        self._normalizer = None
    
    @property
    def normalizer(self):
        """TextNormalizer の遅延初期化"""
        if self._normalizer is None:
            try:
                from app.sdk.ocr.text_normalizer import TextNormalizer
                self._normalizer = TextNormalizer()
            except ImportError:
                # フォールバック: 基本的な正規化
                self._normalizer = _BasicNormalizer()
        return self._normalizer
        
    def _get_client(self):
        """遅延初期化でGeminiClientを取得"""
        if self._client is None:
            try:
                from app.sdk.llm import GeminiClient
                self._client = GeminiClient(model=self.model)
            except Exception as e:
                print(f"[AutoMatcher] Failed to init client: {e}")
        return self._client
    
    def _extract_ngrams(self, text: str, n: int = 3) -> set:
        """n-gram抽出"""
        text = self.normalizer.normalize_for_matching(text) if hasattr(self.normalizer, 'normalize_for_matching') else text
        if len(text) < n:
            return set()
        return {text[i:i+n] for i in range(len(text) - n + 1)}
    
    def _ngram_similarity(self, text1: str, text2: str, n: int = 3) -> float:
        """n-gram Jaccard類似度"""
        ngrams1 = self._extract_ngrams(text1, n)
        ngrams2 = self._extract_ngrams(text2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    def _is_hiragana_dominant(self, text: str) -> bool:
        """ひらがな主体かどうか"""
        if not text:
            return False
        hiragana = len(re.findall(r'[\u3040-\u309F]', text))
        total = len(text.replace(' ', ''))
        return total > 0 and hiragana / total >= 0.7
    
    def find_matching_paragraphs(
        self,
        query_text: str,
        target_paragraphs: List[dict],
        threshold: float = 0.4,
        top_k: int = 5,
        use_embedding_rerank: bool = True
    ) -> List[MatchResult]:
        """
        多信号マッチング
        
        Args:
            query_text: 選択されたテキスト
            target_paragraphs: 対象パラグラフリスト [{\"id\": int, \"text\": str, \"rect\": tuple}, ...]
            threshold: 類似度閾値 (0.0-1.0)
            top_k: 返す最大件数
            use_embedding_rerank: Embedding による再ランキングを使用
            
        Returns:
            類似度順にソートされたMatchResultリスト
        """
        if not query_text.strip():
            return []
        
        if not target_paragraphs:
            return []
        
        # ひらがな主体判定
        is_hiragana = self._is_hiragana_dominant(query_text)
        
        if is_hiragana:
            print(f"[AutoMatcher] ひらがな長文モード: n-gram優先")
        
        # ========================================
        # Stage 1: n-gram で候補生成 (Top 20)
        # ========================================
        candidates = []
        for para in target_paragraphs:
            para_text = para.get("text", "")
            if not para_text.strip():
                continue
            
            # n-gram 類似度（3-gramと4-gramの平均）
            ngram3_score = self._ngram_similarity(query_text, para_text, n=3)
            ngram4_score = self._ngram_similarity(query_text, para_text, n=4)
            ngram_score = (ngram3_score * 0.6 + ngram4_score * 0.4)
            
            # ひらがな長文の場合は閾値を緩和
            min_score = 0.2 if is_hiragana else threshold * 0.5
            
            if ngram_score >= min_score:
                candidates.append({
                    "para": para,
                    "ngram_score": ngram_score
                })
        
        # Top 20 に絞る
        candidates.sort(key=lambda x: x["ngram_score"], reverse=True)
        candidates = candidates[:20]
        
        print(f"[AutoMatcher] Stage 1: {len(candidates)} candidates (n-gram)")
        
        if not candidates:
            # n-gramで候補がない場合はdifflibフォールバック
            return self._difflib_fallback(query_text, target_paragraphs, threshold, top_k)
        
        # ========================================
        # Stage 2: LCS + difflib で再スコアリング
        # ========================================
        from difflib import SequenceMatcher
        
        results = []
        for cand in candidates:
            para = cand["para"]
            para_text = para.get("text", "")
            
            # difflib スコア
            diff_score = SequenceMatcher(None, query_text, para_text).ratio()
            
            # 部分一致ボーナス
            if query_text in para_text or para_text in query_text:
                diff_score = max(diff_score, 0.7)
            
            # 統合スコア (ひらがなはn-gram重視)
            if is_hiragana:
                combined = cand["ngram_score"] * 0.7 + diff_score * 0.3
            else:
                combined = cand["ngram_score"] * 0.4 + diff_score * 0.6
            
            if combined >= threshold:
                results.append(MatchResult(
                    paragraph_id=para.get("id", 0),
                    paragraph_text=para_text,
                    similarity_score=combined,
                    rect=para.get("rect")
                ))
        
        # スコア順にソート
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        print(f"[AutoMatcher] Stage 2: {len(results)} results (LCS+difflib)")
        
        # ========================================
        # Stage 3: Embedding rerank (オプション)
        # ========================================
        if use_embedding_rerank and len(results) > 0 and len(results) <= 10:
            results = self._embedding_rerank(query_text, results[:10])
            print(f"[AutoMatcher] Stage 3: Embedding rerank applied")
        
        # Gemini による最終精緻化（少数候補のみ）
        if results and len(results) <= 5:
            results = self._refine_with_gemini(query_text, results)
        
        return results[:top_k]
    
    def _difflib_fallback(
        self, 
        query_text: str, 
        target_paragraphs: List[dict], 
        threshold: float,
        top_k: int
    ) -> List[MatchResult]:
        """n-gramで候補がない場合のdifflibフォールバック"""
        from difflib import SequenceMatcher
        
        candidates = []
        for para in target_paragraphs:
            para_text = para.get("text", "")
            if not para_text.strip():
                continue
            
            ratio = SequenceMatcher(None, query_text, para_text).ratio()
            
            if query_text in para_text or para_text in query_text:
                ratio = max(ratio, 0.7)
            
            if ratio >= threshold:
                candidates.append(MatchResult(
                    paragraph_id=para.get("id", 0),
                    paragraph_text=para_text,
                    similarity_score=ratio,
                    rect=para.get("rect")
                ))
        
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        return candidates[:top_k]
    
    def _embedding_rerank(self, query: str, candidates: List[MatchResult]) -> List[MatchResult]:
        """Embedding による再ランキング (コスト制御付き)"""
        try:
            from app.sdk.similarity import EmbeddingSimilarSearch
            
            # キャッシュ付きで実行
            search = EmbeddingSimilarSearch(threshold=0.5)
            target_list = [
                {"id": c.paragraph_id, "text": c.paragraph_text}
                for c in candidates
            ]
            
            embed_results = search.find_similar(query, target_list, top_k=5)
            
            if embed_results:
                # Embedding スコアで並べ替え
                id_to_embed = {r.candidate_id: r.similarity_score for r in embed_results}
                for c in candidates:
                    if c.paragraph_id in id_to_embed:
                        # Embedding スコアをブースト
                        embed_score = id_to_embed[c.paragraph_id]
                        c.similarity_score = c.similarity_score * 0.6 + embed_score * 0.4
                
                candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        
        except Exception as e:
            print(f"[AutoMatcher] Embedding rerank skipped: {e}")
        
        return candidates
    
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
        threshold: float = 0.4
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


class _BasicNormalizer:
    """TextNormalizerが使えない場合のフォールバック"""
    def normalize_for_matching(self, text: str) -> str:
        import unicodedata
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[。、,.!?！？]', '', text)
        return text
