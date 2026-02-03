"""
サムネイル生成ロジック検証用テストハーネス
各バックアップから抽出したロジックを順に検証
"""

import os
import sys
from PIL import Image, ImageTk
from dataclasses import dataclass
from typing import Optional, Tuple, List

@dataclass
class MockRegion:
    """テスト用リージョン"""
    rect: List[int]
    text: str
    area_code: str
    page_id: int = 1

# ============================================================
# CANDIDATE 1: backup_ParagraphSorted_SUCCESS_20260113
# ============================================================
def create_thumbnail_success_v1(source_image, region, width: int = 45, height: int = 35):
    """
    SUCCESS版の_create_thumbnail
    - source_image: PIL.Image
    - region: rect属性を持つオブジェクト
    - 直接region.rectを使用
    """
    if not source_image or not region or not hasattr(region, 'rect'):
        return None
        
    try:
        x1, y1, x2, y2 = region.rect
        x1 = max(0, int(x1))
        y1 = max(0, int(y1))
        x2 = min(source_image.width, int(x2))
        y2 = min(source_image.height, int(y2))
        
        if x2 <= x1 or y2 <= y1:
            print(f"  [V1] Invalid bbox: ({x1},{y1},{x2},{y2}) for image {source_image.size}")
            return None
            
        cropped = source_image.crop((x1, y1, x2, y2))
        print(f"  [V1] OK: cropped {cropped.size} from ({x1},{y1},{x2},{y2})")
        
        # Resize
        aspect = cropped.height / cropped.width if cropped.width > 0 else 1
        new_w = width
        new_h = min(int(new_w * aspect), height)
        if new_h < 1: new_h = 1
        if new_w < 1: new_w = 1
            
        resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return resized  # 検証用にPIL.Imageを返す
    except Exception as e:
        print(f"  [V1] Error: {e}")
        return None

# ============================================================
# CANDIDATE 2: ページ対応版（page_idで画像選択）
# ============================================================
def create_thumbnail_page_aware(region, pages_list, fallback_image, source: str, width: int = 80, height: int = 60):
    """
    ページ対応版
    - region.page_idで正しいページ画像を選択
    - region.rectはページ相対座標
    """
    if not region:
        return None
        
    bbox = getattr(region, 'rect', None)
    if not bbox:
        return None
    
    page_id = getattr(region, 'page_id', 1)
    
    # ページリストから正しいページ画像を取得
    page_image = None
    if pages_list and len(pages_list) >= page_id and page_id > 0:
        page_data = pages_list[page_id - 1]
        page_image = page_data.get('image')
        print(f"  [V2] Using page {page_id} image: {page_image.size if page_image else 'None'}")
    
    if not page_image:
        print(f"  [V2] Fallback to stitch image")
        page_image = fallback_image
    
    if not page_image:
        return None
    
    # サムネイル作成
    return create_thumbnail_success_v1(page_image, region, width, height)

# ============================================================
# テスト実行
# ============================================================
def test_candidates():
    """各候補をテスト"""
    # ダミーデータ作成
    # 1000x2000のダミー画像（赤→青のグラデーション）
    test_img = Image.new('RGB', (1000, 2000))
    for y in range(2000):
        r = int(255 * (1 - y/2000))
        b = int(255 * y/2000)
        for x in range(1000):
            test_img.putpixel((x, y), (r, 50, b))
    
    # テストリージョン
    regions = [
        MockRegion(rect=[100, 100, 300, 200], text="Test 1", area_code="P1-1", page_id=1),
        MockRegion(rect=[100, 500, 300, 600], text="Test 2", area_code="P1-2", page_id=1),
        MockRegion(rect=[100, 1500, 300, 1600], text="Test 3 (far down)", area_code="P2-1", page_id=2),
    ]
    
    # ページリスト（2ページ、各1000x1000）
    page1 = test_img.crop((0, 0, 1000, 1000))
    page2 = test_img.crop((0, 1000, 1000, 2000))
    pages_list = [{'image': page1}, {'image': page2}]
    
    print("=" * 60)
    print("CANDIDATE 1: SUCCESS版（ステッチ画像＋ステッチ座標）")
    print("=" * 60)
    for r in regions:
        print(f"\nRegion: {r.area_code}, rect={r.rect}")
        thumb = create_thumbnail_success_v1(test_img, r)
        if thumb:
            print(f"  Result: {thumb.size}")
        else:
            print(f"  Result: FAILED")
    
    print("\n" + "=" * 60)
    print("CANDIDATE 2: ページ対応版（ページ画像＋ページ相対座標）")
    print("=" * 60)
    
    # ページ相対座標に変換
    page_relative_regions = [
        MockRegion(rect=[100, 100, 300, 200], text="Test 1", area_code="P1-1", page_id=1),
        MockRegion(rect=[100, 500, 300, 600], text="Test 2", area_code="P1-2", page_id=1),
        MockRegion(rect=[100, 500, 300, 600], text="Test 3 (page 2)", area_code="P2-1", page_id=2),  # 1500-1000=500
    ]
    
    for r in page_relative_regions:
        print(f"\nRegion: {r.area_code}, rect={r.rect}, page_id={r.page_id}")
        thumb = create_thumbnail_page_aware(r, pages_list, test_img, "web")
        if thumb:
            print(f"  Result: {thumb.size}")
        else:
            print(f"  Result: FAILED")
    
    print("\n" + "=" * 60)
    print("結論: どちらのアプローチを採用すべきか")
    print("=" * 60)
    print("CANDIDATE 1: シンプル、ステッチ座標とステッチ画像の整合性が取れていれば動作")
    print("CANDIDATE 2: ページ分けに対応、ページ相対座標とページ画像の整合性が必要")

if __name__ == "__main__":
    test_candidates()
