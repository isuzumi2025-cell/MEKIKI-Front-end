"""
Web OCR問題診断スクリプト
HybridOCR初期化失敗とWeb OCR 0件の原因を特定
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 環境変数をロード
load_dotenv(Path("c:/Users/raiko/OneDrive/Desktop/26/OCR/.env"))

print("=" * 60)
print("Web OCR 問題診断")
print("=" * 60)

# 1. API Keys Check
print("\n[1] API Keys Check")
gemini_key = os.getenv("GEMINI_API_KEY", "")
print(f"  GEMINI_API_KEY: {'OK (starts with AIza)' if gemini_key.startswith('AIza') else 'INVALID or NOT SET'}")
print(f"  Key value: {gemini_key[:20]}..." if gemini_key else "  Key value: (empty)")

# 2. Cloud Vision Test
print("\n[2] Cloud Vision API Test")
try:
    from app.core.ocr_engine import OCREngine
    engine = OCREngine()
    init_result = engine.initialize()
    print(f"  OCREngine.initialize(): {init_result}")
except Exception as e:
    print(f"  ERROR: {e}")

# 3. LLM Client Test
print("\n[3] LLM Client Test")
try:
    from app.core.llm_client import LLMClient
    llm = LLMClient()
    print(f"  Model: {llm.model}")
    print(f"  Model is None: {llm.model is None}")
except Exception as e:
    print(f"  ERROR: {e}")

# 4. HybridOCR Test
print("\n[4] HybridOCR Engine Test")
try:
    from app.core.hybrid_ocr import HybridOCREngine
    hybrid = HybridOCREngine()
    print(f"  _is_initialized: {hybrid._is_initialized}")
    print(f"  vision_engine OK: {hybrid.vision_engine._is_initialized if hasattr(hybrid.vision_engine, '_is_initialized') else 'N/A'}")
except Exception as e:
    print(f"  ERROR: {e}")

# 5. Suggest Fix
print("\n[5] Diagnosis")
if not gemini_key.startswith("AIza"):
    print("  >>> PROBLEM: GEMINI_API_KEY is not a valid Google API key")
    print("  >>> FIX: Get key from https://aistudio.google.com/apikey")
    print("  >>> Expected format: AIzaSy...")
else:
    print("  >>> GEMINI_API_KEY looks valid")

print("\n" + "=" * 60)
