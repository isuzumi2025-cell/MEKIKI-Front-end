"""Direct Gemini consultation on refactoring strategy"""
import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

response = model.generate_content('''
OCR画像のリンク問題が解決しない。リファクタリングを先に行い、問題を切り分けるアプローチについて評価して。

コンテキスト:
- HybridOCR + Canvas表示 + サムネイル連携
- 座標変換問題（pair.bbox vs region.rect）
- Page-relative座標とStitch座標の混在

質問:
1. このアプローチのメリット・デメリット
2. リファクタリングの優先順位
3. 問題特定の具体的ステップ
4. GPTは「座標変換の一元化」を優先すべきと言ったが、同意するか？

日本語で400文字以内で回答。
''')

print("【Gemini回答】")
print(response.text)
