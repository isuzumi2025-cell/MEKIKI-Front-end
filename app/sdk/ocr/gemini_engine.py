"""
Gemini OCR Engine
Google Gemini を直接使用したOCRエンジン（高速版）

Supports:
- gemini-2.0-flash (default, fast)
- gemini-2.0-flash-lite (faster)
"""
import json
import re
import os
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from PIL import Image


class GeminiOCREngine:
    """
    Google Geminiを使用したOCRエンジン（直接API呼び出し版）
    """
    
    SUPPORTED_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        """初期化"""
        self.model_name = model
        self.model = None
        self._is_initialized = False
        
        try:
            import google.generativeai as genai
            
            # JSONファイルから直接APIキーを読み込み（Config経由せず）
            api_key = None
            possible_paths = [
                Path(__file__).parents[3] / "config" / "api_keys.json",
                Path.cwd() / "config" / "api_keys.json",
                Path.cwd().parent / "config" / "api_keys.json",
            ]
            
            for key_path in possible_paths:
                if key_path.exists():
                    try:
                        with open(key_path, 'r') as f:
                            keys = json.load(f)
                        api_key = keys.get('gemini_api_key')
                        if api_key:
                            print(f"✅ API key from: {key_path.name}")
                            break
                    except:
                        pass
            
            # 環境変数からのフォールバック
            if not api_key:
                api_key = os.environ.get("GEMINI_API_KEY")
            
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model)
                self._is_initialized = True
                print(f"✅ GeminiOCREngine: {model}")
            else:
                print("⚠️ GEMINI_API_KEY not found")
        except Exception as e:
            print(f"❌ GeminiOCREngine init error: {e}")
    
    def initialize(self) -> bool:
        """初期化ステータスを返す"""
        return self._is_initialized
        
    def detect_document_text(self, image_source: Any) -> Optional[Dict]:
        """
        画像からドキュメントテキストを検出（ブロック情報付き）
        """
        if not self._is_initialized or not self.model:
            print("⚠️ Gemini OCR Engine is not initialized.")
            return None
            
        try:
            pil_image = None
            
            # 画像読み込み
            if isinstance(image_source, str):
                if not Path(image_source).exists():
                    print(f"⚠️ Image not found: {image_source}")
                    return None
                pil_image = Image.open(image_source)
                print(f"🔍 Gemini OCR: {Path(image_source).name}")
            elif isinstance(image_source, Image.Image):
                pil_image = image_source
                print(f"🔍 Gemini OCR: In-memory Image")
            else:
                print(f"⚠️ Invalid image source type: {type(image_source)}")
                return None
            
            # プロンプト作成
            prompt = """Analyze this document image and extract all text blocks.
Return a purely valid JSON object (no markdown formatting).
The JSON should have the following structure:
{
    "blocks": [
        {
            "text": "Extracted text content",
            "bbox": [ymin, xmin, ymax, xmax],
            "type": "BLOCK"
        }
    ]
}

- "bbox" should be normalized coordinates (0-1000) integer values.
- Try to group text into logical paragraphs or blocks.
- Extract ALL text visible in the image."""
            
            import time
            start_time = time.time()
            
            # 直接API呼び出し（タイムアウト60秒）
            response = self.model.generate_content(
                [prompt, pil_image],
                request_options={"timeout": 60}
            )
            
            elapsed = time.time() - start_time
            print(f"[DEBUG] Gemini OCR API: {elapsed:.1f}s")
            
            if not response or not hasattr(response, 'text'):
                print("⚠️ Gemini returned no response.")
                return None
                
            # JSON解析
            result = self._parse_json_response(response.text, pil_image.size)
            
            if result:
                print(f"✅ Gemini OCR Complete: {len(result['blocks'])} blocks")
                return result
            else:
                print("⚠️ Failed to parse Gemini response.")
                return None
                
        except Exception as e:
            print(f"❌ Gemini OCR Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_json_response(self, response_text: str, image_size: Tuple[int, int]) -> Optional[Dict]:
        """Geminiのレスポンス（JSON文字列）をパースして正規化"""
        try:
            # Markdownコードブロック除去
            cleaned_text = re.sub(r"```json\s*", "", response_text)
            cleaned_text = re.sub(r"```\s*$", "", cleaned_text)
            cleaned_text = cleaned_text.strip()
            
            data = json.loads(cleaned_text)
            blocks = data.get("blocks", [])
            
            width, height = image_size
            
            normalized_blocks = []
            full_text_parts = []
            
            for block in blocks:
                text = block.get("text", "").strip()
                if not text:
                    continue
                    
                full_text_parts.append(text)
                
                # bbox正規化 (0-1000 -> pixel coords)
                # Gemini format: [ymin, xmin, ymax, xmax] (0-1000)
                # OCREngine format: [x0, y0, x1, y1] (pixel)
                bbox_norm = block.get("bbox", [0, 0, 0, 0])
                
                if len(bbox_norm) == 4:
                    ymin, xmin, ymax, xmax = bbox_norm
                    
                    # Convert to pixel coordinates
                    x0 = int((xmin / 1000) * width)
                    y0 = int((ymin / 1000) * height)
                    x1 = int((xmax / 1000) * width)
                    y1 = int((ymax / 1000) * height)
                    
                    normalized_blocks.append({
                        "text": text,
                        "bbox": [x0, y0, x1, y1],
                        "confidence": 0.95, # Mock confidence
                        "type": "BLOCK"
                    })
            
            return {
                "full_text": "\n".join(full_text_parts),
                "blocks": normalized_blocks
            }
            
        except json.JSONDecodeError:
            print(f"❌ JSON Parse Error. Response was:\n{response_text}")
            return None
        except Exception as e:
            print(f"❌ Parse Logic Error: {e}")
            return None
