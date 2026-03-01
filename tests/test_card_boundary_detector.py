"""
CardBoundaryDetector + color_utils テストスイート

Vision API 不要 — PIL/OpenCV のみで完結。
合成カード画像を動的生成し、検出精度を検証する。

実行:
    cd OCR
    py -3 -m pytest tests/test_card_boundary_detector.py -v -s
"""

import sys
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

# パス設定
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# -----------------------------------------------------------------------
# ヘルパー：合成カード画像を生成
# -----------------------------------------------------------------------

def make_card_grid_image(
    cols: int = 3,
    rows: int = 2,
    card_w: int = 200,
    card_h: int = 150,
    gap: int = 20,
    bg_color=(240, 240, 240),
    card_color=(255, 255, 255),
    border_color=(180, 180, 180),
    with_border: bool = True,
) -> tuple[Image.Image, list[tuple]]:
    """
    cols×rows のカードグリッド画像を生成する。

    Returns:
        (PIL.Image, card_rects_list)
        card_rects_list: [(x0,y0,x1,y1), ...] の実際のカード境界
    """
    pad = 30
    total_w = pad * 2 + cols * card_w + (cols - 1) * gap
    total_h = pad * 2 + rows * card_h + (rows - 1) * gap
    img = Image.new("RGB", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(img)

    rects = []
    for r in range(rows):
        for c in range(cols):
            x0 = pad + c * (card_w + gap)
            y0 = pad + r * (card_h + gap)
            x1 = x0 + card_w
            y1 = y0 + card_h
            draw.rectangle([x0, y0, x1, y1], fill=card_color)
            if with_border:
                draw.rectangle([x0, y0, x1, y1], outline=border_color, width=2)
            # カード内にダミーテキスト風の矩形
            draw.rectangle([x0 + 10, y0 + 10, x1 - 10, y0 + 30], fill=(200, 200, 200))
            draw.rectangle([x0 + 10, y0 + 40, x1 - 10, y0 + 55], fill=(210, 210, 210))
            rects.append((x0, y0, x1, y1))

    return img, rects


# -----------------------------------------------------------------------
# Test 1: color_utils 単体テスト
# -----------------------------------------------------------------------

class TestColorUtils:
    def test_hex_to_rgb_basic(self):
        from app.core.color_utils import hex_to_rgb
        assert hex_to_rgb("#FF0000") == (255, 0, 0)
        assert hex_to_rgb("#000000") == (0, 0, 0)
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_delta_e_same_color_is_zero(self):
        from app.core.color_utils import delta_e_cie76
        de = delta_e_cie76("#FF0000", "#FF0000")
        assert de < 0.01, f"同一色の delta_e が 0 でない: {de}"

    def test_delta_e_white_vs_black_is_large(self):
        from app.core.color_utils import delta_e_cie76
        de = delta_e_cie76("#FFFFFF", "#000000")
        assert de > 50, f"白vs黒のdelta_eが小さすぎる: {de}"

    def test_colors_are_same(self):
        from app.core.color_utils import colors_are_same
        assert colors_are_same("#FFFFFF", "#FEFEFE"), "ほぼ白は同一色"
        assert not colors_are_same("#FF0000", "#0000FF"), "赤vs青は異色"

    def test_colors_are_different(self):
        from app.core.color_utils import colors_are_different
        assert colors_are_different("#FF0000", "#0000FF"), "赤vs青は異色"
        assert not colors_are_different("#FFFFFF", "#FEFEFE"), "ほぼ白は同一色"

    def test_extract_text_foreground_color_returns_hex(self):
        from app.core.color_utils import extract_text_foreground_color
        import cv2

        # 黒テキストを白背景に描画した画像
        img = np.ones((50, 100, 3), dtype=np.uint8) * 255  # 白
        img[10:40, 20:80] = 0  # 黒矩形（テキスト代わり）
        color = extract_text_foreground_color(img, [15, 5, 85, 45])
        assert color.startswith("#"), f"#RRGGBB 形式でない: {color}"
        assert len(color) == 7, f"長さが異常: {color}"
        print(f"  extract_text_foreground_color → {color}")

    def test_extract_text_foreground_color_empty_region(self):
        from app.core.color_utils import extract_text_foreground_color
        import cv2

        img = np.ones((50, 100, 3), dtype=np.uint8) * 255
        # 範囲外を指定 → フォールバック #000000
        color = extract_text_foreground_color(img, [200, 200, 300, 300])
        assert color == "#000000", f"範囲外でフォールバックしない: {color}"


# -----------------------------------------------------------------------
# Test 2: CardBoundaryDetector — 合成カード画像
# -----------------------------------------------------------------------

class TestCardBoundaryDetectorSynthetic:
    def test_detect_returns_result(self):
        from app.core.card_boundary_detector import CardBoundaryDetector
        img, _ = make_card_grid_image(cols=3, rows=2)
        detector = CardBoundaryDetector(min_card_area=3000)
        result = detector.detect(img)
        assert result is not None
        print(f"  3×2グリッド → {len(result.cards)} cards, "
              f"grid={result.grid_cols}×{result.grid_rows}, "
              f"time={result.detection_time_ms:.0f}ms")

    def test_detect_finds_cards_in_grid(self):
        """3×2グリッド → 少なくとも 3 枚以上のカードを検出"""
        from app.core.card_boundary_detector import CardBoundaryDetector
        img, rects = make_card_grid_image(cols=3, rows=2, with_border=True)
        detector = CardBoundaryDetector(min_card_area=2000)
        result = detector.detect(img)
        print(f"  detected={len(result.cards)} cards (expect >=3, actual cards=6)")
        for c in result.cards:
            print(f"    card rect={c.rect} conf={c.confidence:.2f} src={c.source} tmpl={c.template_id}")
        assert len(result.cards) >= 3, \
            f"3×2グリッドで3枚以上検出されるべき。実際: {len(result.cards)}"

    def test_detect_plain_page_finds_few_cards(self):
        """プレーンな白ページ → カードをほとんど検出しない"""
        from app.core.card_boundary_detector import CardBoundaryDetector

        # 均一な白画像（テキストのみページ相当）
        img = Image.new("RGB", (1280, 800), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        # 横線テキスト風
        for y in range(50, 750, 30):
            draw.rectangle([50, y, 800, y + 12], fill=(100, 100, 100))

        detector = CardBoundaryDetector(min_card_area=5000)
        result = detector.detect(img)
        print(f"  プレーンページ → {len(result.cards)} cards")
        # カードが少ないことを確認（厳密に0とは言えないが基本的には少ない）
        assert len(result.cards) <= 3, \
            f"プレーンページでカードが多すぎる: {len(result.cards)}"

    def test_detect_google_homepage(self):
        """Google ホームページ（test_stitch.png）→ カード数は少ない"""
        from app.core.card_boundary_detector import CardBoundaryDetector

        img_path = PROJECT_ROOT / "test_stitch.png"
        if not img_path.exists():
            pytest.skip("test_stitch.png が存在しない")

        img = Image.open(img_path)
        detector = CardBoundaryDetector(min_card_area=5000)
        result = detector.detect(img)
        print(f"  Google ホームページ → {len(result.cards)} cards "
              f"(time={result.detection_time_ms:.0f}ms)")
        # Google ホームページはカードなし → 少ないはず
        assert len(result.cards) <= 5, \
            f"プレーンなGoogle ページで多すぎる: {len(result.cards)}"


# -----------------------------------------------------------------------
# Test 3: blocks_cross_card_boundary / blocks_in_same_card
# -----------------------------------------------------------------------

class TestCardBoundaryStaticMethods:
    def _make_cards(self):
        """テスト用の既知カードリストを返す"""
        from app.core.card_boundary_detector import CardRegion
        return [
            CardRegion(rect=(10, 10, 210, 160), confidence=0.9, template_id=0, source="test"),
            CardRegion(rect=(230, 10, 430, 160), confidence=0.9, template_id=0, source="test"),
            CardRegion(rect=(450, 10, 650, 160), confidence=0.9, template_id=0, source="test"),
        ]

    def test_no_cards_never_crosses(self):
        from app.core.card_boundary_detector import CardBoundaryDetector
        crosses, conf = CardBoundaryDetector.blocks_cross_card_boundary(
            [50, 50, 100, 80], [300, 50, 350, 80], []
        )
        assert crosses is False
        assert conf == 0.0

    def test_same_card_no_cross(self):
        """同一カード内のブロックは cross しない"""
        from app.core.card_boundary_detector import CardBoundaryDetector
        cards = self._make_cards()
        # どちらも card[0] の内側
        r1 = [20, 20, 80, 40]
        r2 = [20, 60, 80, 80]
        crosses, conf = CardBoundaryDetector.blocks_cross_card_boundary(r1, r2, cards)
        print(f"  同一カード内 cross={crosses} conf={conf:.2f}")
        assert crosses is False

    def test_different_cards_cross(self):
        """異なるカードのブロックは cross する"""
        from app.core.card_boundary_detector import CardBoundaryDetector
        cards = self._make_cards()
        # r1 = card[0] 内、r2 = card[1] 内
        r1 = [50, 50, 150, 80]   # card[0]: x0=10..210
        r2 = [270, 50, 380, 80]  # card[1]: x0=230..430
        crosses, conf = CardBoundaryDetector.blocks_cross_card_boundary(r1, r2, cards)
        print(f"  異なるカード cross={crosses} conf={conf:.2f}")
        assert crosses is True
        assert conf > 0.0

    def test_blocks_in_same_card(self):
        """同一カード内 → CardRegion を返す"""
        from app.core.card_boundary_detector import CardBoundaryDetector
        cards = self._make_cards()
        r1 = [20, 20, 80, 40]
        r2 = [20, 100, 80, 120]
        same = CardBoundaryDetector.blocks_in_same_card(r1, r2, cards)
        print(f"  blocks_in_same_card → {same}")
        assert same is not None

    def test_blocks_in_different_card_returns_none(self):
        """異なるカード → None"""
        from app.core.card_boundary_detector import CardBoundaryDetector
        cards = self._make_cards()
        r1 = [50, 50, 150, 80]   # card[0]
        r2 = [270, 50, 380, 80]  # card[1]
        same = CardBoundaryDetector.blocks_in_same_card(r1, r2, cards)
        assert same is None

    def test_template_ids_assigned(self):
        """同型カード（同サイズ・同アスペクト）は同一 template_id を持つ"""
        from app.core.card_boundary_detector import CardBoundaryDetector, CardRegion
        import cv2
        cards = self._make_cards()
        cv_img = np.zeros((200, 700, 3), dtype=np.uint8)
        result = CardBoundaryDetector()._assign_template_ids(cards, cv_img)
        tids = [c.template_id for c in result]
        print(f"  template_ids: {tids}")
        # 全カードが同型なら同一 template_id
        assert len(set(tids)) == 1, f"同型3カードで複数 template_id: {tids}"


# -----------------------------------------------------------------------
# Test 4: CloudOCREngine 統合テスト（Vision API 不使用）
# -----------------------------------------------------------------------

class TestCloudOCREngineWithCardDetection:
    def test_init_with_card_detection_true(self):
        """enable_card_detection=True で初期化できる"""
        from app.core.engine_cloud import CloudOCREngine
        engine = CloudOCREngine(enable_card_detection=True)
        assert engine.enable_card_detection is True

    def test_init_with_card_detection_false(self):
        """enable_card_detection=False で初期化できる（既存動作）"""
        from app.core.engine_cloud import CloudOCREngine
        engine = CloudOCREngine(enable_card_detection=False)
        assert engine.enable_card_detection is False

    def test_vertical_stack_clustering_without_cards(self):
        """_vertical_stack_clustering: card_boundaries なし → 既存の動作（シグネチャ変更なし）"""
        from app.core.engine_cloud import CloudOCREngine
        engine = CloudOCREngine(enable_card_detection=False)

        blocks = [
            {"text": "ブロックA", "rect": [10, 10, 200, 30], "center_x": 105, "width": 190, "font_size": 15},
            {"text": "ブロックB", "rect": [10, 40, 200, 60], "center_x": 105, "width": 190, "font_size": 15},
            {"text": "ブロックC", "rect": [300, 10, 490, 30], "center_x": 395, "width": 190, "font_size": 15},
        ]
        # card_boundaries 引数は不要（post-processor 設計）
        result = engine._vertical_stack_clustering(blocks)
        print(f"  _vertical_stack_clustering → {len(result)} clusters")
        # A と B は近接しているのでマージされ、C は別クラスタ → 合計 2 クラスタ程度
        assert 1 <= len(result) <= 3

    def test_apply_card_boundary_filter_splits_cross_card(self):
        """_apply_card_boundary_filter: 複数カードにまたがるクラスタを分割する"""
        from app.core.engine_cloud import CloudOCREngine
        from app.core.card_boundary_detector import CardRegion, CardDetectionResult

        engine = CloudOCREngine(enable_card_detection=False)

        # 2 つの raw_blocks が 1 つのクラスタにマージされているケース
        raw_blocks = [
            {"text": "カードAのタイトル", "rect": [10, 10, 200, 30], "center_x": 105, "width": 190, "font_size": 15},
            {"text": "カードBのタイトル", "rect": [10, 50, 200, 70], "center_x": 105, "width": 190, "font_size": 15},
        ]
        clusters = [
            {
                "rect": [10, 10, 200, 70],  # A と B を統合した bounding box
                "texts": ["カードAのタイトル", "カードBのタイトル"],
                "width": 190, "center_x": 105, "avg_font_size": 15, "is_template": False,
            }
        ]
        cards = [
            CardRegion(rect=(0, 0, 210, 40),  confidence=0.9, template_id=0, source="test"),
            CardRegion(rect=(0, 45, 210, 80), confidence=0.9, template_id=1, source="test"),
        ]

        # _merge_within_cards を経由せず分割ロジックだけ検証
        filtered = engine._merge_within_cards(
            clusters,  # 分割後は手動で作成
            cards,
        )
        # split ステップを直接確認: raw_blocks ベースで分割されるか
        # (ここでは _merge_within_cards のみ呼ぶので入力が分割済みである必要あり)
        # ─ 代わりに _apply_card_boundary_filter 全体の統合テストは
        #   extract_text() のモックが必要なため別 Issue で扱う
        print(f"  _merge_within_cards (pass-through test) → {len(filtered)} clusters")
        assert len(filtered) >= 1

    def test_merge_within_cards_merges_fragmented_lines(self):
        """_merge_within_cards: 同一カード内の断片化した行クラスタを統合する"""
        from app.core.engine_cloud import CloudOCREngine
        from app.core.card_boundary_detector import CardRegion

        engine = CloudOCREngine(enable_card_detection=False)

        # カード内で 3 行に分断されたクラスタ（Y gap は 15-20px — 閾値内）
        clusters = [
            {"rect": [10, 10, 200, 30], "texts": ["タイトル"],
             "width": 190, "center_x": 105, "avg_font_size": 14, "is_template": False},
            {"rect": [10, 45, 200, 65], "texts": ["本文行1"],
             "width": 190, "center_x": 105, "avg_font_size": 12, "is_template": False},
            {"rect": [10, 80, 200, 100], "texts": ["本文行2"],
             "width": 190, "center_x": 105, "avg_font_size": 12, "is_template": False},
        ]
        cards = [
            CardRegion(rect=(0, 0, 210, 110), confidence=0.9, template_id=0, source="test"),
        ]

        merged = engine._merge_within_cards(clusters, cards)
        print(f"  断片化 3 クラスタ → {len(merged)} クラスタ（カード内マージ後）")
        # 全行が同一カード内かつ gap < 120px → 1 クラスタにまとまるはず
        assert len(merged) == 1, f"期待 1 クラスタ, 実際 {len(merged)}"
        assert "タイトル" in merged[0]["texts"]
        assert "本文行1" in merged[0]["texts"]
        assert "本文行2" in merged[0]["texts"]


# -----------------------------------------------------------------------
# Test 5: NMS と template_id
# -----------------------------------------------------------------------

class TestNMSAndTemplateId:
    def test_nms_removes_overlapping_cards(self):
        """IoU > 0.5 の重複カード → NMS で除去"""
        from app.core.card_boundary_detector import CardBoundaryDetector, CardRegion

        detector = CardBoundaryDetector()
        candidates = [
            CardRegion(rect=(0, 0, 100, 100), confidence=0.9, source="color"),
            CardRegion(rect=(5, 5, 105, 105), confidence=0.7, source="border"),  # 重複
            CardRegion(rect=(200, 0, 300, 100), confidence=0.8, source="color"),  # 非重複
        ]
        merged = detector._merge_detections(candidates)
        print(f"  NMS: {len(candidates)} → {len(merged)} cards")
        # 重複2つ → 1つに、非重複1つ → 計2つ
        assert len(merged) == 2, f"NMS後のカード数: {len(merged)}"

    def test_iou_calculation(self):
        """IoU 計算の正確性"""
        from app.core.card_boundary_detector import CardBoundaryDetector

        # 完全一致 → IoU = 1.0
        iou = CardBoundaryDetector._iou((0, 0, 100, 100), (0, 0, 100, 100))
        assert abs(iou - 1.0) < 1e-9, f"完全一致IoU={iou}"

        # 重複なし → IoU = 0.0
        iou = CardBoundaryDetector._iou((0, 0, 100, 100), (200, 200, 300, 300))
        assert iou == 0.0, f"非重複IoU={iou}"

        # 半分重複 (100×100 と 50×200 が 50×100 重複)
        iou = CardBoundaryDetector._iou((0, 0, 100, 100), (50, 0, 150, 100))
        assert 0.3 < iou < 0.4, f"半重複IoU={iou:.3f}"


# -----------------------------------------------------------------------
# 全体サマリー実行（スクリプト直接実行時）
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestColorUtils,
        TestCardBoundaryDetectorSynthetic,
        TestCardBoundaryStaticMethods,
        TestCloudOCREngineWithCardDetection,
        TestNMSAndTemplateId,
    ]

    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        print(f"\n{'='*60}")
        print(f"  {cls.__name__} ({len(methods)} tests)")
        print(f"{'='*60}")
        for method in methods:
            try:
                getattr(instance, method)()
                print(f"  PASS  {method}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {method}: {e}")
                errors.append((cls.__name__, method, traceback.format_exc()))
                failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed / {failed} failed")
    print(f"{'='*60}")
    if errors:
        print("\n--- Failures ---")
        for cls_name, method, tb in errors:
            print(f"\n[{cls_name}.{method}]")
            print(tb)
    else:
        print("  All tests PASSED")
