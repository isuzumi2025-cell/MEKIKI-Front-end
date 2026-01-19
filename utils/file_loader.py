import os
from pathlib import Path
from typing import List, Union
from PIL import Image
from pdf2image import convert_from_path

class FileLoader:
    """
    画像ファイルまたはPDFファイルを読み込み、PIL.Imageオブジェクトとして返すクラス
    """
    
    @staticmethod
    def load_file(file_path: str) -> List[Image.Image]:
        """
        ファイルパスを受け取り、画像のリストを返す
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        suffix = path.suffix.lower()
        
        if suffix == '.pdf':
            return FileLoader._load_pdf(str(path))
        elif suffix in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            return [FileLoader._load_image(str(path))]
        else:
            raise ValueError(f"サポートされていないファイル形式です: {suffix}")

    @staticmethod
    def _load_image(path: str) -> Image.Image:
        try:
            return Image.open(path).convert('RGB')
        except Exception as e:
            raise RuntimeError(f"画像の読み込みに失敗しました: {e}")

    @staticmethod
    def _load_pdf(path: str) -> List[Image.Image]:
        try:
            # DPIを400に設定して高画質で読み込む（チラシなどの細かい文字対策）
            return convert_from_path(path, dpi=400)
        except Exception as e:
            raise RuntimeError(f"PDFの変換に失敗しました: {e}")
