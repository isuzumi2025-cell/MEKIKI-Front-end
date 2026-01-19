"""
Gemini OCR Engine
Google Gemini (via LLMClient) を使用したOCRエンジン
"""
import json
import re
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from PIL import Image

from app.core.llm_client import LLMClient

class GeminiOCREngine:
    """
    Google Geminiを使用したOCRエンジン
    LLMClient経由でマルチモーダル入力を行い、テキストとレイアウト情報を取得する
    """
    
    def __init__(self):
        """初期化"""
        self.llm_client = LLMClient(model_name="gemini-2.0-flash")
        self._is_initialized = False
        
        # 初期化チェック
        if self.llm_client.model:
            self._is_initialized = True
    
    def initialize(self) -> bool:
        """初期化ステータスを返す"""
        return self._is_initialized
        
    def detect_document_text(self, image_source: Any) -> Optional[Dict]:
        """
        画像からドキュメントテキストを検出（ブロック情報付き）
        
        Args:
            image_source: 画像ファイルのパス (str) または PIL.Imageオブジェクト
        
        Returns:
            APIレスポンス辞書、失敗時None
        """
        if not self._is_initialized:
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
                print(f"🔍 Gemini OCR Processing: {Path(image_source).name}")
            elif isinstance(image_source, Image.Image):
                pil_image = image_source
                print(f"🔍 Gemini OCR Processing: In-memory Image")
            else:
                print(f"⚠️ Invalid image source type: {type(image_source)}")
                return None
            
            # プロンプト作成
            prompt = """
            Analyze this document image and extract all text blocks.
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
            
            - "bbox" should be normalized coordinates (0-1000) integer values: [ymin, xmin, ymax, xmax].
            - Try to group text into logical paragraphs or blocks.
            - Extract ALL text visible in the image.
            """
            
            # Gemini実行
            response_text = self.llm_client.generate_content(prompt, images=[pil_image])
            
            if not response_text:
                print("⚠️ Gemini returned no response.")
                return None
                
            # JSON解析
            result = self._parse_json_response(response_text, pil_image.size)
            
            if result:
                print(f"✅ Gemini OCR Complete: {len(result['blocks'])} blocks extracted")
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
