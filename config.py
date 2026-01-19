import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    """Application Configuration"""
    
    # Base paths
    BASE_DIR = Path(__file__).resolve().parent
    DESKTOP_DIR = Path(os.path.expanduser("~/OneDrive/Desktop/26"))
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    @classmethod
    def load_keys(cls):
        """Load API keys from api_keys.json if not found in env"""
        if cls.GEMINI_API_KEY:
            return

        key_file = cls.DESKTOP_DIR / "api_keys.json"
        
        if key_file.exists():
            try:
                with open(key_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cls.GEMINI_API_KEY = data.get("gemini_api_key")
                    
                    # Set as env var for libraries that might look for it
                    if cls.GEMINI_API_KEY:
                        os.environ["GEMINI_API_KEY"] = cls.GEMINI_API_KEY
                        # generic google generic ai key env var often used
                        os.environ["GOOGLE_API_KEY"] = cls.GEMINI_API_KEY
                        
            except Exception as e:
                print(f"⚠️ Failed to load API keys from {key_file}: {e}")
        else:
            print(f"⚠️ API Key file not found at: {key_file}")

# Initialize keys on import
Config.load_keys()
