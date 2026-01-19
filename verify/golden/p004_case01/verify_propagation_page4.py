import sys
import os
import json
from PIL import Image

# Add project root to path
# Add project root to path
sys.path.append(os.getcwd())
# Ensure UTF-8 output for Windows Console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.core.structure_propagator import StructurePropagator

def verify_page4_propagation():
    print("=== P-004 Verification: Template Propagation (Page 4 Adaptation) ===")
    
    # 1. Load Data
    json_path = r"c:\Users\raiko\OneDrive\Desktop\26\OCR\project_data.json"
    img_path = r"c:\Users\raiko\OneDrive\Desktop\26\OCR\saved project\2502_寺社_パンフ_07 (1)_ページ_4.jpg"
    
    if not os.path.exists(json_path) or not os.path.exists(img_path):
        print(f"FAIL: Data files not found. JSON: {os.path.exists(json_path)}, IMG: {os.path.exists(img_path)}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    raw_clusters = data.get('clusters', [])
    print(f"Loaded {len(raw_clusters)} clusters from project_data.json")
    
    # 2. Setup Propagator
    propagator = StructurePropagator()
    
    # 3. Simulate "Manual Template Selection"
    # Target: ID 11 "30 Mizuta Tenmangu"
    # We simulate the user selecting the region and cleaning the text to be the "Header"
    # The raw text is messy: "福岡\n... 30水田天満宮..."
    # User would likely select the box and maybe ensures it represents the block.
    # The Propagator expects a "Template Region".
    
    template_cluster = next((c for c in raw_clusters if c['id'] == 11), None)
    if not template_cluster:
        print("FAIL: Template ID 11 not found in data.")
        return

    # Clean text for template (Simulating user providing a clear example)
    # The propagator uses the text to find a regex pattern.
    # Let's override the text to start with "30." to see if it picks up digits.
    template_region = {
        'rect': template_cluster['rect'],
        'text': "30. Mizuta Tenmangu" # Cleaned header simulation
    }
    
    print(f"Template Selected: {template_region}")
    
    # 4. Run Propagation
    # We pass the real raw_clusters as "raw_words" (Propagator accepts dicts with rect/text)
    # We also pass the IMAGE for Visual Propagation
    try:
        image = Image.open(img_path)
        page_size = image.size
        print(f"Image Loaded: {page_size}")
        
        # ACT
        results = propagator.propagate(
            template_region,
            raw_clusters,
            page_size,
            image=image
        )
        
        # 5. Analyze Results
        print(f"\nPropagation Results: {len(results)} items found.")
        
        detected_ids = []
        for i, r in enumerate(results):
            # Try to match back to original IDs by overlap
            rect = r['rect']
            cx = (rect[0] + rect[2]) / 2
            cy = (rect[1] + rect[3]) / 2
            
            # Find closest raw cluster
            match = None
            for c in raw_clusters:
                c_rect = c['rect']
                if c_rect[0] <= cx <= c_rect[2] and c_rect[1] <= cy <= c_rect[3]:
                    match = c
                    break
            
            matched_id = match['id'] if match else "New/Unknown"
            detected_ids.append(matched_id)
            print(f" - [{i+1}] {r['rect']} Anchor: {r.get('anchor_word')} (Matched Original ID: {matched_id})")
            
        # Assertions
        # Expecting to find roughly the items on the page (IDs 1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17...)
        # Especially those with numbers "26", "27", etc.
        
        if len(results) >= 5:
            print("\nPASS: Found significant number of aligned regions.")
            print(f"Telemetry: Found {len(results)} items out of {len(raw_clusters)} clusters.")
        else:
            print("\nFAIL: Too few regions found.")
            
    except Exception as e:
        print(f"FAIL: Exception during propagation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_page4_propagation()
