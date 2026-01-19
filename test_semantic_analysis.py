import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.analyzer import ContentAnalyzer
from config import Config

def test_semantic_analysis():
    print("🔧 Testing Semantic Analysis with Gemini...")
    
    if not Config.GEMINI_API_KEY:
        print("❌ SKIPPED: No API Key found.")
        return

    text1 = """
    Product: Super Widget
    Price: $10.00
    Release Date: 2024-01-01
    DISCLAIMER: This product is beta.
    """

    text2 = """
    Product: Super Widget
    Price: $12.50
    Release Date: 2024-01-01
    """
    
    print("\n📝 Input Texts:")
    print("   Web: Price $10.00, has disclaimer")
    print("   PDF: Price $12.50, missing disclaimer")
    
    print("\n🤖 Running Analyzer...")
    analyzer = ContentAnalyzer()
    
    # Force initialization if needed
    # analyzer.llm_client = LLMClient() # analyzer does lazy load
    
    result = analyzer.analyze_semantic_difference(text1, text2)
    
    print("\n🔍 Analysis Result:")
    print("-" * 40)
    print(result)
    print("-" * 40)
    
    if "Price" in result or "disclaimer" in result or "価格" in result:
        print("\n✅ SUCCESS: LLM identified key differences.")
    else:
        print("\n⚠️ WARNING: LLM response was generic or empty.")

if __name__ == "__main__":
    test_semantic_analysis()
