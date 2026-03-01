"""
カード型レイアウト境界検出器

Webページのカード型レイアウト（商品カード、機能紹介カード等）を
検出し、OCRクラスタリングがカード境界を越えてブロックをマージしないよう
制約情報を提供する。

検出手法:
  1. 均一色の矩形領域 (color)
  2. 枠線で囲まれた領域 (border)
  3. 等間隔グリッド配置 (grid)
  4. SSIM 繰り返しパターン (ssim, オプション)

安全設計:
  - detect() は try/except で完全保護。失敗時は空リストを返す
  - blocks_cross_card_boundary() / blocks_in_same_card() はスタティックで
    card_boundaries=None の場合 (False, 0.0) / None を返す
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from PIL import Image


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------

@dataclass
class CardRegion:
    """検出されたカード領域"""
    rect: Tuple[int, int, int, int]   # (x0, y0, x1, y1)
    confidence: float                  # 0.0 - 1.0
    bg_color: str = "#FFFFFF"          # 背景色 "#RRGGBB"
    has_border: bool = False
    template_id: Optional[int] = None  # 同じ ID = 同型カード
    source: str = "unknown"            # "color" | "border" | "grid" | "ssim"


@dataclass
class CardDetectionResult:
    cards: List[CardRegion] = field(default_factory=list)
    grid_cols: int = 0
    grid_rows: int = 0
    detection_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# 検出器本体
# ---------------------------------------------------------------------------

class CardBoundaryDetector:
    """
    PIL.Image からカード領域を検出する。

    使い方:
        detector = CardBoundaryDetector()
        result = detector.detect(pil_image)
        card_boundaries = result.cards
    """

    def __init__(
        self,
        min_card_area: int = 5000,
        border_threshold: int = 30,
        color_uniformity_std: float = 20.0,
        enable_ssim: bool = False,
    ):
        """
        Args:
            min_card_area: カードとして認識する最小面積 (px²)
            border_threshold: ボーダー線として認識する最小強度 (0-255)
            color_uniformity_std: 均一色判定の標準偏差閾値
            enable_ssim: SSIM 繰り返し検出を有効にする（重い処理）
        """
        self.min_card_area = min_card_area
        self.border_threshold = border_threshold
        self.color_uniformity_std = color_uniformity_std
        self.enable_ssim = enable_ssim

    # ------------------------------------------------------------------
    # パブリック API
    # ------------------------------------------------------------------

    def detect(self, image: Image.Image) -> CardDetectionResult:
        """
        PIL Image からカード領域を検出する。

        失敗しても例外を投げず空の CardDetectionResult を返す。
        """
        import time
        t0 = time.time()
        result = CardDetectionResult()
        try:
            # PIL → OpenCV
            if image.mode == "RGBA":
                image = image.convert("RGB")
            cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            candidates: List[CardRegion] = []
            candidates.extend(self._detect_color_regions(cv_img))
            candidates.extend(self._detect_bordered_regions(cv_img))

            if candidates:
                is_grid, cols, rows = self._detect_grid_pattern(candidates)
                result.grid_cols = cols
                result.grid_rows = rows

            if self.enable_ssim:
                candidates.extend(self._detect_ssim_patterns(cv_img))

            merged = self._merge_detections(candidates)
            merged = self._assign_template_ids(merged, cv_img)

            result.cards = merged
            result.detection_time_ms = (time.time() - t0) * 1000
        except Exception as e:
            print(f"[CardBoundaryDetector] detection failed: {e}")
        return result

    # ------------------------------------------------------------------
    # 静的ユーティリティ（engine_cloud.py から呼ばれる）
    # ------------------------------------------------------------------

    @staticmethod
    def blocks_cross_card_boundary(
        rect1,
        rect2,
        cards: List[CardRegion],
    ) -> Tuple[bool, float]:
        """
        rect1 と rect2 が異なるカードに属する場合 (True, confidence) を返す。
        同一カード内 or カード検出なし → (False, 0.0)

        Args:
            rect1, rect2: [x0, y0, x1, y1]
            cards: CardBoundaryDetector.detect() の結果リスト
        """
        if not cards:
            return (False, 0.0)

        c1 = CardBoundaryDetector._find_card(rect1, cards)
        c2 = CardBoundaryDetector._find_card(rect2, cards)

        if c1 is None or c2 is None:
            return (False, 0.0)
        if c1 is c2:
            return (False, 0.0)

        # 異なるカードに属する → 交差している
        conf = min(c1.confidence, c2.confidence)
        return (True, conf)

    @staticmethod
    def blocks_in_same_card(
        rect1,
        rect2,
        cards: List[CardRegion],
    ) -> Optional[CardRegion]:
        """
        rect1 と rect2 が同一カード内に収まる場合、そのカードを返す。
        そうでなければ None を返す。
        """
        if not cards:
            return None

        c1 = CardBoundaryDetector._find_card(rect1, cards)
        c2 = CardBoundaryDetector._find_card(rect2, cards)

        if c1 is not None and c1 is c2:
            return c1
        return None

    # ------------------------------------------------------------------
    # プライベート: 検出ロジック
    # ------------------------------------------------------------------

    def _detect_color_regions(self, cv_img: np.ndarray) -> List[CardRegion]:
        """
        均一な背景色を持つ矩形領域をカードとして検出する。

        アルゴリズム:
          1. ガウシアンブラーでノイズ除去
          2. 適応二値化で均一色領域のマスク生成
          3. 輪郭を矩形 bbox に変換
          4. 均一性（標準偏差）で絞り込み
        """
        cards: List[CardRegion] = []

        # ---- 前処理 ----
        blurred = cv2.GaussianBlur(cv_img, (5, 5), 0)
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)

        # 均一な領域 = 局所的に変化が少ない → ラプラシアンで変化量を測定
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_abs = np.abs(lap).astype(np.uint8)

        # 変化が少ない領域(< 10)を白に
        _, uniform_mask = cv2.threshold(lap_abs, 10, 255, cv2.THRESH_BINARY_INV)

        # モルフォロジーで穴埋め
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        closed = cv2.morphologyEx(uniform_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_img, w_img = cv_img.shape[:2]

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_card_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # 画像全体を覆う領域は除外
            if w > w_img * 0.9 and h > h_img * 0.9:
                continue

            # 均一性確認：領域内の標準偏差
            roi = cv_img[y:y+h, x:x+w]
            std = float(roi.std())
            if std > self.color_uniformity_std:
                continue

            # 平均色を取得
            avg_bgr = roi.mean(axis=(0, 1))
            b, g, r = int(avg_bgr[0]), int(avg_bgr[1]), int(avg_bgr[2])
            hex_color = f"#{r:02X}{g:02X}{b:02X}"

            # 信頼度：均一性が高いほど高い
            confidence = max(0.3, 1.0 - std / 50.0)

            cards.append(CardRegion(
                rect=(x, y, x + w, y + h),
                confidence=confidence,
                bg_color=hex_color,
                source="color",
            ))

        return cards

    def _detect_bordered_regions(self, cv_img: np.ndarray) -> List[CardRegion]:
        """
        枠線で囲まれた矩形領域を検出する。

        アルゴリズム:
          1. グレースケール → Canny エッジ検出
          2. 輪郭を矩形に変換
          3. アスペクト比・面積でカード候補を絞り込み
          4. 矩形充填率で矩形らしさを確認
        """
        cards: List[CardRegion] = []

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        # エッジを太くしてつなぐ
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_img, w_img = cv_img.shape[:2]

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_card_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # 画像全体を覆う領域は除外
            if w > w_img * 0.9 and h > h_img * 0.9:
                continue

            # アスペクト比チェック（カードらしい形：0.3 〜 3.0）
            aspect = w / h if h > 0 else 0
            if not (0.3 <= aspect <= 3.0):
                continue

            # 矩形充填率（輪郭面積 / bbox 面積）
            fill_ratio = area / (w * h) if w * h > 0 else 0
            if fill_ratio < 0.5:
                continue

            # 領域内の平均色
            roi = cv_img[y:y+h, x:x+w]
            avg_bgr = roi.mean(axis=(0, 1))
            b, g, r = int(avg_bgr[0]), int(avg_bgr[1]), int(avg_bgr[2])
            hex_color = f"#{r:02X}{g:02X}{b:02X}"

            confidence = min(0.9, fill_ratio)

            cards.append(CardRegion(
                rect=(x, y, x + w, y + h),
                confidence=confidence,
                bg_color=hex_color,
                has_border=True,
                source="border",
            ))

        return cards

    def _detect_grid_pattern(
        self, candidates: List[CardRegion]
    ) -> Tuple[bool, int, int]:
        """
        候補カードが等間隔グリッド配置かどうかを判定する。

        Returns:
            (is_grid, cols, rows)
        """
        if len(candidates) < 4:
            return (False, 0, 0)

        # 代表的なカードの中心座標
        centers = [(
            (c.rect[0] + c.rect[2]) / 2,
            (c.rect[1] + c.rect[3]) / 2,
        ) for c in candidates]

        # X 方向のクラスタリング（列数推定）
        xs = sorted(set(round(cx / 50) * 50 for cx, _ in centers))
        ys = sorted(set(round(cy / 50) * 50 for _, cy in centers))

        cols = len(xs)
        rows = len(ys)

        # グリッドらしさ判定：列×行がカード数に近い
        expected = cols * rows
        actual = len(candidates)
        is_grid = actual >= expected * 0.6 and cols >= 2 and rows >= 2

        return (is_grid, cols if is_grid else 0, rows if is_grid else 0)

    def _detect_ssim_patterns(self, cv_img: np.ndarray) -> List[CardRegion]:
        """
        SSIM ベースの繰り返しパターン検出（オプション、重い処理）。
        enable_ssim=True の場合のみ呼ばれる。
        """
        # 簡易実装：同一サイズの矩形が複数ある場合にカード判定
        # 本格実装は spatial_cluster_analyzer.py の SpatialClusterAnalyzer を利用
        return []

    def _merge_detections(
        self, candidates: List[CardRegion]
    ) -> List[CardRegion]:
        """
        NMS (Non-Maximum Suppression) で重複カード候補をマージする。
        IoU > 0.5 の場合、信頼度の高い方を残す。
        """
        if not candidates:
            return []

        # 信頼度降順でソート
        sorted_cands = sorted(candidates, key=lambda c: c.confidence, reverse=True)
        merged: List[CardRegion] = []

        for cand in sorted_cands:
            suppressed = False
            for kept in merged:
                iou = self._iou(cand.rect, kept.rect)
                if iou > 0.5:
                    suppressed = True
                    break
            if not suppressed:
                merged.append(cand)

        return merged

    def _assign_template_ids(
        self, cards: List[CardRegion], cv_img: np.ndarray
    ) -> List[CardRegion]:
        """
        アスペクト比とサイズが近いカードを同一テンプレートとして ID を付与する。
        同じ template_id = 同型のカード（繰り返しパターン）
        """
        if not cards:
            return cards

        def card_signature(c: CardRegion) -> Tuple[float, float]:
            w = c.rect[2] - c.rect[0]
            h = c.rect[3] - c.rect[1]
            aspect = round((w / h if h > 0 else 1.0) * 4) / 4  # 0.25刻み
            size_bucket = round(max(w, h) / 50) * 50             # 50px刻み
            return (aspect, size_bucket)

        sig_to_id: Dict[Tuple, int] = {}
        next_id = 0

        for card in cards:
            sig = card_signature(card)
            if sig not in sig_to_id:
                sig_to_id[sig] = next_id
                next_id += 1
            card.template_id = sig_to_id[sig]

        return cards

    # ------------------------------------------------------------------
    # プライベート: ユーティリティ
    # ------------------------------------------------------------------

    @staticmethod
    def _iou(rect1: Tuple, rect2: Tuple) -> float:
        """IoU (Intersection over Union) 計算"""
        x0 = max(rect1[0], rect2[0])
        y0 = max(rect1[1], rect2[1])
        x1 = min(rect1[2], rect2[2])
        y1 = min(rect1[3], rect2[3])

        inter_w = max(0, x1 - x0)
        inter_h = max(0, y1 - y0)
        inter_area = inter_w * inter_h

        area1 = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1])
        area2 = (rect2[2] - rect2[0]) * (rect2[3] - rect2[1])
        union_area = area1 + area2 - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    @staticmethod
    def _find_card(
        rect, cards: List[CardRegion], overlap_thresh: float = 0.3
    ) -> Optional[CardRegion]:
        """
        rect の重心がカード内に入っているか、もしくは一定以上の
        オーバーラップがある最初のカードを返す。
        """
        x0, y0, x1, y1 = [int(v) for v in rect]
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2

        # まず重心でチェック（高速パス）
        for card in cards:
            cx0, cy0, cx1, cy1 = card.rect
            if cx0 <= cx <= cx1 and cy0 <= cy <= cy1:
                return card

        # オーバーラップ率でチェック（フォールバック）
        best: Optional[CardRegion] = None
        best_overlap = overlap_thresh

        rect_area = max(1, (x1 - x0) * (y1 - y0))
        for card in cards:
            ix0 = max(x0, card.rect[0])
            iy0 = max(y0, card.rect[1])
            ix1 = min(x1, card.rect[2])
            iy1 = min(y1, card.rect[3])
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            overlap = inter / rect_area
            if overlap > best_overlap:
                best_overlap = overlap
                best = card

        return best
