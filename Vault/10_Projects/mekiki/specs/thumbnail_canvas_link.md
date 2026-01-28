# サムネイル→Canvas連動仕様

## 正式仕様（2026-01-29確認）

### 1. サムネイルの定義

- **サムネイル** = パラグラフとして認識されるクラスターのセグメント（単位）
- 各サムネイルは**ユニークナンバー**（area_code）を持つ

### 2. クリック時の動作

- シートのサムネイルをクリック
- → Source Canvas上の**同じユニークナンバーを持つ範囲**にハイライト矩形を表示

### 3. スクロール連動

- ハイライト位置が見えるようにCanvasが自動スクロール

## 技術的実装要件

```
サムネイル（area_code: "Col0-W1_P-12"）
    ↓ クリック
SpreadsheetPanel._on_thumbnail_click(region, source, pair)
    ↓ コールバック
AdvancedComparisonView._on_spreadsheet_row_select(web_id, pdf_id, pair)
    ↓ area_codeでregion検索
web_regions / pdf_regions から該当regionを特定
    ↓ region.rect を使用
_highlight_region_on_canvas(canvas, region, color)
```

## 問題の根本原因（調査中）

- `region.rect`の座標系と表示キャンバスの座標系が一致していない
- または、正しいregionが見つかっていない
