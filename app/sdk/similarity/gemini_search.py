"""
MEKIKI SDK - Gemini-Powered Similar Search
Gemini APIを使用した高精度類似検索

機能:
- テンプレートテキストに類似した候補をGemini LLMで検出
- セマンティック類似度（意味的類似性）を考慮
- バッチ処理による高速化

使用例:
    from app.sdk.similarity.gemini_search import GeminiSimilarSearch
    
    searcher = GeminiSimilarSearch()
    results = await searcher.find_similar_async(template_text, candidates)
"""

import logging
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# ロギング設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Gemini Client Import
try:
    from app.sdk.llm import GeminiClient
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False
    GeminiClient = None


@dataclass
class GeminiSearchResult:
    """Gemini類似検索結果"""
    candidate_index: int
    candidate_text: str
    similarity_score: float
    match_reason: str
    is_semantic_match: bool = False


class GeminiSimilarSearch:
    """
    Gemini-Powered 類似検索
    
    ★ 特徴:
    - LLMによるセマンティック類似度判定
    - 単純なテキスト比較では見つけられない類似箇所を発見
    - 日本語/英語混在テキストに強い
    """
    
    def __init__(
        self, 
        model: str = "gemini-2.0-flash",
        threshold: float = 0.6,
        max_candidates: int = 20
    ):
        """
        Args:
            model: Geminiモデル名
            threshold: 類似度閾値 (0.0-1.0)
            max_candidates: 一度に処理する最大候補数
        """
        self.model = model
        self.threshold = threshold
        self.max_candidates = max_candidates
        
        if _HAS_GEMINI:
            self.client = GeminiClient(model=model)
            logger.info(f"GeminiSimilarSearch initialized (model={model})")
        else:
            self.client = None
            logger.warning("GeminiClient not available, falling back to text matching")
    
    def find_similar(
        self, 
        template_text: str, 
        candidates: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> List[GeminiSearchResult]:
        """
        類似テキストを検索 (同期版)
        
        Args:
            template_text: テンプレートテキスト
            candidates: 候補リスト [{'text': str, 'id': str, ...}, ...]
            context: 追加コンテキスト (ドキュメントタイプなど)
        
        Returns:
            GeminiSearchResultのリスト (類似度降順)
        """
        logger.info(f"Gemini search: template='{template_text[:50]}...', candidates={len(candidates)}")
        
        if not template_text.strip() or not candidates:
            return []
        
        # 候補数制限
        candidates = candidates[:self.max_candidates]
        
        if not self.client:
            logger.warning("No Gemini client, using fallback text matching")
            return self._fallback_text_match(template_text, candidates)
        
        # プロンプト構築
        prompt = self._build_prompt(template_text, candidates, context)
        
        try:
            response = self.client.generate(prompt)
            results = self._parse_response(response, candidates)
            
            # 閾値でフィルタ
            results = [r for r in results if r.similarity_score >= self.threshold]
            results.sort(key=lambda r: r.similarity_score, reverse=True)
            
            logger.info(f"Gemini found {len(results)} similar regions")
            return results
            
        except Exception as e:
            logger.error(f"Gemini search error: {e}")
            return self._fallback_text_match(template_text, candidates)
    
    async def find_similar_async(
        self, 
        template_text: str, 
        candidates: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> List[GeminiSearchResult]:
        """類似テキストを検索 (非同期版)"""
        # 現時点では同期版をラップ
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.find_similar(template_text, candidates, context)
        )
    
    def _build_prompt(
        self, 
        template_text: str, 
        candidates: List[Dict[str, Any]],
        context: Optional[str]
    ) -> str:
        """Gemini用プロンプトを構築"""
        
        # 候補リストをJSONで構造化
        candidate_list = []
        for i, c in enumerate(candidates):
            text = c.get('text', '') if isinstance(c, dict) else str(c)
            candidate_list.append({
                "index": i,
                "text": text[:200]  # 切り詰め
            })
        
        prompt = f"""あなたはテキスト類似度分析の専門家です。

## タスク
テンプレートテキストと各候補テキストの類似度を判定してください。

## テンプレート
「{template_text[:300]}」

## 候補一覧
{json.dumps(candidate_list, ensure_ascii=False, indent=2)}

## 判定基準
- 完全一致: 1.0
- ほぼ同じ内容（表現の違いのみ）: 0.8-0.99
- 意味的に類似（同じトピック）: 0.6-0.79
- 部分的に関連: 0.3-0.59
- 無関係: 0.0-0.29

## 出力形式 (JSONのみ)
```json
[
  {{"index": 0, "score": 0.85, "reason": "ほぼ同じ内容", "semantic": true}},
  {{"index": 2, "score": 0.72, "reason": "同じトピック", "semantic": true}}
]
```

類似度0.3以上の候補のみ出力してください。該当なしの場合は空配列[]を返してください。
"""
        return prompt
    
    def _parse_response(
        self, 
        response: str, 
        candidates: List[Dict[str, Any]]
    ) -> List[GeminiSearchResult]:
        """Gemini応答をパース"""
        results = []
        
        try:
            # JSON部分を抽出
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                for item in data:
                    idx = item.get('index', -1)
                    if 0 <= idx < len(candidates):
                        candidate = candidates[idx]
                        text = candidate.get('text', '') if isinstance(candidate, dict) else str(candidate)
                        
                        results.append(GeminiSearchResult(
                            candidate_index=idx,
                            candidate_text=text,
                            similarity_score=float(item.get('score', 0)),
                            match_reason=item.get('reason', ''),
                            is_semantic_match=item.get('semantic', False)
                        ))
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Parse error: {e}")
        
        return results
    
    def _fallback_text_match(
        self, 
        template_text: str, 
        candidates: List[Dict[str, Any]]
    ) -> List[GeminiSearchResult]:
        """フォールバック: 単純テキストマッチング"""
        import difflib
        
        results = []
        template_lower = template_text.lower().strip()
        
        for i, c in enumerate(candidates):
            text = c.get('text', '') if isinstance(c, dict) else str(c)
            if not text:
                continue
            
            text_lower = text.lower().strip()
            
            # SequenceMatcherで類似度計算
            ratio = difflib.SequenceMatcher(None, template_lower, text_lower).ratio()
            
            if ratio >= self.threshold:
                results.append(GeminiSearchResult(
                    candidate_index=i,
                    candidate_text=text,
                    similarity_score=ratio,
                    match_reason="Text similarity",
                    is_semantic_match=False
                ))
        
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        logger.info(f"Fallback found {len(results)} matches")
        return results
    
    def get_stats(self) -> dict:
        """統計情報"""
        return {
            'model': self.model,
            'threshold': self.threshold,
            'has_gemini': self.client is not None
        }


# ========== Convenience exports ==========
__all__ = ["GeminiSimilarSearch", "GeminiSearchResult"]
