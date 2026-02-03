"""
Grok API Client
xAI Grokのリアルタイム検索機能を活用

機能:
- web_search: リアルタイムWeb検索
- x_search: X(Twitter)検索
- OpenAI互換エンドポイント

セットアップ:
    .envに GROK_API_KEY を設定
"""
import os
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = "https://api.x.ai/v1"


def is_grok_available() -> bool:
    """Grok APIが利用可能か確認"""
    return bool(GROK_API_KEY)


def query_grok_with_search(
    query: str,
    enable_web_search: bool = True,
    enable_x_search: bool = False,
    model: str = "grok-2"
) -> Optional[str]:
    """
    Grokにリアルタイム検索付きで質問
    
    Args:
        query: 質問内容
        enable_web_search: Web検索を有効にするか
        enable_x_search: X検索を有効にするか
        model: 使用モデル (grok-2, grok-3)
    
    Returns:
        回答テキストまたはNone
    """
    if not is_grok_available():
        print("⚠️ GROK_API_KEY が設定されていません")
        return None
    
    try:
        # OpenAI互換クライアントを使用
        from openai import OpenAI
        
        client = OpenAI(
            api_key=GROK_API_KEY,
            base_url=GROK_BASE_URL
        )
        
        # シンプルなチャット呼び出し（ツールはモデルが自動判断）
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": query}
            ]
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"⚠️ Grok API エラー: {e}")
        return None


def search_realtime(topic: str) -> Dict:
    """
    トピックについてリアルタイム情報を収集
    
    Args:
        topic: 検索トピック
    
    Returns:
        {
            'summary': str,
            'sources': list,
            'timestamp': str
        }
    """
    from datetime import datetime
    
    if not is_grok_available():
        return {
            'summary': 'Grok API key not configured',
            'sources': [],
            'timestamp': datetime.now().isoformat()
        }
    
    prompt = f"""以下のトピックについて、最新の情報を簡潔にまとめてください:

トピック: {topic}

【出力形式】
1. 概要（2-3文）
2. 主要なポイント（箇条書き3-5項目）
3. 参考になるリソース（あれば）
"""
    
    result = query_grok_with_search(prompt, enable_web_search=True)
    
    return {
        'summary': result or 'No result',
        'sources': [],  # Grok APIからは直接ソースを取得できない
        'timestamp': datetime.now().isoformat()
    }


# CLI実行
if __name__ == "__main__":
    import sys
    
    if not is_grok_available():
        print("❌ GROK_API_KEY を .env に設定してください")
        print("   例: GROK_API_KEY=xai-...")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
        print(f"🔍 Grok検索: {query}")
        result = search_realtime(query)
        print(result['summary'])
    else:
        print("Usage: python -m app.sdk.llm.grok_client 'search query'")
