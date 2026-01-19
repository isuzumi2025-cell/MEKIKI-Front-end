from dataclasses import dataclass, field
from typing import List, Optional, Dict
import threading

@dataclass
class RegionData:
    """統一領域データモデル (Immutable推奨)"""
    id: str
    text: str
    rect: List[int]  # [x1, y1, x2, y2]
    source: str      # 'web' or 'pdf'
    similarity: float = 0.0
    matched_id: Optional[str] = None
    
    @property
    def area_code(self) -> str:
        return self.id

@dataclass
class SyncPairData:
    """シンクロペアデータ"""
    web_id: str
    pdf_id: str
    similarity: float
    web_text: str
    pdf_text: str
    diff_html: Optional[str] = None  # 将来的なDiff表示用
    
    @property
    def is_perfect(self) -> bool:
        return self.similarity >= 0.99

class ComparisonState:
    """
    アプリケーションの全状態を管理するSingle Source of Truth
    スレッドセーフな更新通知機能を持つ
    """
    def __init__(self):
        self._web_regions: Dict[str, RegionData] = {}
        self._pdf_regions: Dict[str, RegionData] = {}
        self._sync_pairs: List[SyncPairData] = []
        self._listeners = []
        self._lock = threading.RLock()
        
    def set_regions(self, source: str, regions: List[RegionData]):
        with self._lock:
            target = self._web_regions if source == 'web' else self._pdf_regions
            target.clear()
            for r in regions:
                target[r.id] = r
            self._notify_update(f"{source}_regions")
            
    def update_matches(self, pairs: List[SyncPairData]):
        with self._lock:
            self._sync_pairs = sorted(pairs, key=lambda x: x.similarity, reverse=True)
            
            # Region側の属性も更新
            for pair in pairs:
                if pair.web_id in self._web_regions:
                    self._web_regions[pair.web_id].similarity = pair.similarity
                    self._web_regions[pair.web_id].matched_id = pair.pdf_id
                if pair.pdf_id in self._pdf_regions:
                    self._pdf_regions[pair.pdf_id].similarity = pair.similarity
                    self._pdf_regions[pair.pdf_id].matched_id = pair.web_id
                    
            self._notify_update("matches")
            
    def get_sync_pairs(self) -> List[SyncPairData]:
        with self._lock:
            return list(self._sync_pairs)
            
    def get_sync_rate(self) -> float:
        with self._lock:
            if not self._web_regions: return 0.0
            matched = sum(1 for p in self._sync_pairs if p.similarity >= 0.5) # 閾値
            return (matched / len(self._web_regions)) * 100
            
    def add_listener(self, callback):
        self._listeners.append(callback)
        
    def _notify_update(self, event_type: str):
        for cb in self._listeners:
            cb(event_type)
