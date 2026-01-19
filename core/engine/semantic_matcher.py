from typing import List, Any
from app.core.paragraph_matcher import SyncPair
from app.core.cluster_matcher import AnchorMatcher, RangeOptimizationSimulator

class SemanticMatcher:
    """
    Genius Edition Core Logic
    Handles high-level matching strategies beyond simple text comparison.
    """
    
    def optimize_and_anchor(self, web_regions: List[Any], pdf_regions: List[Any], current_pairs: List[SyncPair]) -> List[SyncPair]:
        """
        既存のペアリングに対して、範囲最適化とアンカー構造マッチングを適用する
        Genius Hybrid Strategy:
        1. Range Optimization (微細なズレの補正)
        2. Anchor Matching (構造的な絶対正解の適用)
        """
        print("[GeniusEngine] Starting Hybrid Optimization...")
        
        # 1. Range Optimization
        try:
            optimizer = RangeOptimizationSimulator()
            results = optimizer.optimize_all_pairs(web_regions, pdf_regions, current_pairs)
            if results:
                print(f"[GeniusEngine] Range Optimized: {len(results)} pairs")
        except Exception as e:
            print(f"[GeniusEngine] Range Optimization skipped: {e}")

        # 2. Anchor Matching
        try:
            anchor_matcher = AnchorMatcher()
            anchor_matches = anchor_matcher.match_clusters(web_regions, pdf_regions)
            
            if anchor_matches:
                print(f"[GeniusEngine] Anchor Matches: {len(anchor_matches)} pairs")
                
                # Update pairs and regions
                # Note: This modifies regions in-place (Reference passing)
                
                # Pair lookup map for speed
                pair_map = {p.web_id: p for p in current_pairs}
                
                for m in anchor_matches:
                    # Apply to Regions
                    m.web_region.similarity = m.similarity
                    m.web_region.sync_color = "#9C27B0" # Magenta for Anchor Lock
                    
                    if m.pdf_region:
                        m.pdf_region.similarity = m.similarity
                        m.pdf_region.sync_color = "#9C27B0"
                    
                    # Apply to SyncList
                    # Anchor Match is considered "Truth", so we overwrite probability
                    if m.web_region.area_code in pair_map:
                        pair = pair_map[m.web_region.area_code]
                        pair.similarity = m.similarity
                        # Ensure PDF ID matches the anchor truth
                        if m.pdf_region and pair.pdf_id != m.pdf_region.area_code:
                            pair.pdf_id = m.pdf_region.area_code
                            # Ideally we should update text too, but that requires lookup
                            
        except Exception as e:
            print(f"[GeniusEngine] Anchor Match failed: {e}")
            import traceback
            traceback.print_exc()
            
        return current_pairs
