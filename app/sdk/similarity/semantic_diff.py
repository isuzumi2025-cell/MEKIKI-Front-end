"""
MEKIKI SDK - Gemini Semantic Diff
Geminiによる意味的テキスト差分検出

Usage:
    from app.sdk.similarity.semantic_diff import SemanticDiff
    
    diff = SemanticDiff()
    result = diff.analyze(web_text, pdf_text)
    # result = {"matches": [...], "web_only": [...], "pdf_only": [...]}
"""

from dataclasses import dataclass
from typing import List, Optional
import json
import re


@dataclass
class DiffResult:
    """差分検出結果"""
    matches: List[str]      # 両方に存在するフレーズ
    web_only: List[str]     # Web側のみ
    pdf_only: List[str]     # PDF側のみ
    raw_response: str = ""  # Gemini生レスポンス


class SemanticDiff:
    """
    Geminiによる意味的テキスト差分検出
    
    特徴:
    - 順序無視で同一内容を検出
    - 表記揺れ・同義語も考慮
    - 日本語に最適化
    """
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.client = None
        self.model = model
        self._init_client()
    
    def _init_client(self):
        """Geminiクライアント初期化"""
        try:
            from app.sdk.llm.client import GeminiClient
            self.client = GeminiClient(model=self.model)
            print(f"✅ SemanticDiff initialized: {self.model}")
        except Exception as e:
            print(f"⚠️ SemanticDiff init error: {e}")
    
    def analyze(self, text1: str, text2: str) -> DiffResult:
        """
        2つのテキストを意味的に比較
        
        Args:
            text1: Web側テキスト
            text2: PDF側テキスト
        
        Returns:
            DiffResult: 一致・差分情報
        """
        if not self.client or not self.client.model:
            print("⚠️ Gemini not available, using fallback")
            return self._fallback_diff(text1, text2)
        
        prompt = f"""以下の2つのテキストを比較し、一致する情報と異なる情報を抽出してください。

【テキスト1 (Web)】
{text1[:500]}

【テキスト2 (PDF)】
{text2[:500]}

以下のJSON形式で回答してください:
{{
  "matches": ["両方に存在する情報1", "両方に存在する情報2", ...],
  "text1_only": ["テキスト1のみの情報1", ...],
  "text2_only": ["テキスト2のみの情報1", ...]
}}

注意:
- 表記揺れや同義語は同一とみなす（例: "神社" と "しんじゃ"）
- 順序の違いは無視
- 固有名詞、住所、電話番号などの重要情報に注目
- 日本語で回答"""

        try:
            response = self.client.generate(prompt)
            if not response:
                return self._fallback_diff(text1, text2)
            
            # JSON抽出
            result = self._parse_response(response)
            result.raw_response = response
            return result
            
        except Exception as e:
            print(f"❌ SemanticDiff error: {e}")
            return self._fallback_diff(text1, text2)
    
    def _parse_response(self, response: str) -> DiffResult:
        """Geminiレスポンスをパース"""
        try:
            # JSON部分を抽出
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return DiffResult(
                    matches=data.get("matches", []),
                    web_only=data.get("text1_only", []),
                    pdf_only=data.get("text2_only", [])
                )
        except json.JSONDecodeError:
            pass
        
        return DiffResult(matches=[], web_only=[], pdf_only=[])
    
    def _fallback_diff(self, text1: str, text2: str) -> DiffResult:
        """Gemini不可時のフォールバック (ローカル処理)"""
        import difflib
        
        # 空白除去
        clean1 = re.sub(r'\s+', '', text1)[:200]
        clean2 = re.sub(r'\s+', '', text2)[:200]
        
        # 共通部分を抽出
        matcher = difflib.SequenceMatcher(None, clean1, clean2)
        matches = []
        for match in matcher.get_matching_blocks():
            if match.size >= 5:
                matches.append(clean1[match.a:match.a + match.size])
        
        return DiffResult(
            matches=matches,
            web_only=[],
            pdf_only=[]
        )
    
    def highlight_matches(self, text: str, matches: List[str]) -> List[tuple]:
        """
        テキスト内のマッチ箇所を特定
        
        Returns:
            [(start, end, "match"|"diff"), ...]
        """
        text = text[:200]
        ranges = []
        
        # 各マッチフレーズの位置を探す
        for phrase in sorted(matches, key=len, reverse=True):
            if len(phrase) < 3:
                continue
            pattern = re.escape(phrase)
            for m in re.finditer(pattern, text, re.IGNORECASE):
                ranges.append((m.start(), m.end(), "match"))
        
        # 範囲をソート・マージ
        ranges.sort()
        return ranges


# Singleton instance for reuse
_semantic_diff_instance: Optional[SemanticDiff] = None

def get_semantic_diff() -> SemanticDiff:
    """SemanticDiffシングルトン取得"""
    global _semantic_diff_instance
    if _semantic_diff_instance is None:
        _semantic_diff_instance = SemanticDiff()
    return _semantic_diff_instance
