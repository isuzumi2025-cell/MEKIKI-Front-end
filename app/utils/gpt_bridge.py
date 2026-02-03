"""
GPT-5.2 Bridge - AI間連携モジュール
Antigravity (Claude) ↔ OpenAI GPT 間の通信ブリッジ
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env読み込み（複数のパス候補を試行）
env_candidates = [
    Path(__file__).parent.parent.parent / ".env",  # app/utils/gpt_bridge.py -> OCR/.env
    Path("c:/Users/raiko/OneDrive/Desktop/26/OCR/.env"),
    Path(".env"),
]

for env_path in env_candidates:
    if env_path.exists():
        load_dotenv(env_path)
        break



def query_gpt(prompt: str, system_prompt: str = None, model: str = "gpt-4o") -> str:
    """
    GPT APIに問い合わせを送信
    
    Args:
        prompt: ユーザープロンプト
        system_prompt: システムプロンプト（オプション）
        model: 使用モデル（デフォルト: gpt-4o）
    
    Returns:
        GPTからの応答テキスト
    """
    try:
        from openai import OpenAI
    except ImportError:
        return "エラー: openai パッケージがインストールされていません。pip install openai を実行してください。"
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("#") or "sk-" not in api_key:
        return "エラー: OPENAI_API_KEY が .env に設定されていません。"
    
    try:
        client = OpenAI(api_key=api_key)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"エラー: GPT API呼び出し失敗 - {str(e)}"


def consult_gpt_strategist(problem_description: str) -> str:
    """
    GPT-5.2を戦略アドバイザーとして相談
    
    Args:
        problem_description: 現在の問題の説明
    
    Returns:
        戦略的アドバイス
    """
    system_prompt = """あなたはMEKIKI Proofing Systemの開発戦略アドバイザー（GPT-5.2）です。

【役割】
- Antigravity (Claude Code) と連携して開発を支援
- アーキテクチャ設計、デバッグ戦略、優先順位付けを担当
- 具体的で実装可能な提案を行う

【プロジェクト概要】
- Web/PDF比較校正システム
- HybridOCR (Cloud Vision + Gemini補正)
- Phase 44: 非対称混合モード対応
- 座標系: ページ相対座標 + P{page}-{seq}形式

【回答形式】
1. 問題の根本原因分析
2. 具体的な修正手順（コード例付き）
3. 優先順位とリスク評価
"""
    
    return query_gpt(problem_description, system_prompt, model="gpt-4o")


if __name__ == "__main__":
    # テスト実行
    print("=== GPT-5.2 Bridge テスト ===")
    
    test_problem = """
    【現在の問題】
    1. HybridOCR Engine が初期化に失敗する
    2. AI Analysis Mode が自動実行される（_run_ai_analysis_modeが呼ばれる）
    3. Web OCR が0件を返す（PDF: 859件は正常）
    4. area_code形式が Col0-W1_P-1 になっている（期待: P{page}-{seq}）
    
    【質問】
    この問題の根本原因と修正手順を教えてください。
    """
    
    print("\n問題を送信中...")
    response = consult_gpt_strategist(test_problem)
    print("\n=== GPT-5.2 からの回答 ===")
    print(response)
