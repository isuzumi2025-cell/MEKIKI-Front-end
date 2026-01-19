"""
SDK LLM Client - Multi-Provider Support
Gemini, ChatGPT, Grok対応マルチLLMクライアント

Usage:
    from app.sdk.llm import GeminiClient, ChatGPTClient
    
    # Gemini (default)
    client = GeminiClient(model="gemini-2.0-flash")
    result = client.generate("Hello")
    
    # Gemini 3.0 (experimental)
    client = GeminiClient(model="gemini-3.0-flash")
    
    # ChatGPT (long context)
    client = ChatGPTClient(model="gpt-4-turbo")
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from dataclasses import dataclass
import os


@dataclass
class LLMResponse:
    """LLMレスポンス"""
    text: str
    model: str
    tokens_used: int = 0
    error: Optional[str] = None


class LLMClient(ABC):
    """LLMクライアント基底クラス"""
    
    @abstractmethod
    def generate(self, prompt: str, images: Optional[List[Any]] = None) -> Optional[str]:
        """テキスト生成"""
        pass
    
    @abstractmethod
    def analyze(self, text: str, instruction: str) -> Optional[str]:
        """テキスト分析"""
        pass


class GeminiClient(LLMClient):
    """
    Google Gemini Client
    
    Supported models:
    - gemini-2.0-flash (default, fast)
    - gemini-2.0-flash-lite (faster, less accurate)
    - gemini-3.0-flash (experimental, more accurate)
    """
    
    SUPPORTED_MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite", 
        "gemini-3.0-flash",  # Experimental
    ]
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model_name = model
        self.model = None
        
        try:
            import google.generativeai as genai
            from config import Config
            
            # ★ Config.load_keys() を呼び出してAPIキーを確実に読み込む
            if hasattr(Config, 'load_keys'):
                try:
                    Config.load_keys()
                except:
                    pass
            
            api_key = getattr(Config, 'GEMINI_API_KEY', None) or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                print("⚠️ GEMINI_API_KEY not set")
                return
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model)
            print(f"✅ Gemini Client: {model}")
        except Exception as e:
            print(f"❌ Gemini init error: {e}")
    
    def generate(self, prompt: str, images: Optional[List[Any]] = None) -> Optional[str]:
        if not self.model:
            return None
        try:
            contents = [prompt]
            if images:
                contents.extend(images)
            response = self.model.generate_content(contents)
            return response.text if response and hasattr(response, 'text') else None
        except Exception as e:
            print(f"❌ Gemini error: {e}")
            return None
    
    def analyze(self, text: str, instruction: str) -> Optional[str]:
        prompt = f"{instruction}\n\nTarget Text:\n{text}"
        return self.generate(prompt)
    
    def generate_with_image(self, prompt: str, image_b64: str) -> Optional[str]:
        """
        Base64エンコード画像を使用してテキスト生成
        
        Args:
            prompt: プロンプト
            image_b64: Base64エンコードされた画像データ
            
        Returns:
            生成されたテキスト
        """
        if not self.model:
            print("[GeminiOCR] No model available")
            return None
        try:
            import base64
            import io
            from PIL import Image
            
            # Base64デコード
            image_data = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_data))
            
            print(f"[GeminiOCR] Image size: {image.size}")
            
            # Gemini APIで画像を含めて送信
            response = self.model.generate_content([prompt, image])
            
            # ★ response.text の安全なアクセス
            if response and hasattr(response, 'text') and response.text:
                print(f"[GeminiClient] Vision OCR response: {len(response.text)} chars")
                return response.text
            else:
                print("[GeminiOCR] Empty response from Gemini")
                return ""
        except Exception as e:
            print(f"❌ Gemini Vision error: {e}")
            import traceback
            traceback.print_exc()
            return None


class ChatGPTClient(LLMClient):
    """
    OpenAI ChatGPT Client
    長文・長期コンテキスト対応
    
    Supported models:
    - gpt-4-turbo (128k context)
    - gpt-4o (latest)
    - gpt-3.5-turbo (cheaper)
    """
    
    def __init__(self, model: str = "gpt-4-turbo"):
        self.model_name = model
        self.client = None
        
        try:
            from openai import OpenAI
            
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("⚠️ OPENAI_API_KEY not set")
                return
            
            self.client = OpenAI(api_key=api_key)
            print(f"✅ ChatGPT Client: {model}")
        except ImportError:
            print("⚠️ openai package not installed. Run: pip install openai")
        except Exception as e:
            print(f"❌ ChatGPT init error: {e}")
    
    def generate(self, prompt: str, images: Optional[List[Any]] = None) -> Optional[str]:
        if not self.client:
            return None
        try:
            messages = [{"role": "user", "content": prompt}]
            
            # Image support for GPT-4V
            if images:
                import base64
                from io import BytesIO
                content = [{"type": "text", "text": prompt}]
                for img in images:
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    b64 = base64.b64encode(buffer.getvalue()).decode()
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}
                    })
                messages = [{"role": "user", "content": content}]
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ ChatGPT error: {e}")
            return None
    
    def analyze(self, text: str, instruction: str) -> Optional[str]:
        prompt = f"{instruction}\n\nText:\n{text}"
        return self.generate(prompt)


class GrokClient(LLMClient):
    """
    xAI Grok Client
    クリエイティブ評価用
    
    Note: Grok API is currently in beta
    """
    
    def __init__(self, model: str = "grok-1"):
        self.model_name = model
        self.client = None
        
        try:
            api_key = os.environ.get("GROK_API_KEY")
            if not api_key:
                print("⚠️ GROK_API_KEY not set")
                return
            
            # Grok uses OpenAI-compatible API
            from openai import OpenAI
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1"  # xAI endpoint
            )
            print(f"✅ Grok Client: {model}")
        except ImportError:
            print("⚠️ openai package not installed")
        except Exception as e:
            print(f"❌ Grok init error: {e}")
    
    def generate(self, prompt: str, images: Optional[List[Any]] = None) -> Optional[str]:
        if not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Grok error: {e}")
            return None
    
    def analyze(self, text: str, instruction: str) -> Optional[str]:
        prompt = f"{instruction}\n\n{text}"
        return self.generate(prompt)


# Convenience factory
def get_llm_client(provider: str = "gemini", model: Optional[str] = None) -> LLMClient:
    """
    LLMクライアント取得
    
    Args:
        provider: "gemini", "chatgpt", "grok"
        model: Model name (optional)
    
    Returns:
        LLMClient instance
    """
    if provider == "chatgpt":
        return ChatGPTClient(model=model or "gpt-4-turbo")
    elif provider == "grok":
        return GrokClient(model=model or "grok-1")
    else:
        return GeminiClient(model=model or "gemini-2.0-flash")
