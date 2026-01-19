import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.llm_client import LLMClient
from config import Config

def test_llm_integration():
    print(f"🔧 Testing API Key Integration...")
    print(f"   Key loaded: {'Yes' if Config.GEMINI_API_KEY else 'No'}")
    if Config.GEMINI_API_KEY:
        print(f"   Key prefix: {Config.GEMINI_API_KEY[:4]}...")
    
    print("\n🤖 Initializing LLM Client...")
    client = LLMClient()
    
    if not client.model:
        print("❌ LLM Client failed to initialize.")
        return
        
    print("\n🧪 Running simple generation test...")
    response = client.generate_content("Hello! Please reply with 'System Operational'.")
    
    print("\n📝 Response:")
    print("-" * 20)
    print(response)
    print("-" * 20)
    
    if response and "Operational" in response:
        print("\n✅ SUCCESS: API Key is working and LLM is responding.")
    else:
        print("\n⚠️ WARNING: Response received but logic check failed (or response was empty).")

if __name__ == "__main__":
    test_llm_integration()
