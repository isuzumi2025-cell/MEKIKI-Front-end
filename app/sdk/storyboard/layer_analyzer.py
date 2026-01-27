"""
Layer Analyzer - フォントウェイト別レイヤー分析
Phase 3.0 SDK
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class LayerStats:
    """レイヤー統計情報"""
    text_layers: Dict[str, int]  # フォントウェイト別カウント
    image_layers: int
    total_text_blocks: int
    total_images: int


class LayerAnalyzer:
    """
    レイヤー分析クラス
    
    フォントウェイト、サイズ別にテキストブロックを分類し、
    レイヤー統計を生成する。
    """
    
    # フォントウェイト分類
    WEIGHT_CATEGORIES = {
        "Bold": [700, 800, 900],
        "Regular": [400, 500, 600],
        "Light": [100, 200, 300]
    }
    
    def __init__(self, layer_result: Any = None):
        """
        Args:
            layer_result: LayerSeparator.extract_layers()の結果
        """
        self.layer_result = layer_result
        self._stats: Optional[LayerStats] = None
    
    def set_layer_result(self, layer_result: Any):
        """レイヤー結果を設定"""
        self.layer_result = layer_result
        self._stats = None  # キャッシュクリア
    
    def get_layer_stats(self) -> LayerStats:
        """レイヤー統計を取得"""
        if self._stats:
            return self._stats
        
        if not self.layer_result:
            return LayerStats(
                text_layers={},
                image_layers=0,
                total_text_blocks=0,
                total_images=0
            )
        
        # テキストブロック分析
        text_layers = self._analyze_text_layers()
        
        # 画像数
        image_count = 0
        if hasattr(self.layer_result, 'image_layer') and self.layer_result.image_layer:
            if hasattr(self.layer_result.image_layer, 'images'):
                image_count = len(self.layer_result.image_layer.images)
        
        # 統計生成
        self._stats = LayerStats(
            text_layers=text_layers,
            image_layers=image_count,
            total_text_blocks=sum(text_layers.values()),
            total_images=image_count
        )
        
        return self._stats
    
    def _analyze_text_layers(self) -> Dict[str, int]:
        """テキストブロックをフォントウェイト別に分類"""
        layers = {"Bold": 0, "Regular": 0, "Light": 0}
        
        if not self.layer_result:
            return layers
        
        text_layer = None
        if hasattr(self.layer_result, 'text_layer'):
            text_layer = self.layer_result.text_layer
        
        if not text_layer or not hasattr(text_layer, 'blocks'):
            return layers
        
        for block in text_layer.blocks:
            # フォントサイズでウェイトを推定
            font_size = getattr(block, 'font_size', 12.0)
            
            if font_size >= 18:
                layers["Bold"] += 1
            elif font_size >= 12:
                layers["Regular"] += 1
            else:
                layers["Light"] += 1
        
        return layers
    
    def get_text_blocks(self) -> List[Any]:
        """テキストブロック一覧を取得"""
        if not self.layer_result:
            return []
        
        if hasattr(self.layer_result, 'text_layer') and self.layer_result.text_layer:
            if hasattr(self.layer_result.text_layer, 'blocks'):
                return self.layer_result.text_layer.blocks
        
        return []
    
    def get_images(self) -> List[Any]:
        """画像一覧を取得"""
        if not self.layer_result:
            return []
        
        if hasattr(self.layer_result, 'image_layer') and self.layer_result.image_layer:
            if hasattr(self.layer_result.image_layer, 'images'):
                return self.layer_result.image_layer.images
        
        return []
