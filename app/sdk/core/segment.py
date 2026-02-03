"""
Image Segment Module
リサイズ画像セグメントのカプセル化と座標変換の一元管理

このモジュールは以下を提供:
- ImageSegment: リサイズされた画像とメタデータのカプセル化
- CoordinateConverter: 座標変換の一元管理
- SegmentCache: リサイズ結果のキャッシュ（速度改善）
"""
from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image
import io
import tempfile
import os
from pathlib import Path


@dataclass
class BBox:
    """座標情報（不変）"""
    x0: float
    y0: float
    x1: float
    y1: float
    
    @property
    def width(self) -> float:
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        return self.y1 - self.y0
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)
    
    def to_int_tuple(self) -> Tuple[int, int, int, int]:
        return (int(self.x0), int(self.y0), int(self.x1), int(self.y1))
    
    def to_list(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1]
    
    def to_int_list(self) -> List[int]:
        return [int(self.x0), int(self.y0), int(self.x1), int(self.y1)]
    
    @classmethod
    def from_tuple(cls, t: Tuple[float, float, float, float]) -> 'BBox':
        return cls(x0=t[0], y0=t[1], x1=t[2], y1=t[3])
    
    @classmethod
    def from_list(cls, lst: List[float]) -> 'BBox':
        return cls(x0=lst[0], y0=lst[1], x1=lst[2], y1=lst[3])
    
    def __repr__(self) -> str:
        return f"BBox({self.x0:.1f}, {self.y0:.1f}, {self.x1:.1f}, {self.y1:.1f})"


class CoordinateConverter:
    """
    座標変換の一元管理
    
    リサイズ前後の座標変換を正確に行う
    丸め誤差を最小限に抑える設計
    """
    
    def __init__(
        self, 
        original_size: Tuple[int, int], 
        resized_size: Tuple[int, int]
    ):
        """
        Args:
            original_size: (width, height) オリジナル画像サイズ
            resized_size: (width, height) リサイズ後サイズ
        """
        self.original_width, self.original_height = original_size
        self.resized_width, self.resized_height = resized_size
        
        # スケール係数（除算を事前計算して精度向上）
        self.scale_x = self.resized_width / self.original_width
        self.scale_y = self.resized_height / self.original_height
        
        # 逆スケール（復元用）
        self.inv_scale_x = self.original_width / self.resized_width
        self.inv_scale_y = self.original_height / self.resized_height
        
        # 統一スケール（アスペクト比維持の場合）
        self.uniform_scale = min(self.scale_x, self.scale_y)
        self.inv_uniform_scale = 1.0 / self.uniform_scale if self.uniform_scale else 1.0
    
    def to_resized(self, bbox: BBox) -> BBox:
        """オリジナル座標 → リサイズ座標"""
        return BBox(
            x0=bbox.x0 * self.scale_x,
            y0=bbox.y0 * self.scale_y,
            x1=bbox.x1 * self.scale_x,
            y1=bbox.y1 * self.scale_y
        )
    
    def to_original(self, bbox: BBox) -> BBox:
        """リサイズ座標 → オリジナル座標"""
        return BBox(
            x0=bbox.x0 * self.inv_scale_x,
            y0=bbox.y0 * self.inv_scale_y,
            x1=bbox.x1 * self.inv_scale_x,
            y1=bbox.y1 * self.inv_scale_y
        )
    
    def to_resized_uniform(self, bbox: BBox) -> BBox:
        """オリジナル座標 → リサイズ座標（アスペクト比維持）"""
        return BBox(
            x0=bbox.x0 * self.uniform_scale,
            y0=bbox.y0 * self.uniform_scale,
            x1=bbox.x1 * self.uniform_scale,
            y1=bbox.y1 * self.uniform_scale
        )
    
    def to_original_uniform(self, bbox: BBox) -> BBox:
        """リサイズ座標 → オリジナル座標（アスペクト比維持）"""
        return BBox(
            x0=bbox.x0 * self.inv_uniform_scale,
            y0=bbox.y0 * self.inv_uniform_scale,
            x1=bbox.x1 * self.inv_uniform_scale,
            y1=bbox.y1 * self.inv_uniform_scale
        )
    
    def point_to_resized(self, x: float, y: float) -> Tuple[float, float]:
        """ポイント座標変換（オリジナル → リサイズ）"""
        return (x * self.scale_x, y * self.scale_y)
    
    def point_to_original(self, x: float, y: float) -> Tuple[float, float]:
        """ポイント座標変換（リサイズ → オリジナル）"""
        return (x * self.inv_scale_x, y * self.inv_scale_y)
    
    def __repr__(self) -> str:
        return (f"CoordinateConverter("
                f"{self.original_width}x{self.original_height} → "
                f"{self.resized_width}x{self.resized_height}, "
                f"scale={self.scale_x:.4f}x{self.scale_y:.4f})")


