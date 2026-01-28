"""
Multi-Model Advisor
Claude Opus 4 を主体とし、Gemini の意見も参考表示

運用:
1. Claude (主体): 分析・計画・実装案
2. Gemini (参考): 代替案・ユニークな視点
3. ユーザー: 最終選択
"""
import os
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class Opinion:
    """モデルの意見"""
    model: str
    role: str  # "primary" or "reference"
    content: str
    reasoning: str


class MultiModelAdvisor:
    """
    マルチモデルアドバイザー
    
    Claude Opus 4 を主体として、Gemini の意見も取得し比較表示
    """
    
    def __init__(self):
        self._claude_client = None
        self._gemini_client = None
        
        # Gemini API キー (Google AI Studio)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    def _init_claude(self):
        """Claude クライアント初期化"""
        if self._claude_client:
            return self._claude_client
        
        import anthropic
        self._claude_client = anthropic.Anthropic()
        return self._claude_client
    
    def _init_gemini(self):
        """Gemini クライアント初期化"""
        if self._gemini_client:
            return self._gemini_client
        
        if not self.gemini_api_key:
            print("⚠️ GEMINI_API_KEY not set")
            return None
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_api_key)
            self._gemini_client = genai.GenerativeModel("gemini-1.5-pro")
            return self._gemini_client
        except ImportError:
            print("⚠️ google-generativeai not installed")
            print("   pip install google-generativeai")
            return None
    
    def get_gemini_opinion(self, question: str, context: str = "") -> Optional[str]:
        """Gemini の意見を取得"""
        client = self._init_gemini()
        if not client:
            return None
        
        prompt = f"""あなたは創造的なソフトウェアエンジニアです。
以下の質問に対して、ユニークで実用的な意見を述べてください。

{f"コンテキスト: {context}" if context else ""}

質問: {question}

回答は簡潔に、箇条書きで3-5点にまとめてください。
従来とは異なるアプローチや、見落とされがちな視点を重視してください。
"""
        
        try:
            response = client.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"⚠️ Gemini API error: {e}")
            return None
    
    def compare(
        self, 
        question: str,
        claude_opinion: str,
        context: str = ""
    ) -> Dict:
        """
        Claude の意見（主体）と Gemini の意見（参考）を比較
        
        Args:
            question: 質問
            claude_opinion: Claude の意見（事前に決定済み）
            context: 追加コンテキスト
        
        Returns:
            比較結果辞書
        """
        gemini_opinion = self.get_gemini_opinion(question, context)
        
        result = {
            "question": question,
            "primary": {
                "model": "Claude Opus 4",
                "role": "主体（実行責任）",
                "opinion": claude_opinion
            },
            "reference": {
                "model": "Gemini 1.5 Pro",
                "role": "参考（代替視点）",
                "opinion": gemini_opinion or "（取得失敗）"
            }
        }
        
        return result
    
    def format_comparison(self, result: Dict) -> str:
        """比較結果を整形して表示"""
        output = []
        output.append("=" * 60)
        output.append(f"📋 質問: {result['question']}")
        output.append("=" * 60)
        output.append("")
        
        # 主体意見 (Claude)
        output.append("┌" + "─" * 58 + "┐")
        output.append(f"│ 🎯 {result['primary']['model']} ({result['primary']['role']})")
        output.append("├" + "─" * 58 + "┤")
        for line in result['primary']['opinion'].split('\n'):
            output.append(f"│ {line}")
        output.append("└" + "─" * 58 + "┘")
        output.append("")
        
        # 参考意見 (Gemini)
        output.append("┌" + "─" * 58 + "┐")
        output.append(f"│ 💡 {result['reference']['model']} ({result['reference']['role']})")
        output.append("├" + "─" * 58 + "┤")
        for line in result['reference']['opinion'].split('\n'):
            output.append(f"│ {line}")
        output.append("└" + "─" * 58 + "┘")
        output.append("")
        
        output.append("👤 どちらを採用しますか？ [A: Claude / B: Gemini / C: 統合]")
        
        return "\n".join(output)


# 使用例
if __name__ == "__main__":
    advisor = MultiModelAdvisor()
    
    # Claude の意見（主体）
    claude_opinion = """
1. PDFパラグラフ検出にはPyMuPDFのブロック→パラグラフ解析を使用
2. マルチカラムはX座標クラスタリングで検出
3. OCRフォールバックでスキャンPDFに対応
4. 見出し判定はフォントサイズ比較で実装
"""
    
    question = "PDF からの長文パラグラフ検出において、最適なアプローチは？"
    
    result = advisor.compare(question, claude_opinion)
    print(advisor.format_comparison(result))
