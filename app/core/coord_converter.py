\"\"\"
座標変換ユーティリティ - 統一座標系管理

全ての座標変換はこのクラスを通して行う。
PDF座標 ⇔ 画像座標 ⇔ Canvas座標 の変換を一元管理。
\"\"\"

from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class BBox:
    \"\"\"座標ボックス (x1, y1, x2, y2)\"\"\"
    x1: float
    y1: float
    x2: float
    y2: float
    
    def to_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]
    
    @classmethod
    def from_list(cls, coords: List[float]) -> 'BBox':
        return cls(coords[0], coords[1], coords[2], coords[3])
    
    @property
    def width(self) -> float:
        return self.x2 - self.x1
    
    @property
    def height(self) -> float:
        return self.y2 - self.y1
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


class CoordConverter:
    \"\"\"
    座標変換の統一インターフェース
    
    変換フロー:
    PDF座標 (72 DPI) → 画像座標 (300 DPI) → Canvas座標 (scale + offset)
    \"\"\"
    
    def __init__(self, pdf_dpi: int = 72, image_dpi: int = 300):
        self.pdf_dpi = pdf_dpi
        self.image_dpi = image_dpi
        self.dpi_scale = image_dpi / pdf_dpi  # 4.1667
        
        # ページオフセット管理（縦連結対応）
        self._page_offsets: List[int] = []
    
    def add_page_offset(self, page_height: int):
        \"\"\"ページを追加し、次ページ用のオフセットを計算\"\"\"
        if not self._page_offsets:
            self._page_offsets.append(0)
        else:
            self._page_offsets.append(self._page_offsets[-1] + page_height)
    
    def get_page_offset(self, page_num: int) -> int:
        \"\"\"指定ページのY軸オフセットを取得 (0-indexed)\"\"\"
        if page_num < len(self._page_offsets):
            return self._page_offsets[page_num]
        return 0
    
    def reset_pages(self):
        \"\"\"ページオフセットをリセット\"\"\"
        self._page_offsets = []
    
    # ========== PDF → 画像座標変換 ==========
    
    def pdf_to_image(self, bbox: BBox, page_num: int = 0) -> BBox:
        \"\"\"
        PDF座標を画像座標に変換
        
        Args:
            bbox: PDF座標系のBBox (72 DPI基準)
            page_num: ページ番号 (0-indexed)
        
        Returns:
            画像座標系のBBox (300 DPI基準、縦連結オフセット込み)
        \"\"\"
        y_offset = self.get_page_offset(page_num)
        
        return BBox(
            x1=int(bbox.x1 * self.dpi_scale),
            y1=int(bbox.y1 * self.dpi_scale + y_offset),
            x2=int(bbox.x2 * self.dpi_scale),
            y2=int(bbox.y2 * self.dpi_scale + y_offset)
        )
    
    def pdf_to_image_list(self, coords: List[float], page_num: int = 0) -> List[int]:
        \"\"\"リスト形式での変換（後方互換性）\"\"\"
        bbox = BBox.from_list(coords)
        result = self.pdf_to_image(bbox, page_num)
        return [int(x) for x in result.to_list()]
    
    # ========== 画像座標 → Canvas座標変換 ==========
    
    def image_to_canvas(
        self, 
        bbox: BBox, 
        scale_x: float = 1.0, 
        scale_y: float = 1.0,
        offset_x: float = 0,
        offset_y: float = 0
    ) -> BBox:
        \"\"\"
        画像座標をCanvas座標に変換
        
        Args:
            bbox: 画像座標系のBBox
            scale_x, scale_y: Canvasのスケール係数
            offset_x, offset_y: Canvasのオフセット
        
        Returns:
            Canvas座標系のBBox
        \"\"\"
        return BBox(
            x1=bbox.x1 * scale_x + offset_x,
            y1=bbox.y1 * scale_y + offset_y,
            x2=bbox.x2 * scale_x + offset_x,
            y2=bbox.y2 * scale_y + offset_y
        )
    
    def image_to_canvas_list(
        self,
        coords: List[float],
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        offset_x: float = 0,
        offset_y: float = 0
    ) -> List[float]:
        \"\"\"リスト形式での変換（後方互換性）\"\"\"
        bbox = BBox.from_list(coords)
        result = self.image_to_canvas(bbox, scale_x, scale_y, offset_x, offset_y)
        return result.to_list()
    
    # ========== 複合変換 ==========
    
    def pdf_to_canvas(
        self,
        bbox: BBox,
        page_num: int,
        scale_x: float,
        scale_y: float,
        offset_x: float = 0,
        offset_y: float = 0
    ) -> BBox:
        \"\"\"PDF座標を直接Canvas座標に変換\"\"\"
        image_bbox = self.pdf_to_image(bbox, page_num)
        return self.image_to_canvas(image_bbox, scale_x, scale_y, offset_x, offset_y)


# シングルトンインスタンス（グローバル使用用）
_default_converter: Optional[CoordConverter] = None


def get_converter() -> CoordConverter:
    \"\"\"デフォルトのCoordConverterを取得\"\"\"
    global _default_converter
    if _default_converter is None:
        _default_converter = CoordConverter()
    return _default_converter


def reset_converter():
    \"\"\"デフォルトConverterをリセット\"\"\"
    global _default_converter
    _default_converter = None
