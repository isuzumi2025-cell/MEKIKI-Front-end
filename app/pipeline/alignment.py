"""
Visual Alignment Module
ORB特徴量 + Homography変換による画像位置合わせ

Created: 2026-01-11
"""
import numpy as np
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class AlignmentResult:
    """アライメント結果"""
    success: bool = False
    homography_matrix: Optional[np.ndarray] = None
    aligned_image: Optional[Image.Image] = None
    match_count: int = 0
    inlier_count: int = 0
    confidence: float = 0.0
    error: Optional[str] = None


class VisualAligner:
    """
    視覚的位置合わせ
    ORB特徴点 + RANSAC Homography
    """
    
    def __init__(
        self,
        n_features: int = 5000,
        scale_factor: float = 1.2,
        n_levels: int = 8,
        match_ratio: float = 0.75,
        min_matches: int = 10
    ):
        """
        初期化
        
        Args:
            n_features: 抽出する特徴点数
            scale_factor: ORBのスケールファクター
            n_levels: ORBのピラミッドレベル
            match_ratio: Lowe's ratio test の閾値
            min_matches: 最小マッチ数
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV (cv2) is not installed")
        
        self.n_features = n_features
        self.scale_factor = scale_factor
        self.n_levels = n_levels
        self.match_ratio = match_ratio
        self.min_matches = min_matches
        
        # ORB検出器
        self.orb = cv2.ORB_create(
            nfeatures=n_features,
            scaleFactor=scale_factor,
            nlevels=n_levels
        )
        
        # BFマッチャー
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    
    def align(
        self,
        reference_image: Image.Image,
        target_image: Image.Image
    ) -> AlignmentResult:
        """
        ターゲット画像を参照画像に位置合わせ
        
        Args:
            reference_image: 参照画像（基準）
            target_image: ターゲット画像（変換対象）
            
        Returns:
            AlignmentResult
        """
        result = AlignmentResult()
        
        try:
            # PIL → OpenCV
            ref_cv = self._pil_to_cv(reference_image)
            tgt_cv = self._pil_to_cv(target_image)
            
            # グレースケール変換
            ref_gray = cv2.cvtColor(ref_cv, cv2.COLOR_BGR2GRAY)
            tgt_gray = cv2.cvtColor(tgt_cv, cv2.COLOR_BGR2GRAY)
            
            # 特徴点検出
            kp1, desc1 = self.orb.detectAndCompute(ref_gray, None)
            kp2, desc2 = self.orb.detectAndCompute(tgt_gray, None)
            
            if desc1 is None or desc2 is None:
                result.error = "特徴点が検出できませんでした"
                return result
            
            # マッチング
            matches = self.bf.knnMatch(desc1, desc2, k=2)
            
            # Lowe's ratio test
            good_matches = []
            for m_n in matches:
                if len(m_n) == 2:
                    m, n = m_n
                    if m.distance < self.match_ratio * n.distance:
                        good_matches.append(m)
            
            result.match_count = len(good_matches)
            
            if len(good_matches) < self.min_matches:
                result.error = f"マッチ数不足 ({len(good_matches)} < {self.min_matches})"
                return result
            
            # Homography計算
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
            
            if H is None:
                result.error = "Homography計算に失敗"
                return result
            
            result.homography_matrix = H
            result.inlier_count = np.sum(mask) if mask is not None else 0
            result.confidence = result.inlier_count / len(good_matches) if good_matches else 0.0
            
            # 画像変換
            h, w = ref_cv.shape[:2]
            aligned_cv = cv2.warpPerspective(tgt_cv, H, (w, h))
            
            # OpenCV → PIL
            result.aligned_image = self._cv_to_pil(aligned_cv)
            result.success = True
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def create_overlay(
        self,
        image1: Image.Image,
        image2: Image.Image,
        alpha: float = 0.5,
        align_first: bool = True
    ) -> Optional[Image.Image]:
        """
        2つの画像を重ね合わせ
        
        Args:
            image1: 参照画像
            image2: ターゲット画像
            alpha: ブレンド率
            align_first: 事前にアライメントするか
            
        Returns:
            オーバーレイ画像
        """
        if align_first:
            alignment = self.align(image1, image2)
            if alignment.success:
                image2 = alignment.aligned_image
            else:
                print(f"[VisualAligner] Alignment failed: {alignment.error}")
        
        # サイズを合わせる
        w1, h1 = image1.size
        w2, h2 = image2.size
        
        target_w = max(w1, w2)
        target_h = max(h1, h2)
        
        # リサイズ
        if (w1, h1) != (target_w, target_h):
            image1 = image1.resize((target_w, target_h), Image.LANCZOS)
        if (w2, h2) != (target_w, target_h):
            image2 = image2.resize((target_w, target_h), Image.LANCZOS)
        
        # ブレンド
        return Image.blend(image1.convert("RGBA"), image2.convert("RGBA"), alpha)
    
    def create_diff_image(
        self,
        image1: Image.Image,
        image2: Image.Image,
        align_first: bool = True,
        threshold: int = 30
    ) -> Optional[Image.Image]:
        """
        差分画像を生成
        
        Args:
            image1: 参照画像
            image2: ターゲット画像
            align_first: 事前にアライメントするか
            threshold: 差分閾値
            
        Returns:
            差分画像
        """
        if align_first:
            alignment = self.align(image1, image2)
            if alignment.success:
                image2 = alignment.aligned_image
        
        # サイズを合わせる
        w1, h1 = image1.size
        w2, h2 = image2.size
        target_size = (max(w1, w2), max(h1, h2))
        
        if image1.size != target_size:
            image1 = image1.resize(target_size, Image.LANCZOS)
        if image2.size != target_size:
            image2 = image2.resize(target_size, Image.LANCZOS)
        
        # OpenCV形式で差分計算
        cv1 = self._pil_to_cv(image1)
        cv2_img = self._pil_to_cv(image2)
        
        # グレースケールで差分
        gray1 = cv2.cvtColor(cv1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
        
        diff = cv2.absdiff(gray1, gray2)
        
        # 閾値処理
        _, diff_binary = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        
        # 差分領域をハイライト
        result = cv1.copy()
        result[diff_binary > 0] = [0, 0, 255]  # 赤でハイライト
        
        return self._cv_to_pil(result)
    
    def _pil_to_cv(self, pil_image: Image.Image) -> np.ndarray:
        """PIL → OpenCV"""
        return cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
    
    def _cv_to_pil(self, cv_image: np.ndarray) -> Image.Image:
        """OpenCV → PIL"""
        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))


# ========== Convenience Functions ==========

def align_images(
    reference: Image.Image,
    target: Image.Image
) -> AlignmentResult:
    """
    画像アライメント（簡易インターフェース）
    """
    aligner = VisualAligner()
    return aligner.align(reference, target)


def create_overlay_image(
    image1: Image.Image,
    image2: Image.Image,
    alpha: float = 0.5,
    align: bool = True
) -> Optional[Image.Image]:
    """
    オーバーレイ画像作成（簡易インターフェース）
    """
    aligner = VisualAligner()
    return aligner.create_overlay(image1, image2, alpha, align)


def create_diff_highlight(
    image1: Image.Image,
    image2: Image.Image,
    align: bool = True
) -> Optional[Image.Image]:
    """
    差分ハイライト画像作成（簡易インターフェース）
    """
    aligner = VisualAligner()
    return aligner.create_diff_image(image1, image2, align)


if __name__ == "__main__":
    # テスト
    from PIL import Image
    
    # テスト画像作成
    img1 = Image.new("RGB", (400, 300), color="white")
    img2 = Image.new("RGB", (400, 300), color="lightgray")
    
    aligner = VisualAligner()
    result = aligner.align(img1, img2)
    
    print(f"Success: {result.success}")
    print(f"Matches: {result.match_count}")
    print(f"Inliers: {result.inlier_count}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Error: {result.error}")
