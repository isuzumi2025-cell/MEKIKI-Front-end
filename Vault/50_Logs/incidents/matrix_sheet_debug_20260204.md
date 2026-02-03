# MEKIKI マトリクス比較シート デバッグレポート

**日時**: 2026-02-04 02:15  
**エージェント**: Cursor (ByCursor)  
**重大度**: 中  
**ステータス**: 調査中

---

## 1. 報告された問題

| # | 問題 | カテゴリ | 影響範囲 |
|---|------|---------|---------|
| 1 | サムネイルがパラグラフと一致しない | UI/データ連携 | SpreadsheetPanel |
| 2 | PDFソースウィンドウに選択範囲が表示されない | 描画/座標変換 | AdvancedComparisonView |
| 3 | パラグラフが短すぎる | OCR/クラスタリング | engine_cloud.py |
| 4 | AI分析エラー (bad window path name) | Tkinter/ウィジェット破棄 | SpreadsheetPanel |

---

## 2. アーキテクチャ概要（参照: architecture.md）

```
User Action
    ↓
UnifiedApp._run_ai_analysis_mode_impl()
    ↓
┌─────────────────────────────────────────────────────────────┐
│ OCR Pipeline                                                 │
│ ┌──────────────┐    ┌───────────────┐    ┌───────────────┐  │
│ │ CloudOCR     │ →  │ HybridOCR     │ →  │ Paragraph     │  │
│ │ (Clustering) │    │ (Gemini補正)  │    │ Matcher       │  │
│ └──────────────┘    └───────────────┘    └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Data Flow                                                    │
│ web_paragraphs[] + pdf_paragraphs[]                          │
│     ↓ match_paragraphs()                                     │
│ sync_pairs[] (SyncPair dataclass)                            │
│     ↓                                                        │
│ web_regions[] + pdf_regions[] (ParaRegion objects)           │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ GUI Update                                                   │
│ view.spreadsheet_panel.update_data(                          │
│     sync_pairs, web_regions, pdf_regions,                    │
│     stitched_web, stitched_pdf,                              │
│     web_pages_list, pdf_pages_list  ← ★ 今回修正したパラメータ│
│ )                                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 根本原因分析

### 3.1 問題1: サムネイル不一致

**カプセル**: `ThumbnailManager.create_thumbnail_from_global_bbox()`

**原因仮説**:
1. `region.rect` がスティッチ座標（グローバルY）とページローカル座標で混在
2. `page_id` が正しく設定されていない（デフォルト -1 のまま）
3. ページ境界をまたぐ領域の座標変換エラー

**検証方法**:
```python
# 診断ログの追加
for i, r in enumerate(web_regions[:5]):
    print(f"[Diag] Region {i}: page_id={r.page_id}, rect={r.rect}")
```

**関連ログ（過去インシデント）**:
- 2026-01-28: 「画像サイズがおかしい」「PDFが抽出できていない」

---

### 3.2 問題2: PDF選択範囲非表示

**カプセル**: `AdvancedComparisonView._redraw_regions()`

**原因**:
- ログ: `[_redraw_regions] pdf_regions=0` 
- AI分析モードが `bad window path name` エラーで中断
- `view.pdf_regions` が空のまま

**データフロー検証**:
```
_run_ai_analysis_mode_impl() Line 1580-1581:
    view.web_regions = web_regions
    view.pdf_regions = pdf_regions
        ↓
spreadsheet_panel.update_data() Line 1631-1639 ← ★ ここでエラー発生
        ↓
_redraw_regions() が古いデータ（空）で実行
```

**修正済み**: `_create_row()` にウィジェット有効性チェック追加

---

### 3.3 問題3: パラグラフが短い

**カプセル**: `engine_cloud.py` (🔴 Core File - 変更注意)

**現行パラメータ** (Match:70 Baseline):
```python
overlap_ratio = 0.6   # 重複判定
gap_x = 2.5           # 水平ギャップ許容
min_text_length = 5   # 最小文字数
```

**原因仮説**:
1. クラスタリングが過度に分割している
2. 日本語スペース正規化で意図しない分割
3. Gemini補正がテキストを短縮している

**診断方法**:
```python
# unified_app.py 内での診断
for cluster in clusters:
    raw_text = cluster.get('text', '')
    print(f"[Cluster] len={len(raw_text)}: {raw_text[:50]}...")