@dataclass
class ImageSegment:
    """
    リサイズされた画像セグメントのカプセル化
    
    OCR処理やCanvas表示で使用される画像セグメントの
    メタデータと座標変換情報を一元管理
    """
    # 基本情報
    original_path: Optional[str] = None
    original_size: Tuple[int, int] = (0, 0)  # (width, height)
    resized_size: Tuple[int, int] = (0, 0)
    
    # 画像データ（オプション - 遅延ロード対応）
    _original_image: Optional[Image.Image] = field(default=None, repr=False)
    _resized_image: Optional[Image.Image] = field(default=None, repr=False)
    
    # 座標変換器
    _converter: Optional[CoordinateConverter] = field(default=None, repr=False)
    
    # メタデータ
    page_index: int = 0
    segment_id: str = ""
    source_type: str = "image"  # "image", "pdf", "screenshot"
    
    # 一時ファイルパス（OCR用）
    _temp_path: Optional[str] = field(default=None, repr=False)
    
    # 処理フラグ
    is_resized: bool = False
    max_long_edge: int = 4096  # Vision API推奨値
    
    def __post_init__(self):
        """初期化後の処理"""
        if self.original_size[0] > 0 and self.resized_size[0] > 0:
            self._converter = CoordinateConverter(self.original_size, self.resized_size)
    
    @classmethod
    def from_image(
        cls, 
        image: Image.Image, 
        max_long_edge: int = 4096,
        segment_id: str = ""
    ) -> 'ImageSegment':
        """
        PIL Imageからセグメントを作成
        
        Args:
            image: PIL Imageオブジェクト
            max_long_edge: 最大長辺（超えたらリサイズ）
            segment_id: セグメント識別子
        
        Returns:
            ImageSegment インスタンス
        """
        orig_width, orig_height = image.size
        long_edge = max(orig_width, orig_height)
        
        segment = cls(
            original_size=(orig_width, orig_height),
            segment_id=segment_id,
            max_long_edge=max_long_edge,
            _original_image=image
        )
        
        if long_edge > max_long_edge:
            # リサイズが必要
            scale = max_long_edge / long_edge
            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)
            
            resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            segment.resized_size = (new_width, new_height)
            segment._resized_image = resized
            segment.is_resized = True
            segment._converter = CoordinateConverter(
                (orig_width, orig_height), 
                (new_width, new_height)
            )
            
            print(f"📐 ImageSegment: {orig_width}x{orig_height} → {new_width}x{new_height} (scale: {scale:.3f})")
        else:
            # リサイズ不要
            segment.resized_size = (orig_width, orig_height)
            segment._resized_image = image
            segment.is_resized = False
            segment._converter = CoordinateConverter(
                (orig_width, orig_height),
                (orig_width, orig_height)
            )
        
        return segment
    
    @classmethod
    def from_path(
        cls, 
        image_path: str, 
        max_long_edge: int = 4096,
        segment_id: str = ""
    ) -> 'ImageSegment':
        """ファイルパスからセグメントを作成"""
        image = Image.open(image_path)
        segment = cls.from_image(image, max_long_edge, segment_id)
        segment.original_path = image_path
        return segment
    
    @property
    def converter(self) -> CoordinateConverter:
        """座標変換器を取得"""
        if self._converter is None:
            self._converter = CoordinateConverter(self.original_size, self.resized_size)
        return self._converter
    
    @property
    def scale_factor(self) -> float:
        """リサイズスケール係数"""
        return self.converter.uniform_scale
    
    @property
    def resized_image(self) -> Optional[Image.Image]:
        """リサイズ済み画像を取得"""
        return self._resized_image
    
    @property
    def original_image(self) -> Optional[Image.Image]:
        """オリジナル画像を取得"""
        return self._original_image
    
    def bbox_to_original(self, bbox: BBox) -> BBox:
        """リサイズ後座標 → オリジナル座標"""
        return self.converter.to_original(bbox)
    
    def bbox_to_resized(self, bbox: BBox) -> BBox:
        """オリジナル座標 → リサイズ後座標"""
        return self.converter.to_resized(bbox)
    
    def get_temp_path(self) -> str:
        """
        OCR用一時ファイルパスを取得（遅延作成）
        
        Returns:
            一時ファイルの絶対パス
        """
        if self._temp_path and os.path.exists(self._temp_path):
            return self._temp_path
        
        if self._resized_image is None:
            raise ValueError("No resized image available")
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            self._resized_image.save(f.name, "PNG", optimize=True)
            self._temp_path = f.name
        
        return self._temp_path
    
    def cleanup_temp(self):
        """一時ファイルを削除"""
        if self._temp_path and os.path.exists(self._temp_path):
            os.unlink(self._temp_path)
            self._temp_path = None
    
    def __del__(self):
        """デストラクタで一時ファイルをクリーンアップ"""
        self.cleanup_temp()
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式でエクスポート"""
        return {
            'segment_id': self.segment_id,
            'original_size': self.original_size,
            'resized_size': self.resized_size,
            'scale_factor': self.scale_factor,
            'is_resized': self.is_resized,
            'page_index': self.page_index,
            'source_type': self.source_type
        }


class SegmentCache:
    """
    セグメントキャッシュ（速度改善）
    
    同じ画像パスに対するリサイズ結果をキャッシュ
    """
    _cache: Dict[str, ImageSegment] = {}
    _max_size: int = 50
    
    @classmethod
    def get(cls, path: str) -> Optional[ImageSegment]:
        """キャッシュからセグメントを取得"""
        return cls._cache.get(path)
    
    @classmethod
    def put(cls, path: str, segment: ImageSegment):
        """セグメントをキャッシュに追加"""
        if len(cls._cache) >= cls._max_size:
            # LRU的に古いエントリを削除（簡易版）
            oldest_key = next(iter(cls._cache))
            del cls._cache[oldest_key]
        cls._cache[path] = segment
    
    @classmethod
    def get_or_create(
        cls, 
        path: str, 
        max_long_edge: int = 4096
    ) -> ImageSegment:
        """
        キャッシュから取得、なければ作成
        
        Args:
            path: 画像ファイルパス
            max_long_edge: 最大長辺
        
        Returns:
            ImageSegment
        """
        cached = cls.get(path)
        if cached:
            return cached
        
        segment = ImageSegment.from_path(path, max_long_edge, Path(path).stem)
        cls.put(path, segment)
        return segment
    
    @classmethod
    def clear(cls):
        """キャッシュをクリア"""
        for segment in cls._cache.values():
            segment.cleanup_temp()
        cls._cache.clear()


# 便利関数
def create_segment_from_path(
    image_path: str,
    max_long_edge: int = 4096,
    use_cache: bool = True
) -> ImageSegment:
    """
    画像パスからセグメントを作成（キャッシュ対応）
    
    Args:
        image_path: 画像ファイルパス
        max_long_edge: 最大長辺
        use_cache: キャッシュを使用するか
    
    Returns:
        ImageSegment
    """
    if use_cache:
        return SegmentCache.get_or_create(image_path, max_long_edge)
    else:
        return ImageSegment.from_path(image_path, max_long_edge)


def convert_bbox_to_original(
    bbox: Tuple[float, float, float, float],
    scale_factor: float
) -> List[int]:
    """
    リサイズ後座標をオリジナル座標に変換（互換関数）
    
    既存コードとの互換性のための関数
    """
    return [
        int(bbox[0] / scale_factor),
        int(bbox[1] / scale_factor),
        int(bbox[2] / scale_factor),
        int(bbox[3] / scale_factor)
    ]


# モジュールテスト
if __name__ == "__main__":
    # テスト用コード
    print("=== ImageSegment Module Test ===\n")
    
    # BBoxテスト
    bbox = BBox(10, 20, 100, 200)
    print(f"BBox: {bbox}")
    print(f"  Width: {bbox.width}, Height: {bbox.height}")
    print(f"  Center: {bbox.center}")
    print(f"  Tuple: {bbox.to_tuple()}")
    print()
    
    # CoordinateConverterテスト
    converter = CoordinateConverter((1000, 800), (500, 400))
    print(f"Converter: {converter}")
    
    original_bbox = BBox(100, 100, 200, 200)
    resized_bbox = converter.to_resized(original_bbox)
    restored_bbox = converter.to_original(resized_bbox)
    
    print(f"  Original: {original_bbox}")
    print(f"  Resized:  {resized_bbox}")
    print(f"  Restored: {restored_bbox}")
    print()
    
    print("✅ Module test completed")
