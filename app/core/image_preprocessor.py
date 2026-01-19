"""
画像前処理
OCR精度向上のための4倍拡大・ノイズ除去・ガンマ補正・二値化

Legacy移植元: 251220_NewOCR_B4Claude/app/core/preprocessor.py

Created: 2026-01-11
"""
import cv2
import numpy as np
from PIL import Image
from typing import Optional


class ImagePreprocessor:
    """
    OCR精度向上のための画像前処理クラス
    
    処理順序:
    1. 4倍拡大 (LANCZOS4) - 小文字対応
    2. グレースケール化
    3. ノイズ除去 (fastNlMeansDenoising)
    4. ガンマ補正 (薄い文字を濃く)
    5. 大津の二値化
    """
    
    def __init__(
        self,
        scale_factor: float = 4.0,
        denoise_strength: int = 10,
        gamma: float = 0.5,
        enable_binarize: bool = True
    ):
        """
        初期化
        
        Args:
            scale_factor: 拡大倍率（デフォルト4倍）
            denoise_strength: ノイズ除去強度
            gamma: ガンマ値（<1で暗部を持ち上げ）
            enable_binarize: 二値化を有効にするか
        """
        self.scale_factor = scale_factor
        self.denoise_strength = denoise_strength
        self.gamma = gamma
        self.enable_binarize = enable_binarize
    
    def process(self, image: Image.Image) -> Image.Image:
        """
        画像を前処理
        
        Args:
            image: 入力PIL画像
            
        Returns:
            前処理済みPIL画像
        """
        # PIL → OpenCV (numpy array) 変換
        img_np = np.array(image)
        
        # RGBならBGRに変換
        if img_np.ndim == 3:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 1. 拡大（小さい画像のみ）
        height, width = img_np.shape[:2]
        if height < 2000 or width < 2000:
            img_np = cv2.resize(
                img_np, None,
                fx=self.scale_factor,
                fy=self.scale_factor,
                interpolation=cv2.INTER_LANCZOS4
            )
        
        # 2. グレースケール化
        if img_np.ndim == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_np
        
        # 3. ノイズ除去
        denoised = cv2.fastNlMeansDenoising(
            gray, None,
            self.denoise_strength,
            7, 21
        )
        
        # 4. ガンマ補正（薄い文字を濃くする）
        look_up_table = np.array([
            ((i / 255.0) ** self.gamma) * 255
            for i in np.arange(0, 256)
        ]).astype("uint8")
        gamma_corrected = cv2.LUT(denoised, look_up_table)
        
        # 5. 二値化（オプション）
        if self.enable_binarize:
            _, binary = cv2.threshold(
                gamma_corrected, 0, 255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            result = binary
        else:
            result = gamma_corrected
        
        # OpenCV → PIL 変換
        return Image.fromarray(result)
    
    def process_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        OCR用に最適化された前処理（二値化あり）
        """
        return self.process(image)
    
    def process_for_display(self, image: Image.Image) -> Image.Image:
        """
        表示用の前処理（二値化なし）
        """
        original_binarize = self.enable_binarize
        self.enable_binarize = False
        result = self.process(image)
        self.enable_binarize = original_binarize
        return result
    
    def enhance_region(
        self,
        image: Image.Image,
        bbox: tuple,
        margin: int = 10
    ) -> Image.Image:
        """
        特定領域のみ強化処理
        
        Args:
            image: 入力画像
            bbox: (x1, y1, x2, y2) 領域
            margin: マージン
            
        Returns:
            強化された領域画像
        """
        x1, y1, x2, y2 = bbox
        
        # マージン適用
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(image.width, x2 + margin)
        y2 = min(image.height, y2 + margin)
        
        # 切り抜き
        cropped = image.crop((x1, y1, x2, y2))
        
        # 前処理
        return self.process(cropped)


# ========== Convenience Function ==========

def preprocess_image(
    image: Image.Image,
    scale: float = 4.0,
    binarize: bool = True
) -> Image.Image:
    """
    画像前処理（簡易インターフェース）
    
    Args:
        image: 入力PIL画像
        scale: 拡大倍率
        binarize: 二値化するか
        
    Returns:
        前処理済み画像
    """
    preprocessor = ImagePreprocessor(
        scale_factor=scale,
        enable_binarize=binarize
    )
    return preprocessor.process(image)


if __name__ == "__main__":
    # テスト
    from PIL import Image
    
    # テスト画像を作成
    test_img = Image.new("RGB", (200, 100), color="white")
    
    preprocessor = ImagePreprocessor()
    result = preprocessor.process(test_img)
    
    print(f"入力: {test_img.size} → 出力: {result.size}")
    print(f"拡大倍率: {preprocessor.scale_factor}")
