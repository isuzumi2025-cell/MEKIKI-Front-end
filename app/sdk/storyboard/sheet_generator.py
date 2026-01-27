"""
Sheet Generator - シート表示用データ生成
Phase 3.0 SDK
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from PIL import Image
import io


@dataclass
class SheetRow:
    """シート行データ"""
    id: int
    thumbnail: Optional[Image.Image] = None
    item_type: str = "text"  # "text" or "image"
    layer_name: str = ""
    text: str = ""
    bbox: tuple = (0, 0, 0, 0)
    page_num: int = 0
    metadata: Dict = field(default_factory=dict)


class SheetGenerator:
    """
    シート表示用データ生成クラス
    
    レイヤー結果からスプレッドシート形式のデータを生成。
    """
    
    THUMBNAIL_SIZE = (80, 60)
    
    def __init__(self, layer_result: Any = None, page_images: List[Image.Image] = None):
        """
        Args:
            layer_result: LayerSeparator.extract_layers()の結果
            page_images: PDFページ画像リスト
        """
        self.layer_result = layer_result
        self.page_images = page_images or []
    
    def set_data(self, layer_result: Any, page_images: List[Image.Image] = None):
        """データを設定"""
        self.layer_result = layer_result
        if page_images:
            self.page_images = page_images
    
    def generate_sheet_data(self) -> List[SheetRow]:
        """シートデータを生成"""
        rows = []
        row_id = 1
        
        # テキストブロックを追加
        text_rows = self._generate_text_rows(row_id)
        rows.extend(text_rows)
        row_id += len(text_rows)
        
        # 画像を追加
        image_rows = self._generate_image_rows(row_id)
        rows.extend(image_rows)
        
        return rows
    
    def _generate_text_rows(self, start_id: int) -> List[SheetRow]:
        """テキストブロックからシート行を生成"""
        rows = []
        
        if not self.layer_result:
            return rows
        
        text_layer = None
        if hasattr(self.layer_result, 'text_layer'):
            text_layer = self.layer_result.text_layer
        
        if not text_layer or not hasattr(text_layer, 'blocks'):
            return rows
        
        for i, block in enumerate(text_layer.blocks):
            # フォントサイズでレイヤー名決定
            font_size = getattr(block, 'font_size', 12.0)
            if font_size >= 18:
                layer_name = "Bold"
            elif font_size >= 12:
                layer_name = "Regular"
            else:
                layer_name = "Light"
            
            # サムネイル生成
            thumbnail = self._create_text_thumbnail(block)
            
            row = SheetRow(
                id=start_id + i,
                thumbnail=thumbnail,
                item_type="text",
                layer_name=layer_name,
                text=getattr(block, 'text', '')[:100],  # 最初の100文字
                bbox=getattr(block, 'bbox', (0, 0, 0, 0)),
                page_num=getattr(block, 'page_num', 0),
                metadata={"font_size": font_size}
            )
            rows.append(row)
        
        return rows
    
    def _generate_image_rows(self, start_id: int) -> List[SheetRow]:
        """画像からシート行を生成"""
        rows = []
        
        if not self.layer_result:
            return rows
        
        image_layer = None
        if hasattr(self.layer_result, 'image_layer'):
            image_layer = self.layer_result.image_layer
        
        if not image_layer or not hasattr(image_layer, 'images'):
            return rows
        
        for i, img_block in enumerate(image_layer.images):
            # サムネイル
            thumbnail = None
            if hasattr(img_block, 'image') and img_block.image:
                thumbnail = img_block.image.copy()
                thumbnail.thumbnail(self.THUMBNAIL_SIZE)
            
            row = SheetRow(
                id=start_id + i,
                thumbnail=thumbnail,
                item_type="image",
                layer_name=f"Image{i + 1}",
                text="",
                bbox=getattr(img_block, 'bbox', (0, 0, 0, 0)),
                page_num=getattr(img_block, 'page_num', 0),
                metadata={}
            )
            rows.append(row)
        
        return rows
    
    def _create_text_thumbnail(self, block) -> Optional[Image.Image]:
        """テキストブロックのサムネイルを作成"""
        page_num = getattr(block, 'page_num', 0)
        
        if not self.page_images or page_num >= len(self.page_images):
            return None
        
        page_img = self.page_images[page_num]
        bbox = getattr(block, 'bbox', None)
        
        if not bbox or len(bbox) < 4:
            return None
        
        try:
            # 座標を取得してクロップ
            x0, y0, x1, y1 = bbox[:4]
            cropped = page_img.crop((x0, y0, x1, y1))
            cropped.thumbnail(self.THUMBNAIL_SIZE)
            return cropped
        except:
            return None
    
    def to_csv_data(self) -> List[Dict]:
        """CSV形式のデータを生成"""
        rows = self.generate_sheet_data()
        csv_data = []
        
        for row in rows:
            csv_data.append({
                "id": row.id,
                "type": row.item_type,
                "layer": row.layer_name,
                "text": row.text,
                "x": row.bbox[0] if len(row.bbox) > 0 else 0,
                "y": row.bbox[1] if len(row.bbox) > 1 else 0,
                "width": row.bbox[2] - row.bbox[0] if len(row.bbox) > 2 else 0,
                "height": row.bbox[3] - row.bbox[1] if len(row.bbox) > 3 else 0,
                "page": row.page_num
            })
        
        return csv_data
