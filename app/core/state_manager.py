"""
MEKIKI State Manager
全状態の一元管理

Created: 2026-01-28
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image
import threading


@dataclass
class EditableRegion:
    """編集可能なエリア"""
    id: int
    rect: List[int]  # [x1, y1, x2, y2]
    text: str
    area_code: str
    sync_number: Optional[int] = None
    similarity: float = 0.0
    source: str = ""  # "web" or "pdf"
    canvas_rect_id: Optional[int] = None
    canvas_text_id: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "rect": self.rect,
            "text": self.text,
            "area_code": self.area_code,
            "sync_number": self.sync_number,
            "similarity": self.similarity,
            "source": self.source
        }


@dataclass
class SyncPair:
    """Sync ペア"""
    web_region: Optional[EditableRegion] = None
    pdf_region: Optional[EditableRegion] = None
    similarity: float = 0.0
    status: str = "unmatched"  # matched, partial, unmatched


class StateManager:
    """
    全状態の一元管理
    
    責務:
    - 画像データ保持
    - 領域データ保持
    - Sync結果保持
    - 処理状態追跡
    - スレッドセーフな更新
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._reset_internal()
    
    def _reset_internal(self):
        """内部状態リセット"""
        # 画像
        self.web_image: Optional[Image.Image] = None
        self.pdf_image: Optional[Image.Image] = None
        self.web_pages: List[Image.Image] = []
        self.pdf_pages: List[Image.Image] = []
        
        # ページ
        self.current_web_page: int = 0
        self.current_pdf_page: int = 0
        self.total_web_pages: int = 0
        self.total_pdf_pages: int = 0
        
        # 領域
        self.web_regions: List[EditableRegion] = []
        self.pdf_regions: List[EditableRegion] = []
        
        # Sync
        self.sync_pairs: List[SyncPair] = []
        self.sync_rate: float = 0.0
        self.match_count: int = 0
        
        # 処理状態
        self.is_processing: bool = False
        self.current_operation: str = ""
        self.error_message: Optional[str] = None
    
    def reset(self):
        """安全なリセット"""
        with self._lock:
            self._reset_internal()
    
    def can_process(self) -> bool:
        """処理可能状態かチェック"""
        with self._lock:
            return not self.is_processing
    
    def start_operation(self, operation: str) -> bool:
        """処理開始 (排他制御)"""
        with self._lock:
            if self.is_processing:
                return False
            self.is_processing = True
            self.current_operation = operation
            self.error_message = None
            return True
    
    def end_operation(self, error: Optional[str] = None):
        """処理終了"""
        with self._lock:
            self.is_processing = False
            self.current_operation = ""
            self.error_message = error
    
    # ========== 画像管理 ==========
    
    def set_web_image(self, image: Image.Image):
        """Web画像を設定"""
        with self._lock:
            self.web_image = image
    
    def set_pdf_image(self, image: Image.Image):
        """PDF画像を設定"""
        with self._lock:
            self.pdf_image = image
    
    def get_web_image(self) -> Optional[Image.Image]:
        """Web画像を取得"""
        with self._lock:
            return self.web_image
    
    def get_pdf_image(self) -> Optional[Image.Image]:
        """PDF画像を取得"""
        with self._lock:
            return self.pdf_image
    
    # ========== 領域管理 ==========
    
    def add_web_region(self, region: EditableRegion):
        """Web領域を追加"""
        with self._lock:
            region.source = "web"
            self.web_regions.append(region)
    
    def add_pdf_region(self, region: EditableRegion):
        """PDF領域を追加"""
        with self._lock:
            region.source = "pdf"
            self.pdf_regions.append(region)
    
    def get_web_regions(self) -> List[EditableRegion]:
        """Web領域を取得"""
        with self._lock:
            return list(self.web_regions)
    
    def get_pdf_regions(self) -> List[EditableRegion]:
        """PDF領域を取得"""
        with self._lock:
            return list(self.pdf_regions)
    
    def clear_regions(self, source: str = None):
        """領域をクリア"""
        with self._lock:
            if source == "web":
                self.web_regions.clear()
            elif source == "pdf":
                self.pdf_regions.clear()
            else:
                self.web_regions.clear()
                self.pdf_regions.clear()
    
    # ========== Sync管理 ==========
    
    def set_sync_result(self, pairs: List[SyncPair], rate: float, match_count: int):
        """Sync結果を設定"""
        with self._lock:
            self.sync_pairs = pairs
            self.sync_rate = rate
            self.match_count = match_count
    
    def get_sync_stats(self) -> Tuple[float, int, int]:
        """Sync統計を取得 (rate, matched, total)"""
        with self._lock:
            total = len(self.web_regions) + len(self.pdf_regions)
            return (self.sync_rate, self.match_count, total)
    
    # ========== スナップショット ==========
    
    def snapshot(self) -> Dict[str, Any]:
        """現在の状態のスナップショットを取得"""
        with self._lock:
            return {
                "web_page": self.current_web_page,
                "pdf_page": self.current_pdf_page,
                "web_regions_count": len(self.web_regions),
                "pdf_regions_count": len(self.pdf_regions),
                "sync_rate": self.sync_rate,
                "match_count": self.match_count,
                "is_processing": self.is_processing,
                "current_operation": self.current_operation,
                "error": self.error_message
            }


# シングルトンインスタンス
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """StateManagerシングルトン取得"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
