# コンテ素材抽出ツール v2 実装指示書

## Claude Code Opus 4.5 向け

**作成日**: 2026-01-24
**目的**: 既存コードを流用してStoryboard Extractor v2を効率的に構築

---

## 🎯 ミッション

比較マトリクス画面（`advanced_comparison_view.py`）と同じUI構成で、コンテ素材抽出ツールをリデザインする。

---

## 📋 フェーズ1: ディープリサーチ（流用コード特定）

### 調査対象ファイル

| ファイル | 目的 |
|----------|------|
| `app/gui/windows/advanced_comparison_view.py` | 3パネルレイアウト、タブ切替、手動選択、シート表示 |
| `app/gui/windows/comparison_spreadsheet.py` | スプレッドシートコンポーネント |
| `app/gui/windows/comparison_mixins/selection_mixin.py` | 手動範囲選択Mixin |
| `app/gui/windows/storyboard_extractor.py` | 現行版（リデザイン対象） |
| `app/sdk/selection/manager.py` | 選択管理SDK |

### 流用候補の特定ポイント

1. **3パネルレイアウト構築**
   - `_build_ui()` の `grid_columnconfigure`, `grid_rowconfigure` パターン
   - `_build_left_panel()`, `_build_center_panel()`, `_build_right_panel()`

2. **タブ切替**
   - `CTkTabview` の使用パターン
   - `_on_source_tab_change()` コールバック

3. **キャンバス + 手動選択**
   - `SelectionMixin` の統合方法
   - `_bind_canvas_events()` パターン

4. **スプレッドシート表示**
   - `LiveComparisonSpreadsheet` クラス
   - 行選択時のハイライト連動

---

## 📋 フェーズ2: 構築ロードマップ

### Step 1: GUI骨格（3パネル）

```
現行: サイドバー + コンテンツ（2カラム）
↓
新規: 左Panel + 中央Panel + 下部Sheet（比較マトリクス型）
```

**流用元**: `advanced_comparison_view.py` L199-314 `_build_ui()`

### Step 2: 中央パネル（テキスト/画像タブ）

```
現行: プレビュー/テキスト/画像/パーツ（4タブ）
↓
新規: テキスト/画像（2タブ、比較マトリクスのWeb/PDFと同様）
```

**流用元**: `advanced_comparison_view.py` L332-483 `_build_center_panel()`

### Step 3: Action欄（レイヤー数表示）

```
Action Panel:
├── インポートボタン
├── レイヤー統計表示
│   ├── テキスト: Bold N / Regular M / Light K
│   └── 画像: N個
├── エクスポートボタン群
│   ├── Excel
│   ├── PowerPoint
│   ├── CSV
│   └── PNG
└── ステータス
```

**新規実装**: `LayerAnalyzer` SDK使用

### Step 4: 手動選択（SelectionMixin統合）

**流用元**:

- `comparison_mixins/selection_mixin.py`
- `advanced_comparison_view.py` のMixin統合パターン

### Step 5: 素材シート（下部パネル）

```
| # | サムネイル | タイプ | レイヤー | テキスト |
|---|-----------|--------|---------|---------|
| 1 | [img]     | Text   | Bold    | 見出し... |
```

**流用元**:

- `LiveComparisonSpreadsheet` のRow構造
- `SheetGenerator` SDK使用

### Step 6: エクスポート統合

**新規SDK**: `LayoutExporter` （作成済み）

- `to_pptx()` - 座標配置再現
- `to_excel()` - レイヤー別シート
- `to_csv()` - メタデータ
- `to_png()` - 個別画像

---

## 📋 フェーズ3: 実装タスク

### 3.0-A: GUI リデザイン

- [ ] `_build_ui()` を3パネル構成に変更
- [ ] 中央パネルをテキスト/画像タブに変更
- [ ] Action欄にレイヤー統計表示追加
- [ ] SelectionMixin統合
- [ ] 下部に素材シート追加

### 3.0-B: エクスポート拡張

- [ ] CSVエクスポートボタン追加
- [ ] PNGエクスポートボタン追加
- [ ] 座標配置PPTXエクスポート実装

### 3.0-C: SDK統合

- [ ] `LayerAnalyzer` 統合
- [ ] `SheetGenerator` 統合
- [ ] `LayoutExporter` 統合

---

## 📁 作成済みSDK

以下のSDKファイルは既に作成済み：

```
app/sdk/storyboard/
├── __init__.py
├── layer_analyzer.py      # レイヤー統計
├── sheet_generator.py     # シートデータ生成
└── layout_exporter.py     # 多形式エクスポート
```

---

## 🔧 実行コマンド

```bash
# アプリ起動
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
python run_unified.py
```

---

## 📚 参照Runbook

`.agent/workflows/storyboard-extractor-v2.md`

---

Tags: #ClaudeCode #Opus4.5 #StoryboardExtractor #Implementation
