"""
Check available Gemini models
"""
import google.generativeai as genai
from config import Config

def check_models():
    genai.configure(api_key=Config.GEMINI_API_KEY)
    
    print("Available models:")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    check_models()
