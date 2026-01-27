"""
Test Script for Gemini Embedding SDK
Verifies embedding generation and semantic similarity search.
"""
import sys
import io
import os
from pathlib import Path

# Windows UTF-8 support
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ★ Ensure Config.load_keys() is called FIRST before any SDK import
from config import Config
Config.load_keys()



def test_embedding_client():
    """Test GeminiEmbeddingClient directly"""
    print("=" * 60)
    print("🧪 Test 1: GeminiEmbeddingClient")
    print("=" * 60)
    
    from app.sdk.llm import GeminiEmbeddingClient
    
    client = GeminiEmbeddingClient()
    
    if not client.is_available():
        print("❌ Client not available (check API key)")
        return False
    
    print("✅ Client initialized")
    
    # Test single embedding
    text1 = "鎮國寺は福岡県宗像市にある歴史ある寺院です"
    vec1 = client.embed_text(text1)
    
    if vec1 is None:
        print("❌ Failed to generate embedding")
        return False
    
    print(f"✅ Embedding generated: {len(vec1)} dimensions")
    
    # Test similarity
    text2 = "鎮國寺は福岡にあるお寺"  # Similar
    text3 = "東京タワーの高さは333メートル"  # Different
    
    vec2 = client.embed_text(text2)
    vec3 = client.embed_text(text3)
    
    if vec2 and vec3:
        sim_similar = client.cosine_similarity(vec1, vec2)
        sim_different = client.cosine_similarity(vec1, vec3)
        
        print(f"   Similar texts similarity: {sim_similar:.4f}")
        print(f"   Different texts similarity: {sim_different:.4f}")
        
        if sim_similar > sim_different:
            print("✅ Similarity scoring is correct!")
        else:
            print("⚠️ Similarity scoring may be incorrect")
    
    return True


def test_embedding_search():
    """Test EmbeddingSimilarSearch"""
    print("\n" + "=" * 60)
    print("🧪 Test 2: EmbeddingSimilarSearch")
    print("=" * 60)
    
    from app.sdk.similarity import EmbeddingSimilarSearch
    
    search = EmbeddingSimilarSearch(threshold=0.5)
    
    # Test data
    query = "福岡県にある歴史的なお寺"
    candidates = [
        {"id": "P001", "text": "鎮國寺は福岡県宗像市にある真言宗御室派の寺院"},
        {"id": "P002", "text": "東京スカイツリーは高さ634メートルの電波塔"},
        {"id": "P003", "text": "福岡市内の観光名所について"},
        {"id": "P004", "text": "京都の金閣寺は有名な観光地です"},
    ]
    
    print(f"Query: {query}")
    print(f"Candidates: {len(candidates)}")
    
    results = search.find_similar(query, candidates, top_k=3)
    
    print(f"\n📊 Results ({len(results)} matches):")
    for r in results:
        print(f"   #{r.rank} [{r.candidate_id}] Score: {r.similarity_score:.4f}")
        print(f"       {r.candidate_text[:50]}...")
    
    # Check stats
    stats = search.get_stats()
    print(f"\n📈 Stats: {stats}")
    
    return len(results) > 0


def test_similarity_matrix():
    """Test similarity matrix computation"""
    print("\n" + "=" * 60)
    print("🧪 Test 3: Similarity Matrix")
    print("=" * 60)
    
    from app.sdk.similarity import EmbeddingSimilarSearch
    
    search = EmbeddingSimilarSearch()
    
    texts1 = ["福岡県の寺院", "東京の観光地"]
    texts2 = ["福岡のお寺", "京都の神社", "東京スカイツリー"]
    
    print(f"Texts1: {texts1}")
    print(f"Texts2: {texts2}")
    
    matrix = search.compute_similarity_matrix(texts1, texts2)
    
    print("\n📊 Similarity Matrix:")
    print("        ", end="")
    for t in texts2:
        print(f" {t[:8]:8}", end="")
    print()
    
    for i, row in enumerate(matrix):
        print(f"{texts1[i][:8]:8}", end="")
        for val in row:
            print(f" {val:8.4f}", end="")
        print()
    
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 MEKIKI Gemini Embedding SDK Test")
    print("=" * 60 + "\n")
    
    try:
        result1 = test_embedding_client()
        result2 = test_embedding_search()
        result3 = test_similarity_matrix()
        
        print("\n" + "=" * 60)
        print("📋 Summary")
        print("=" * 60)
        print(f"  Embedding Client: {'✅ PASS' if result1 else '❌ FAIL'}")
        print(f"  Embedding Search: {'✅ PASS' if result2 else '❌ FAIL'}")
        print(f"  Similarity Matrix: {'✅ PASS' if result3 else '❌ FAIL'}")
        
        if all([result1, result2, result3]):
            print("\n🎉 All tests passed!")
        else:
            print("\n⚠️ Some tests failed")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
