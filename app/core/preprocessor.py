import cv2
import numpy as np
from PIL import Image

class ImagePreprocessor:
    """
    OCR精度向上のための画像前処理クラス（4倍拡大・高精度版）
    """

    @staticmethod
    def process(image: Image.Image) -> Image.Image:
        # PIL -> OpenCV (numpy array) 変換
        img_np = np.array(image)
        
        # RGBならBGRに変換
        if img_np.ndim == 3:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # 1. 4倍に拡大（Tesseractは文字高さ30px以上を好むため、思い切って大きくします）
        # INTER_LANCZOS4 は CUBIC よりも滑らかに拡大できるアルゴリズムです
        height, width = img_np.shape[:2]
        if height < 2000 or width < 2000: 
            img_np = cv2.resize(img_np, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)

        # 2. グレースケール化
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

        # 3. ノイズ除去（拡大した分、ノイズ除去も少し強めに）
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # 4. ガンマ補正（薄い文字を濃くする処理）
        # これを入れると、薄いグレーの文字などが認識されやすくなります
        gamma = 0.5  # 1.0以下で暗部を持ち上げる
        look_up_table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        gamma_corrected = cv2.LUT(denoised, look_up_table)

        # 5. 二値化（大津の二値化）
        _, binary = cv2.threshold(gamma_corrected, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # OpenCV -> PIL 変換
        return Image.fromarray(binary)
