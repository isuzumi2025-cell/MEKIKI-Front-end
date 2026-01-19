import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Tuple

class VisualPropagator:
    """
    Visual Anchor Engine (VAE)
    OpenCVを使用した画像ベースのテンプレートマッチングエンジン。
    OCRでは認識できないアイコンや、レイアウト上の「画像」をアンカーとして利用する。
    """

    def __init__(self):
        pass

    def find_anchors(self, 
                     template_img: Image.Image, 
                     target_img: Image.Image, 
                     threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        テンプレート画像をターゲット画像内から探索する
        
        Args:
            template_img: テンプレート領域の画像 (PIL)
            target_img: 探索対象のページ全体画像 (PIL)
            threshold: 一致率閾値 (0.0 - 1.0)
            
        Returns:
            List[Dict]: 検出された領域リスト
        """
        # PIL -> OpenCV (BGR)
        tmpl_np = np.array(template_img)
        targ_np = np.array(target_img)
        
        # RGB to BGR conversion if needed (OpenCV uses BGR)
        if tmpl_np.shape[-1] == 3:
            tmpl_bgr = cv2.cvtColor(tmpl_np, cv2.COLOR_RGB2BGR)
        else:
            tmpl_bgr = cv2.cvtColor(tmpl_np, cv2.COLOR_RGBA2BGR)
            
        if targ_np.shape[-1] == 3:
            targ_bgr = cv2.cvtColor(targ_np, cv2.COLOR_RGB2BGR)
        else:
            targ_bgr = cv2.cvtColor(targ_np, cv2.COLOR_RGBA2BGR)

        # グレースケール化（ロバスト性向上）
        tmpl_gray = cv2.cvtColor(tmpl_bgr, cv2.COLOR_BGR2GRAY)
        targ_gray = cv2.cvtColor(targ_bgr, cv2.COLOR_BGR2GRAY)
        
        # テンプレートマッチング実行
        # TM_CCOEFF_NORMED: 正規化相関係数（明るさ変動に強い）
        res = cv2.matchTemplate(targ_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        
        # 閾値以上の位置を検出
        loc = np.where(res >= threshold)
        
        h, w = tmpl_gray.shape
        anchors = []
        
        # 重複除去用のマスク
        mask = np.zeros(targ_gray.shape, dtype=np.uint8)
        
        # locは (y_array, x_array)
        # スコア順に処理したいが、np.whereの順序はY順
        # 検出点をリスト化
        points = []
        for pt in zip(*loc[::-1]): # (x, y)
            score = res[pt[1], pt[0]]
            points.append((pt, score))
            
        # スコアが高い順に採用 (NMS)
        points.sort(key=lambda x: x[1], reverse=True)
        
        for pt, score in points:
            x, y = pt
            # マスクチェック (既に採用された領域と重なっているか)
            if mask[y + h//2, x + w//2] == 0:
                # 領域採用
                anchors.append({
                    "rect": [int(x), int(y), int(x + w), int(y + h)],
                    "score": float(score),
                    "type": "visual_anchor"
                })
                
                # マスクを塗る (近傍を無効化)
                cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
                
        print(f"[VisualPropagator] Found {len(anchors)} visual anchors (threshold={threshold})")
        return anchors
