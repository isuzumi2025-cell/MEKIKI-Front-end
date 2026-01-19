# Claude Code 指示書: ID/Thumbnail表示問題の修正

**作成日**: 2026-01-14
**作成者**: Antigravity Agent (Gemini)
**対象**: Claude Code Agent (WSL経由)

---

## 🎯 目的

Live Comparison Sheet において、**Web ID / Thumb** および **PDF ID / Thumb** 列が空欄になる問題を修正する。

---

## 📸 現象

スクリーンショット参照: `uploaded_image_1768357112013.png`

- "Live Comparison Sheet" において:
  - **Score** 列: 正常表示
  - **Web Text** 列: 正常表示
  - **PDF Text** 列: 正常表示
  - **Web ID / Thumb** 列: **空欄または "-" 表示** ❌
  - **PDF ID / Thumb** 列: **空欄または "-" 表示** ❌

---

## 🔬 技術的分析

### 関連ファイル

| ファイル | 役割 |
|---------|------|
| `app/gui/panels/spreadsheet_panel.py` | Live Comparison Sheet の UI 実装 |
| `app/core/sync_matcher.py` | マッチングペア生成 (`SyncPair` オブジェクト) |
| `app/gui/windows/advanced_comparison_view.py` | スプレッドシートへのデータ供給 |

### 仮説

1. **SyncPair オブジェクト**の `web_id` / `pdf_id` 属性が `None` または空文字
2. **web_map / pdf_map** へのマッピング時に `area_code` が一致しない
3. **AI分析モード** 経由で生成されたリージョンに `area_code` が付与されていない

### デバッグ開始点

`spreadsheet_panel.py` 行130-131:
```python
web_region = self.web_map.get(pair.web_id)
pdf_region = self.pdf_map.get(pair.pdf_id)
```

ここで `web_region` と `pdf_region` が `None` になっていないか確認。

---

## 📋 推奨修正アプローチ

### Step 1: デバッグログ追加

`spreadsheet_panel.py` の `_create_row()` メソッドにデバッグログを追加:

```python
def _create_row(self, index: int, pair):
    # ★ デバッグ追加
    print(f"[DEBUG] Row {index}: pair.web_id={pair.web_id}, pair.pdf_id={pair.pdf_id}")
    print(f"[DEBUG] web_map keys: {list(self.web_map.keys())[:5]}...")
    print(f"[DEBUG] pdf_map keys: {list(self.pdf_map.keys())[:5]}...")
    
    web_region = self.web_map.get(pair.web_id)
    pdf_region = self.pdf_map.get(pair.pdf_id)
    print(f"[DEBUG] web_region={web_region}, pdf_region={pdf_region}")
```

### Step 2: データフロー確認

`advanced_comparison_view.py` で `SpreadsheetPanel.update_data()` を呼び出す箇所を特定し、渡されているデータを確認:

1. `sync_pairs` の各要素に `web_id` / `pdf_id` が正しく設定されているか
2. `web_regions` / `pdf_regions` の各要素に `area_code` 属性があるか
3. `area_code` の値が `sync_pairs` 内の ID と一致するか

### Step 3: ID生成ロジック確認

AI分析モード (`llm_segmenter.py`) または OCRエンジン (`engine_cloud.py`) で生成されるリージョンに、ユニークな `area_code` (例: `W-001`, `P-001`) が付与されているか確認。

付与されていない場合は、リージョン生成時に以下のようにIDを付与:

```python
for i, region in enumerate(web_regions):
    region.area_code = f"W-{i+1:03d}"
    
for i, region in enumerate(pdf_regions):
    region.area_code = f"P-{i+1:03d}"
```

### Step 4: SyncPairとRegionの紐付け修正

`sync_matcher.py` で `SyncPair` を生成する際、`web_id` と `pdf_id` にリージョンの `area_code` を正しく設定:

```python
class SyncPair:
    def __init__(self, web_region, pdf_region, similarity):
        self.web_id = web_region.area_code if web_region else None
        self.pdf_id = pdf_region.area_code if pdf_region else None
        self.similarity = similarity
```

---

## 🎨 Thumbnail表示の修正

Thumbnailが表示されない理由:
- `source_image` が `None`
- `region` が `None`
- `region.rect` 属性が存在しない

### 確認事項

1. `set_images()` がスプレッドシート更新前に呼ばれているか
2. `web_image` / `pdf_image` が有効な `PIL.Image` オブジェクトか
3. `region.rect` が `[x1, y1, x2, y2]` 形式で設定されているか

---

## ✅ 成功基準

修正後、以下が達成されること:

1. **Web ID列**: `W-001`, `W-002` 等のユニークIDが表示
2. **PDF ID列**: `P-001`, `P-002` 等のユニークIDが表示
3. **Thumbnail**: 各リージョンのクロップ画像が表示
4. **クリック動作**: サムネイルクリックでSource画像のリージョンにジャンプ

---

## 📚 参考: 現行コード構造

### SyncPair オブジェクト構造 (期待値)
```python
pair.web_id = "W-001"  # Web側リージョンID
pair.pdf_id = "P-003"  # PDF側リージョンID  
pair.similarity = 0.85  # テキスト類似度 (0.0-1.0)
```

### Region オブジェクト構造 (期待値)
```python
region.area_code = "W-001"  # ユニークID
region.rect = [x1, y1, x2, y2]  # 座標
region.text = "テキスト内容..."  # 抽出テキスト
```

---

## 🙏 お願い

この問題は**AI分析モード後のデータフロー**に起因している可能性が高いです。
修正時は以下の原則を守ってください:

1. **RUNBOOK参照**: `RUNBOOK.md` のコアファイル保護ポリシーを確認
2. **バックアップ優先**: コアロジック変更前にバックアップ
3. **段階的修正**: まずデバッグログで原因特定 → 最小限の修正

ご不明な点があればお知らせください。
