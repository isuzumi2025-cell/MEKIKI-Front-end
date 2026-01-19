"""
MEKIKI SDK - Page Coordinate Manager
ページ単位の座標管理システム

機能:
- 各ページに領域を紐付け
- 表示画像に対応する領域のみ返却
- マルチページスクロール対応

使用例:
    from app.sdk.canvas.page_coords import PageCoordinateManager
    
    mgr = PageCoordinateManager()
    mgr.register_page(0, image, 0)
    mgr.add_region(0, region)
    regions = mgr.get_regions_for_page(0)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from PIL import Image

# ロギング設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class PageData:
    """ページデータ"""
    page_idx: int
    image: Optional[Image.Image] = None
    offset_y: int = 0  # 縦スクロール時のY座標オフセット
    height: int = 0
    width: int = 0
    regions: List[Any] = field(default_factory=list)
    source: str = ""  # "web" or "pdf"
    
    def __post_init__(self):
        if self.image:
            self.width, self.height = self.image.size


@dataclass
class RegionBinding:
    """領域とページのバインディング"""
    region: Any
    page_idx: int
    local_rect: Tuple[int, int, int, int]  # ページ内のローカル座標
    global_rect: Tuple[int, int, int, int]  # 全体の絶対座標


class PageCoordinateManager:
    """
    ページ単位の座標管理
    
    ★ 目的:
    - 各ページに領域を紐付けて座標ズレを防止
    - 表示中のページに該当する領域のみ返却
    - マルチページ表示時の座標変換を一元管理
    """
    
    def __init__(self, source: str = ""):
        """
        Args:
            source: ソースタイプ ("web" or "pdf")
        """
        self.source = source
        self.pages: Dict[int, PageData] = {}
        self.bindings: List[RegionBinding] = []
        self._cumulative_height = 0
        
        logger.info(f"PageCoordinateManager initialized (source={source})")
    
    def register_page(
        self, 
        page_idx: int, 
        image: Optional[Image.Image] = None,
        offset_y: Optional[int] = None
    ) -> PageData:
        """
        ページを登録
        
        Args:
            page_idx: ページインデックス (0-based)
            image: ページ画像 (PIL Image)
            offset_y: Y座標オフセット (None時は自動計算)
        
        Returns:
            登録されたPageData
        """
        if offset_y is None:
            offset_y = self._cumulative_height
        
        page = PageData(
            page_idx=page_idx,
            image=image,
            offset_y=offset_y,
            source=self.source
        )
        
        self.pages[page_idx] = page
        
        if image:
            self._cumulative_height += image.height
        
        logger.info(f"Page {page_idx} registered (offset_y={offset_y}, size={page.width}x{page.height})")
        return page
    
    def add_region(self, page_idx: int, region: Any) -> Optional[RegionBinding]:
        """
        領域をページに紐付け
        
        Args:
            page_idx: 紐付け先ページインデックス
            region: 領域オブジェクト (EditableRegion等)
        
        Returns:
            作成されたRegionBinding (ページが未登録の場合None)
        """
        if page_idx not in self.pages:
            logger.warning(f"Page {page_idx} not registered, cannot add region")
            return None
        
        page = self.pages[page_idx]
        
        # 領域の座標を取得
        if hasattr(region, 'rect') and len(region.rect) >= 4:
            local_rect = tuple(region.rect[:4])
        else:
            logger.warning(f"Region has no valid rect: {region}")
            return None
        
        # グローバル座標を計算 (Y座標にページオフセットを加算)
        global_rect = (
            local_rect[0],
            local_rect[1] + page.offset_y,
            local_rect[2],
            local_rect[3] + page.offset_y
        )
        
        binding = RegionBinding(
            region=region,
            page_idx=page_idx,
            local_rect=local_rect,
            global_rect=global_rect
        )
        
        self.bindings.append(binding)
        page.regions.append(region)
        
        logger.debug(f"Region bound to page {page_idx}: local={local_rect}, global={global_rect}")
        return binding
    
    def get_regions_for_page(self, page_idx: int) -> List[Any]:
        """
        指定ページに紐付けられた領域のみ返却
        
        Args:
            page_idx: ページインデックス
        
        Returns:
            該当ページの領域リスト
        """
        if page_idx not in self.pages:
            return []
        
        regions = self.pages[page_idx].regions
        logger.debug(f"Returning {len(regions)} regions for page {page_idx}")
        return regions
    
    def get_page_for_y(self, global_y: int) -> Optional[int]:
        """
        Y座標からページインデックスを取得
        
        Args:
            global_y: グローバルY座標
        
        Returns:
            該当するページインデックス (該当なしの場合None)
        """
        for page_idx, page in self.pages.items():
            if page.offset_y <= global_y < page.offset_y + page.height:
                return page_idx
        return None
    
    def global_to_local(self, global_x: int, global_y: int) -> Tuple[int, int, int]:
        """
        グローバル座標をローカル座標に変換
        
        Args:
            global_x: グローバルX座標
            global_y: グローバルY座標
        
        Returns:
            (page_idx, local_x, local_y)
        """
        page_idx = self.get_page_for_y(global_y)
        if page_idx is None:
            return (-1, global_x, global_y)
        
        page = self.pages[page_idx]
        local_y = global_y - page.offset_y
        
        return (page_idx, global_x, local_y)
    
    def local_to_global(self, page_idx: int, local_x: int, local_y: int) -> Tuple[int, int]:
        """
        ローカル座標をグローバル座標に変換
        
        Args:
            page_idx: ページインデックス
            local_x: ローカルX座標
            local_y: ローカルY座標
        
        Returns:
            (global_x, global_y)
        """
        if page_idx not in self.pages:
            return (local_x, local_y)
        
        page = self.pages[page_idx]
        global_y = local_y + page.offset_y
        
        return (local_x, global_y)
    
    def clear(self):
        """全データをクリア"""
        self.pages.clear()
        self.bindings.clear()
        self._cumulative_height = 0
        logger.info("PageCoordinateManager cleared")
    
    def get_stats(self) -> dict:
        """統計情報を取得"""
        return {
            'source': self.source,
            'page_count': len(self.pages),
            'region_count': len(self.bindings),
            'total_height': self._cumulative_height
        }
    
    def __repr__(self):
        stats = self.get_stats()
        return f"PageCoordinateManager({stats['source']}, pages={stats['page_count']}, regions={stats['region_count']})"


# ========== Convenience exports ==========
__all__ = ["PageCoordinateManager", "PageData", "RegionBinding"]
