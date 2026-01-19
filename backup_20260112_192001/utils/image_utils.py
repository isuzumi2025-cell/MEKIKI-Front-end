"""
Image Utilities Module
画像処理ユーティリティ - リサイズ、変換、サムネイル生成
"""
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional
import io


class ImageUtils:
    """画像処理ユーティリティクラス"""
    
    @staticmethod
    def resize_image(
        image: Image.Image,
        max_width: int = 800,
        max_height: int = 600,
        maintain_aspect: bool = True
    ) -> Image.Image:
        """
        画像をリサイズ
        
        Args:
            image: PIL Imageオブジェクト
            max_width: 最大幅
            max_height: 最大高さ
            maintain_aspect: アスペクト比を維持するか
        
        Returns:
            リサイズ後の画像
        """
        if maintain_aspect:
            # アスペクト比を維持してリサイズ
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            return image
        else:
            # 強制的にリサイズ
            return image.resize((max_width, max_height), Image.Resampling.LANCZOS)
    
    @staticmethod
    def create_thumbnail(
        image: Image.Image,
        size: Tuple[int, int] = (200, 200)
    ) -> Image.Image:
        """
        サムネイルを作成
        
        Args:
            image: PIL Imageオブジェクト
            size: サムネイルサイズ (width, height)
        
        Returns:
            サムネイル画像
        """
        thumbnail = image.copy()
        thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
        return thumbnail
    
    @staticmethod
    def image_to_bytes(
        image: Image.Image,
        format: str = "PNG"
    ) -> bytes:
        """
        PIL ImageをバイトデータにImage変換
        
        Args:
            image: PIL Imageオブジェクト
            format: 画像フォーマット
        
        Returns:
            バイトデータ
        """
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()
    
    @staticmethod
    def bytes_to_image(data: bytes) -> Image.Image:
        """
        バイトデータをPIL Imageに変換
        
        Args:
            data: バイトデータ
        
        Returns:
            PIL Imageオブジェクト
        """
        return Image.open(io.BytesIO(data))
    
    @staticmethod
    def create_placeholder(
        width: int = 800,
        height: int = 600,
        message: str = "画像なし",
        bg_color: str = "#2B2B2B",
        text_color: str = "#FF4444"
    ) -> Image.Image:
        """
        プレースホルダー画像を作成
        
        Args:
            width: 幅
            height: 高さ
            message: メッセージ
            bg_color: 背景色
            text_color: テキスト色
        
        Returns:
            PIL Imageオブジェクト
        """
        # 背景画像を作成
        img = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # 枠を描画
        margin = 50
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=text_color,
            width=5
        )
        
        # テキストを描画
        text = f"⚠️ {message}"
        text_width = len(text) * 10
        text_x = (width - text_width) // 2
        text_y = height // 2
        
        draw.text((text_x, text_y), text, fill=text_color)
        
        return img
    
    @staticmethod
    def blend_images(
        image1: Image.Image,
        image2: Image.Image,
        alpha: float = 0.5
    ) -> Image.Image:
        """
        2つの画像をブレンド（オニオンスキン用）
        
        Args:
            image1: 画像1
            image2: 画像2
            alpha: ブレンド比率 (0.0-1.0)
        
        Returns:
            ブレンド後の画像
        """
        # サイズを統一
        max_width = max(image1.width, image2.width)
        max_height = max(image1.height, image2.height)
        
        img1_resized = image1.resize((max_width, max_height), Image.Resampling.LANCZOS)
        img2_resized = image2.resize((max_width, max_height), Image.Resampling.LANCZOS)
        
        # ブレンド
        return Image.blend(
            img1_resized.convert("RGBA"),
            img2_resized.convert("RGBA"),
            alpha
        )