```

**関連ログ（過去インシデント）**:
- 2026-01-28: 「パラグラフ短文化」「パラグラフ選択範囲がベンチマークより狭い」

---

### 3.4 問題4: AI分析エラー

**カプセル**: `SpreadsheetPanel._create_row()`

**エラー**:
```
_tkinter.TclError: bad window path name 
".!ctkframe2...!spreadsheetpanel...!text"
```

**原因**:
- `_render_visible_rows()` が非同期で行を生成中
- 親ウィジェット（`scroll_frame`）が破棄された後に `pack()` 呼び出し
- Tkinter/CustomTkinter のライフサイクル問題

**修正内容**:
```python
# ByCursor Fix: ウィジェット有効性チェック
def _create_row(self, index: int, pair):
    try:
        if not self.scroll_frame.winfo_exists():
            return None
    except Exception:
        return None
    # ... 以下省略
```

---

## 4. Orchestra System との連携状況

### 4.1 エージェント状態

| エージェント | 状態 | 役割 |
|-------------|------|------|
| Antigravity (Claude/Cursor) | ✅ Active | IDE統合、コーディング |
| Clawdbot (GPT-5.2) | ✅ Ready | 戦略立案 |
| Grok | ⚠️ 未使用 | リアルタイム検索 |
| Gemini (Reviewer) | ⚠️ 未使用 | レビュー・スコアリング |

### 4.2 推奨フロー

```
現在: Antigravity 単独でデバッグ中
推奨: 
  1. Obsidian (内部情報) ← 実行中
  2. Grok (外部調査) ← スキップ可
  3. GPT-5.2 (戦略) ← 複雑な判断時に相談
  4. Gemini (レビュー) ← 修正完了後に検証
```

---

## 5. 外部Web連携

### 5.1 Slack連携

- **状態**: `🎧 Async Slack Listener started`
- **用途**: 通知、遠隔操作

### 5.2 Gemini API

- **状態**: FutureWarning（deprecated package）
- **影響**: 機能には影響なし、将来的にパッケージ更新が必要

### 5.3 GitHub連携

- **状態**: ✅ 接続済み (`isuzumi2025-cell/MEKIKI`)
- **用途**: バージョン管理、バックアップ

---

## 6. 修正済み項目

| # | 修正内容 | ファイル | 状態 |
|---|---------|---------|------|
| 1 | ウィジェット有効性チェック | `spreadsheet_panel.py` | ✅ |
| 2 | None返却処理 | `spreadsheet_panel.py` | ✅ |
| 3 | `pdf_pages_list` 初期化 | `advanced_comparison_view.py` | ✅ |
| 4 | `web_pages_list` 同期 | `advanced_comparison_view.py` | ✅ |
| 5 | クロージャ変数キャプチャ | `unified_app.py` | ✅ |

---

## 7. 残存問題と次のアクション

### 優先度: High

| # | 問題 | アクション | 担当カプセル |
|---|------|-----------|-------------|
| 1 | サムネイル不一致 | `page_id` 設定の検証 | `unified_app.py` Line 1295 |
| 2 | PDF選択範囲 | `_redraw_regions()` タイミング検証 | `advanced_comparison_view.py` |

### 優先度: Medium

| # | 問題 | アクション | 担当カプセル |
|---|------|-----------|-------------|
| 3 | パラグラフ短縮 | クラスタリングパラメータ検証 | `engine_cloud.py` 🔴 |
| 4 | Gemini FutureWarning | パッケージ更新 | `llm_client.py` |

---

## 8. 検証手順

1. **アプリ再起動**
2. **Web読み込み** → クロール実行
3. **PDF読み込み** → ファイル選択
4. **「ハイブリッドOCR」ボタン押下**
5. **確認項目**:
   - [ ] AI分析エラーが発生しない
   - [ ] Live Comparison Sheetにデータ表示
   - [ ] サムネイルがパラグラフ内容と一致
   - [ ] 行クリック → ソースウィンドウにハイライト表示

---

## 参照

- [[architecture]] - システム依存関係図
- [[CURSOR_CONTEXT]] - 実装ルール
- [[2026-01-28_hybridocr_regression]] - 類似インシデント
- [[unauthorized_hybrid_ocr_disable_20260131]] - 関連インシデント

---

Tags: #Incident #Debug #MEKIKI #ByCursor #20260204
