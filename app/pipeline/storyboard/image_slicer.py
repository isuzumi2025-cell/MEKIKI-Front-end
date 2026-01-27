"""
ImageSlicer - 画像をパーツに分割

Phase 2.5: コンテ素材抽出ツール用の画像パーツ分割器
- Gemini Visionによる物体検出
- OpenCV輪郭抽出（オプション）
- アニメーション用差分抽出
"""
import io
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from PIL import Image

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


@dataclass
class ImagePart:
    """画像パーツ"""
    id: str
    image: Image.Image
    bbox: Tuple[int, int, int, int]  # (x0, y0, x1, y1)
    label: str = "unknown"
    confidence: float = 0.0
    layer_order: int = 0  # アニメーション用のレイヤー順序
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImageSlicer:
    """
    画像を個別パーツに分割するエンジン
    
    機能:
    - Gemini Visionによる物体検出
    - OpenCV輪郭抽出（高精度モード）
    - 手動領域指定
    - アニメーション用差分抽出
    """
    
    def __init__(
        self, 
        use_opencv: bool = False,
        min_area: int = 100,
        gemini_model: str = "gemini-2.0-flash"
    ):
        """
        Args:
            use_opencv: OpenCV輪郭抽出を使用するか
            min_area: 最小パーツ面積（ピクセル^2）
            gemini_model: 使用するGeminiモデル
        """
        self.use_opencv = use_opencv and OPENCV_AVAILABLE
        self.min_area = min_area
        self.gemini_model = gemini_model
        self._llm_client = None
    
    def slice_image(
        self, 
        image: Image.Image, 
        mode: str = "auto"
    ) -> List[ImagePart]:
        """
        画像をパーツに分割
        
        Args:
            image: 分割対象画像
            mode: 分割モード
                - "auto": 自動検出（Gemini優先、フォールバックでOpenCV）
                - "gemini": Gemini Visionのみ使用
                - "opencv": OpenCV輪郭抽出のみ使用
                - "grid": グリッド分割
                
        Returns:
            List[ImagePart]: 分割された画像パーツ
        """
        if mode == "auto":
            # まずGeminiを試す
            parts = self._slice_with_gemini(image)
            if parts:
                return parts
            # フォールバックとしてOpenCV
            if self.use_opencv:
                return self._slice_with_opencv(image)
            return self._slice_grid(image)
        
        elif mode == "gemini":
            return self._slice_with_gemini(image)
        
        elif mode == "opencv":
            if not self.use_opencv:
                print("⚠️ OpenCV not available. Falling back to grid.")
                return self._slice_grid(image)
            return self._slice_with_opencv(image)
        
        elif mode == "grid":
            return self._slice_grid(image)
        
        else:
            print(f"⚠️ Unknown mode: {mode}. Using auto.")
            return self.slice_image(image, "auto")
    
    def _slice_with_gemini(self, image: Image.Image) -> List[ImagePart]:
        """Gemini Visionで物体検出してスライス"""
        try:
            from app.core.llm_client import LLMClient
            
            if self._llm_client is None:
                self._llm_client = LLMClient(model_name=self.gemini_model)
            
            if not self._llm_client.model:
                return []
            
            prompt = """
            Analyze this image and identify all distinct visual elements/objects.
            Return a JSON array where each object has:
            - "label": descriptive name (e.g., "person", "logo", "text_block", "background")
            - "bbox": [x_min, y_min, x_max, y_max] as percentages (0-100)
            - "layer_order": integer for animation layering (0=background, higher=foreground)
            
            Example response:
            [
                {"label": "background", "bbox": [0, 0, 100, 100], "layer_order": 0},
                {"label": "person", "bbox": [20, 30, 60, 90], "layer_order": 2},
                {"label": "logo", "bbox": [80, 5, 95, 15], "layer_order": 3}
            ]
            
            Return ONLY the JSON array, no other text.
            """
            
            response = self._llm_client.generate_content(prompt, images=[image])
            
            if not response:
                return []
            
            # JSON解析
            import json
            import re
            
            # Markdownコードブロック除去
            cleaned = re.sub(r'```json\s*', '', response)
            cleaned = re.sub(r'```\s*$', '', cleaned).strip()
            
            parts_data = json.loads(cleaned)
            
            width, height = image.size
            parts = []
            
            for i, part_info in enumerate(parts_data):
                bbox_pct = part_info.get("bbox", [0, 0, 100, 100])
                
                # パーセンテージからピクセルに変換
                x0 = int(bbox_pct[0] * width / 100)
                y0 = int(bbox_pct[1] * height / 100)
                x1 = int(bbox_pct[2] * width / 100)
                y1 = int(bbox_pct[3] * height / 100)
                
                # 領域チェック
                if x1 <= x0 or y1 <= y0:
                    continue
                if (x1 - x0) * (y1 - y0) < self.min_area:
                    continue
                
                # 画像を切り出し
                cropped = image.crop((x0, y0, x1, y1))
                
                parts.append(ImagePart(
                    id=f"part_{i:03d}",
                    image=cropped,
                    bbox=(x0, y0, x1, y1),
                    label=part_info.get("label", "unknown"),
                    confidence=0.9,  # Gemini検出は高信頼
                    layer_order=part_info.get("layer_order", i)
                ))
            
            return parts
            
        except Exception as e:
            print(f"⚠️ Gemini slicing failed: {e}")
            return []
    
    def _slice_with_opencv(self, image: Image.Image) -> List[ImagePart]:
        """OpenCV輪郭抽出でスライス"""
        if not OPENCV_AVAILABLE:
            return []
        
        try:
            # PIL → OpenCV
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # エッジ検出
            edges = cv2.Canny(gray, 50, 150)
            
            # 膨張処理で輪郭を繋げる
            kernel = np.ones((3, 3), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=2)
            
            # 輪郭抽出
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            parts = []
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if area < self.min_area:
                    continue
                
                x, y, w, h = cv2.boundingRect(contour)
                
                # 画像を切り出し
                cropped_cv = cv_image[y:y+h, x:x+w]
                cropped_pil = Image.fromarray(cv2.cvtColor(cropped_cv, cv2.COLOR_BGR2RGB))
                
                parts.append(ImagePart(
                    id=f"part_{i:03d}",
                    image=cropped_pil,
                    bbox=(x, y, x + w, y + h),
                    label="detected_region",
                    confidence=0.7,
                    layer_order=i
                ))
            
            return parts
            
        except Exception as e:
            print(f"⚠️ OpenCV slicing failed: {e}")
            return []
    
    def _slice_grid(
        self, 
        image: Image.Image, 
        rows: int = 2, 
        cols: int = 2
    ) -> List[ImagePart]:
        """グリッド分割（フォールバック）"""
        width, height = image.size
        cell_w = width // cols
        cell_h = height // rows
        
        parts = []
        
        for row in range(rows):
            for col in range(cols):
                x0 = col * cell_w
                y0 = row * cell_h
                x1 = x0 + cell_w if col < cols - 1 else width
                y1 = y0 + cell_h if row < rows - 1 else height
                
                cropped = image.crop((x0, y0, x1, y1))
                
                parts.append(ImagePart(
                    id=f"grid_{row}_{col}",
                    image=cropped,
                    bbox=(x0, y0, x1, y1),
                    label=f"cell_{row}x{col}",
                    confidence=1.0,
                    layer_order=row * cols + col
                ))
        
        return parts
    
    def extract_foreground(
        self, 
        image: Image.Image
    ) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
        """
        前景と背景を分離（アニメーション用）
        
        Returns:
            Tuple of (foreground with transparency, background)
        """
        if not OPENCV_AVAILABLE:
            return None, None
        
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # GrabCutによる前景抽出
            mask = np.zeros(cv_image.shape[:2], np.uint8)
            rect = (10, 10, cv_image.shape[1] - 20, cv_image.shape[0] - 20)
            
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)
            
            cv2.grabCut(cv_image, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
            
            # マスク適用
            mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
            foreground = cv_image * mask2[:, :, np.newaxis]
            
            # 背景抽出
            background = cv_image * (1 - mask2[:, :, np.newaxis])
            
            # PIL変換
            fg_pil = Image.fromarray(cv2.cvtColor(foreground, cv2.COLOR_BGR2RGB))
            bg_pil = Image.fromarray(cv2.cvtColor(background, cv2.COLOR_BGR2RGB))
            
            return fg_pil, bg_pil
            
        except Exception as e:
            print(f"⚠️ Foreground extraction failed: {e}")
            return None, None
