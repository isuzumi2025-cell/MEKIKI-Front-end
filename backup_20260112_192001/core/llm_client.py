import google.generativeai as genai
from app.core.interface import LLMEngineStrategy
from config import Config
from typing import Optional, List, Dict, Any

class LLMClient:
    """
    Client for interacting with Google's Gemini models.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the LLM Client.
        
        Args:
            model_name: The name of the model to use (default: gemini-1.5-flash-latest)
        """
        if not Config.GEMINI_API_KEY:
            print("⚠️ Warning: GEMINI_API_KEY is not set. LLM features will not work.")
            self.model = None
            return

        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(model_name)
            print(f"✅ LLM Client initialized with model: {model_name}")
        except Exception as e:
            print(f"❌ Failed to initialize LLM Client: {e}")
            self.model = None

    def generate_content(self, prompt: str) -> Optional[str]:
        """
        Generate text content from a prompt.
        
        Args:
            prompt: The text prompt.
            
        Returns:
            The generated text, or None if failed.
        """
        if not self.model:
            print("⚠️ LLM Client is not initialized.")
            return None
            
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ LLM Generation Error: {e}")
            return None

    def analyze_text(self, text: str, instruction: str) -> Optional[str]:
        """
        Analyze text using the LLM with a specific instruction.
        
        Args:
            text: The text to analyze.
            instruction: The instruction for analysis.
            
        Returns:
            The analysis result.
        """
        prompt = f"{instruction}\n\nTarget Text:\n{text}"
        return self.generate_content(prompt)
