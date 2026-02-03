"""Direct GPT consultation on refactoring strategy"""
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

response = client.chat.completions.create(
    model='gpt-4o',
    messages=[{
        'role': 'user',
        'content': '''OCR画像のリンク問題が解決しない。リファクタリングを先に行い、問題を切り分けるアプローチについて評価して。

コンテキスト:
- HybridOCR + Canvas表示 + サムネイル連携
- 座標変換問題（pair.bbox vs region.rect）

質問:
1. このアプローチのメリット・デメリット
2. リファクタリングの優先順位
3. 問題特定の具体的ステップ

日本語で400文字以内で回答。'''
    }],
    max_tokens=600
)

print(response.choices[0].message.content)
