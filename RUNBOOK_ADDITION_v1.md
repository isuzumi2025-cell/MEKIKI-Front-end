# MEKIKI Runbook 追加要綱 - 選択・編集機能復旧計画

**作成日**: 2026-01-19 17:07
**対象**: Phase 1.5 - 手動選択とリアルタイムシート反映

---

## 1. 現状の問題分析

### 1.1 座標ズレ問題

**症状**:

- 2ページ目以降で選択範囲が表示されない
- 異なるページの座標メタデータが現在の表示画像に重複表示

**根本原因**:

```
各ページ座標の定義がパラグラフリンクに基づいていない
→ 全ページの領域が単一キャンバスに描画されている
```

**解決策**:

```python
# 読み込み完了時にページ単位で座標を関連付け
def _load_with_page_binding(self):
    for page_idx, page in enumerate(self.pdf_pages_list):
        page['regions'] = []  # ページ固有の領域リスト
        page['offset_y'] = cumulative_height  # Y座標オフセット
```

### 1.2 手動編集機能の欠落

**現状**: 領域選択後の移動・リサイズが不可

**バックアップで発見した優れた実装** (20260108):

```python
# L807-825: ドラッグによる矩形移動
def _on_canvas_drag(self, event):
    if not self.selected_region or not self.drag_start:
        return
    
    dx = event.x - self.drag_start[0]
    dy = event.y - self.drag_start[1]
    
    # 矩形を移動
    self.selected_region.rect[0] += dx
    self.selected_region.rect[1] += dy
    self.selected_region.rect[2] += dx
    self.selected_region.rect[3] += dy
    
    self.drag_start = (event.x, event.y)
    self._redraw_regions()

# L827-833: リリース時にリアルタイム更新
def _on_canvas_release(self, event):
    if self.selected_region:
        self._update_text_for_region(self.selected_region)
    self.drag_start = None
```

---

## 2. 復旧対象のレガシーコード

### 2.1 リアルタイムシート反映 (20260108)

| メソッド | 行番号 | 機能 |
|----------|--------|------|
| `_refresh_inline_spreadsheet` | L570-634 | シート全体更新 |
| `_create_spreadsheet_row` | L636-737 | 行作成+サムネイル |
| `_on_spreadsheet_row_click` | L739-752 | 行クリック→領域選択 |

### 2.2 類似検出機能 (20260111)

| メソッド | 行番号 | 機能 |
|----------|--------|------|
| `✨ 類似検出` ボタン | L137 | UI追加 |
| `_propagate_from_editor` | L2380 | 類似領域検出 |

---

## 3. 実装計画

### Phase 1.5: 手動選択とリアルタイム反映

#### Step 1: ページ単位座標システム (2h)

```python
# 新規: app/sdk/canvas/page_coords.py
class PageCoordinateManager:
    """ページ単位の座標管理"""
    
    def __init__(self):
        self.pages = {}  # page_idx -> PageData
    
    def register_page(self, page_idx, image, y_offset):
        self.pages[page_idx] = {
            'image': image,
            'offset_y': y_offset,
            'regions': []
        }
    
    def get_regions_for_page(self, page_idx):
        return self.pages.get(page_idx, {}).get('regions', [])
```

#### Step 2: レガシーコード移植 (3h)

```python
# 移植元: _OLD/gui/windows/advanced_comparison_view_backup_20260108.py
# 移植先: comparison_mixins/edit_mixin.py

class EditMixin:
    def _on_canvas_drag(self, event):
        # L807-825のコードを移植
    
    def _on_canvas_release(self, event):
        # L827-833のコードを移植
    
    def _update_text_for_region(self, region):
        # L885-888を実装
```

#### Step 3: 類似検出SDK化 (2h)

```python
# 新規: app/sdk/similarity/detector.py
import logging

logger = logging.getLogger(__name__)

class SimilarityDetector:
    """類似領域検出 SDK"""
    
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        logger.info(f"SimilarityDetector initialized (threshold={threshold})")
    
    def find_similar(self, template: dict, candidates: list) -> list:
        """テンプレートに類似した候補を検出"""
        logger.info(f"Searching {len(candidates)} candidates for similar regions")
        results = []
        # 実装...
        logger.info(f"Found {len(results)} similar regions")
        return results
```

---

## 4. 検証手順

### 4.1 HybridOCR前の手動選択

1. 画像読み込み完了
2. Canvas上でドラッグ選択
3. 選択領域がシートに即時反映
4. 領域の移動・リサイズが可能

### 4.2 類似検出

1. 1つの領域を選択
2. 「✨ 類似検出」ボタンをクリック
3. 類似領域が自動検出・ハイライト

---

## 5. ファイル構成

```
app/
├── sdk/
│   ├── canvas/
│   │   └── page_coords.py  # [NEW] ページ座標管理
│   └── similarity/
│       └── detector.py     # [NEW] 類似検出SDK
│
├── gui/
│   └── windows/
│       └── comparison_mixins/
│           └── edit_mixin.py  # [UPDATE] レガシー移植
```

---

## 6. 品質基準

| 項目 | 目標 |
|------|------|
| 選択→シート反映 | <100ms |
| 領域移動 | 60fps |
| 類似検出 | <2秒 |
| ログ出力 | 全操作記録 |

---

**優先度**: 🔴 最高
**工数見積**: 7時間
