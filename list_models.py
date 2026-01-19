import google.generativeai as genai
from config import Config

def list_models():
    if not Config.GEMINI_API_KEY:
        print("No API Key set.")
        return

    genai.configure(api_key=Config.GEMINI_API_KEY)
    
    print("Listing available models...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
