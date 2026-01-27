# MEKIKI Proofing System - Runbook

**Last Updated**: 2026-01-14
**Backup**: `backup_Case2_ImageDisplayDebug_20260113`

---

## 🚨 エージェント行動原則 (AGENT BEHAVIOR MANDATES)

> **これらの原則は全セッションで最優先で参照すること**

### 原則1: 根本解決優先
問題のあるアーキテクチャに追加実装しない。根本解決が必要な場合は既存コードを**置き換える**。

### 原則2: 結果追及型
見かけの進捗より**実際の問題解決**を優先する。「機能を追加した」は成果ではない。ユーザーの問題が解決したかどうかが成果。

### 原則3: 処理順序の遵守
ユーザーが指定した処理順序を変更しない。「全文比較してからUI反映」と指示されたら、その順序で実装する。

### 原則4: 理解確認の義務
実装前にRUNBOOKと会話ログを参照し、ユーザーの要求を正確に理解してから作業開始する。

---


## ⚠️ CORE FILE PROTECTION POLICY (必読)

以下のファイルは**精度に直結**するため、**UI変更時は絶対に触らない**こと。

| ファイル | 役割 | 変更禁止レベル |
|---------|------|---------------|
| `app/core/engine_cloud.py` | OCRクラスタリング | 🔴 厳禁 |
| `app/core/sync_matcher.py` | マッチングロジック | 🔴 厳禁 |
| `app/core/paragraph_matcher.py` | パラグラフ比較 | 🔴 厳禁 |

**変更が必要な場合**:
1. まず `backup_YYYYMMDD_HHMMSS/` にバックアップ
2. 変更後は必ずOCRテストを実行
3. Match数が下がったらバックアップから復元

---

## ✅ RESOLVED: Match:70 達成 (2026-01-12 16:22)

### セッション要約

**目標**: Match:20の設定復元と精度向上

**結果**: **Match:70（真のパラグラフマッチ）** を達成

### 試行と結果

| 試行 | 変更内容 | 結果 | 判定 |
|-----|---------|------|------|
| 1 | Relaxed Clustering (overlap 0.4, gap_y 80) | Match:2（虚構） | ❌ |
| 2 | 閾値0.50→0.40 | Match:20（虚構） | ❌ |
| 3 | アンカーベースマッチング (15文字) | Match:0 | ❌ |
| 4 | アンカー緩和 (8文字) | Match:1 | △ |
| 5 | **元のバックアップ完全復元** | **Match:70（真）** | ✅ |

### 重要な教訓

> **「Relaxed Clustering」は精度を悪化させた**
> 
> 緩和パラメータ（overlap 0.4, gap_y 80）を適用すると、
> クラスタリングが不適切になり虚構のマッチが発生。
> **元の厳格なパラメータが正しい。**

---

## 🔖 Configuration Checkpoints (重要設定バージョン)

良好な結果が出た設定は必ずここに記録する。

### CHECKPOINT: Match=70（真のパラグラフマッチ）2026-01-12 16:22

**結果**: Sync Rate 36.6%, Match: 70, Matched: 48/131

**バックアップ**: `backup_20260112_004423/`

**復元コマンド**:
```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
Copy-Item "backup_20260112_004423\paragraph_matcher.py" "app\core\paragraph_matcher.py" -Force
Copy-Item "backup_20260112_004423\engine_cloud.py" "app\core\engine_cloud.py" -Force
Copy-Item "backup_20260112_004423\sync_matcher.py" "app\core\sync_matcher.py" -Force
```

**正しいクラスタリング設定 (engine_cloud.py)**:
```python
overlap_ratio > 0.6   # 厳格
left_diff < 30        # 厳格
threshold_y = max(base_size * 2.5, 50)  # 厳格
font_size_tol: 2.5x / 2.0x  # 厳格
gap_x > 15            # 厳格
```

**❌ 使用禁止の設定**:
- overlap 0.4（緩すぎ）
- gap_y 80（緩すぎ）
- gap_x 30（緩すぎ）

---

## 🚀 NEXT: テキスト抽出パイプライン再設計 (2026-01-12)

### 目標
Web/PDF間の**真のパラグラフマッチング**を実現する

---

### 📋 タスクシート

| # | Phase | タスク | 担当ファイル | 状態 |
|---|-------|-------|-------------|------|
| 1 | Header Fix | スクロールキャプチャ時のヘッダー重複を修正 | `enhanced_scraper.py` | [x] ✅ |
| 2 | Export | 検出テキスト+座標をスプレッドシートに出力 | `metadata_exporter.py` (新規) | [x] ✅ |
| 3 | Extract | Web/PDFから全文抽出→クラスタリング→ID付与 | `engine_cloud.py`, `text_comparator.py` | [x] ✅ |
| 4 | Match | パラグラフマッチング→比較レイアウト表示 | `metadata_exporter.py`, `advanced_comparison_view.py` | [x] ✅ |
| 4+ | UI | 「🔍 全文比較」ボタン追加 | `advanced_comparison_view.py` | [x] ✅ |
| **5** | **LLM RAG** | **マルチモーダルLLMパラグラフ生成** | `llm_segmenter.py` | [ ] ⬅️ |

---

### 🧠 Phase 5: AI分析モード (NEW)

**目的**: 座標クラスタリングをバイパスし、LLMがセマンティックにパラグラフ生成

**ボタン**: 「🤖 AI分析モード」（従来OCR実行とは別）

**処理フロー**:
```
1. 全ページ自動スキャン（Web+PDF）
2. 全文抽出（クラスタリングなし）
3. 全文比較 → マッチ検出（8+文字）
4. LLMパラグラフ生成（画像+テキスト）
5. LiveComparisonSheet表示
```

**モード選択**:
| モード | ボタン | 特徴 |
|--------|--------|------|
| 従来モード | OCR実行 | 高速・座標ベース・調整可能 |
| AI分析モード | 🤖 AI分析 | 安定・LLMベース・セマンティック |

---

### 🔧 技術的実装計画

#### Phase 1: ヘッダー重複問題の修正

**問題**: 固定ヘッダーがスクロールキャプチャに何度も含まれる

**解決策**:
```python
# web_crawler.py
async def capture_with_header_removal(page):
    # 固定ヘッダーを検出
    fixed_elements = await page.query_selector_all('[style*="position: fixed"], header')
    
    # ヘッダーを一時的に非表示
    for el in fixed_elements:
        await el.evaluate('el => el.style.display = "none"')
    
    # スクリーンショット取得
    screenshot = await page.screenshot(full_page=True)
    
    # ヘッダーを復元
    for el in fixed_elements:
        await el.evaluate('el => el.style.display = ""')
    
    return screenshot
```

---

#### Phase 2: メタデータをスプレッドシートに出力

**出力形式** (CSV/Excel):
```
ID,Source,Page,X1,Y1,X2,Y2,Text
W-001,web,1,100,200,500,250,"サンプルテキスト..."
P-001,pdf,1,120,180,480,230,"サンプルテキスト..."
```

**新規ファイル**: `app/pipeline/metadata_exporter.py`
```python
def export_ocr_metadata(web_clusters, pdf_clusters, output_path):
    rows = []
    for i, c in enumerate(web_clusters):
        rows.append({
            'ID': f'W-{i+1:03d}',
            'Source': 'web',
            'Page': c.get('page', 1),
            'X1': c['rect'][0], 'Y1': c['rect'][1],
            'X2': c['rect'][2], 'Y2': c['rect'][3],
            'Text': c['text'][:200]
        })
    # PDF側も同様
    # CSVまたはExcelに出力
```

---

#### Phase 3: 全文抽出とクラスタリング

**処理フロー**:
```
1. Web画像 → Vision API → 生テキスト + 座標
2. PDF画像 → Vision API → 生テキスト + 座標
3. 近接テキストをパラグラフに統合
4. ユニークID付与 (W-001, P-001...)
5. メタデータ出力
```

---

#### Phase 4: パラグラフマッチングとレイアウト

**マッチング基準**:
- テキスト共通部分が**8文字以上**存在するペアのみマッチ
- 類似度スコアで優先順位付け

**表示レイアウト**:
```
┌───────────────────────────────────────────────────────────────┐
│ # │ Web ID │ Web Text         │⇔│ PDF Text         │ PDF ID │ Score │
├───────────────────────────────────────────────────────────────┤
│ 1 │ W-001  │ ○○神社は福の神... │✓│ ○○神社は福の神... │ P-003  │ 95%   │
│ 2 │ W-002  │ 住所：福岡市...   │✓│ 住所：福岡市...   │ P-005  │ 88%   │
└───────────────────────────────────────────────────────────────┘
```

---

### 📁 データ出力先

| Phase | 出力ファイル | パス |
|-------|------------|------|
| 2 | メタデータCSV | `OCR/exports/metadata_{timestamp}.csv` |
| 2 | メタデータExcel | `OCR/exports/metadata_{timestamp}.xlsx` |
| 4 | 比較結果Excel | `OCR/exports/comparison_{timestamp}.xlsx` |

---

### 🛠️ 使用技術

| 技術 | 用途 | 既存/新規 |
|------|------|----------|
| `openpyxl` | Excel出力 | 既存 |
| `csv` | CSV出力 | Python標準 |
| `Playwright` | Webキャプチャ | 既存 |
| `Google Cloud Vision API` | OCR | 既存 |
| `PIL/Pillow` | 画像処理 | 既存 |

---

### 📊 データ仕様

#### メタデータCSV形式
```csv
ID,Source,Page,X1,Y1,X2,Y2,Width,Height,TextLength,Text
W-001,web,1,100,200,500,250,400,50,45,"サンプルテキスト..."
W-002,web,1,100,260,500,310,400,50,38,"次のテキスト..."
P-001,pdf,1,120,180,480,230,360,50,45,"サンプルテキスト..."
```

#### カラム定義
| カラム | 型 | 説明 |
|--------|-----|------|
| ID | string | ユニークID (W-001, P-001) |
| Source | string | "web" or "pdf" |
| Page | int | ページ番号 |
| X1, Y1 | int | 左上座標 |
| X2, Y2 | int | 右下座標 |
| Width, Height | int | 幅・高さ (px) |
| TextLength | int | テキスト文字数 |
| Text | string | 抽出テキスト (最大500文字) |

---

### 🔄 処理フロー図

```
┌─────────────────────────────────────────────────────────────┐
│                        入力                                  │
├─────────────────────────────────────────────────────────────┤
│  [PDF ファイル]              [Web URL]                       │
│       ↓                         ↓                           │
│  PDF→画像変換              Playwright キャプチャ            │
│       ↓                         ↓                           │
│  (Phase 1)                 ヘッダー除去                      │
│       ↓                         ↓                           │
├─────────────────────────────────────────────────────────────┤
│                    Vision API OCR                            │
├─────────────────────────────────────────────────────────────┤
│       ↓                         ↓                           │
│  PDF クラスタリング        Web クラスタリング                 │
│       ↓                         ↓                           │
│  (Phase 2) ──────→ メタデータCSV/Excel出力                   │
│       ↓                         ↓                           │
│  PDF パラグラフ            Web パラグラフ                     │
│  P-001, P-002...           W-001, W-002...                  │
├─────────────────────────────────────────────────────────────┤
│                (Phase 3, 4) マッチング                       │
│       ↓                                                     │
│  W-001 ⇔ P-003 (95%)                                        │
│  W-002 ⇔ P-005 (88%)                                        │
│       ↓                                                     │
│  比較スプレッドシート表示 + Excel出力                         │
└─────────────────────────────────────────────────────────────┘
```

---

### 実装優先順位

1. **Phase 2** (メタデータ出力) - デバッグ基盤
2. **Phase 1** (ヘッダー修正) - キャプチャ品質向上
3. **Phase 3** (全文抽出) - パラグラフ形成
4. **Phase 4** (マッチング) - 最終表示

---

## Project Structure

| Directory | Status | Description |
|:--|:--|:--|
| `OCR/` | **Active** | MEKIKI Main App (OCR, GUI, Comparison Tools) |
| `sitemap_app/` | **MVP Done** | Visual Sitemap Generator (Web API + Dashboard) |
| `sitemap_pro/` | **Frozen** | Legacy Sitemap Tool (Backup) |
| `ObsidianVault/` | **Output** | Obsidian RAG Pipeline Output |

---

## Startup Commands

### Main App (MEKIKI Unified)
```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
py -3 run_unified.py
```

### Legacy Version
```powershell
py -3 main.py           # Old UI
py -3 main_dashboard.py # Dashboard only
```

---

## Known Issues

### 1. StandaloneScraper Import Error
**Symptom**: `cannot import name 'Crawler' from 'app.core.crawler'`  
**Cause**: `standalone_scraper.py` tries to import sitemap_pro's Crawler  
**Impact**: New crawl feature does not work  
**Fix**: Rewrite to use `WebCrawler` directly

### 2. Dual Screen Sync Issues
**Symptom**: Comparison sheet window sync sometimes fails  
**Status**: FIXED - Added `_safe_window_exists()`, initialized `sync_pairs`

### 3. OCR Accuracy
**Diagnostic Tool**: `py -3 diagnose_ocr.py <image_path>`

### 4. ID/Thumbnail Display Empty (2026-01-14) 🔴 ACTIVE
**Symptom**: Live Comparison Sheet の "Web ID / Thumb" と "PDF ID / Thumb" 列が空欄  
**Cause**: AI分析モード後、`SyncPair.web_id`/`pdf_id` と `Region.area_code` の紐付けが不正  
**Impact**: リージョンIDとサムネイルが表示されない  
**Debug**: `spreadsheet_panel.py` の `_create_row()` でログ確認  
**Reference**: `docs/CLAUDE_CODE_INSTRUCTIONS_ID_THUMBNAIL_FIX.md`  
**Status**: IN PROGRESS

---

## Feature Status

### GUI Windows

| File | Feature | Status |
|:--|:--|:--|
| `unified_app.py` | Main App | OK (except crawl) |
| `advanced_comparison_view.py` | Advanced Comparison | OK (Fixed) |
| `comparison_spreadsheet.py` | Comparison Sheet | OK |
| `comparison_matrix.py` | Comparison Matrix | OK |
| `detail_inspector.py` | Detail Inspector | OK |
| `dashboard.py` | Dashboard | WARN: Crawl broken |
| `sitemap_viewer.py` | Sitemap Viewer | OK |
| `report_editor.py` | Report Editor | OK |
| `region_editor.py` | Region Editor | OK |

### Core Modules

| File | Feature | Status |
|:--|:--|:--|
| `crawler.py` | WebCrawler | OK |
| `standalone_scraper.py` | Standalone Scraper | BROKEN: Import error |
| `engine_cloud.py` | Cloud OCR | OK |
| `ocr_engine.py` | OCR Engine | OK |
| `enhanced_scraper.py` | Enhanced Scraper | OK |
| `auth_manager.py` | Auth Manager | OK |

---

## Future Options

### Option A: Fix StandaloneScraper
- Rewrite to use `WebCrawler` directly
- Effort: 30 min

### Option B: Restore sitemap_pro
- Fix import paths
- Integrate sitemap_pro properly
- Effort: 2 hours

### Option C: Keep Current + Focus on PDF
- Defer crawl feature
- Focus on PDF Load -> OCR -> Compare workflow
- Effort: 0

---

## Verification Steps

### 1. App Startup Check
```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
py -3 run_unified.py
```

### 2. PDF Load Test
1. Click "PDF Load" button
2. Select PDF file
3. Open "Comparison Matrix"

### 3. OCR Diagnostic
```powershell
py -3 diagnose_ocr.py test.jpg
```

---

## Phase 4 Roadmap: Live Spreadsheet Redesign

### Goal
Unified comparison spreadsheet with cell-source synchronization

### Design
```
| ID   | Web Text      | Match | PDF Text      | Act |
|------|---------------|-------|---------------|-----|
| W001 | Full text...  | 98%   | Full text...  | >>  |
| W002 | Different...  | 45%   | Changed...    | >>  |
```

### Features
- Single spreadsheet (remove duplicate)
- Auto-expanding cell heights for full text
- Click row -> highlight both Web/PDF sources
- Hybrid matching: Position (30%) + Text similarity (70%)

### Files to Create/Modify
- `live_spreadsheet.py` - NEW unified widget
- `advanced_comparison_view.py` - Integration
- `sync_matcher.py` - Hybrid matching

### Status: IN PROGRESS (WIP)

---

## Phase 5: Critical UI Issues (2026-01-11)

### Priority Issues

| # | Issue | Description | Status |
|:--|:--|:--|:--|
| 1 | **Web Region Not Displayed** | OCR scan results don't show region rectangles on Web image | DEBUG ADDED |
| 2 | **PDF Width Not Following** | PDF image doesn't resize to follow Source window width | TODO |
| 3 | **Spreadsheet Thumbnails** | Add thumbnail images below ID in Live Comparison Sheet. Click to jump to Source. | DONE |
| 4 | **Layout Restructure** | Remove Text Comparison panel (right side), expand Source window, make Spreadsheet resizable/separable | DONE |

### Implementation Plan

#### Issue 1: Web Region Display
- Verify `_redraw_regions()` is called after OCR
- Check `scale_x/scale_y` values are set on canvas
- Ensure `region.rect` coordinates are valid

#### Issue 2: PDF Width Follow
- Fix `_display_image()` to recalculate on resize
- Bind `<Configure>` event properly
- Ensure scrollregion updates

#### Issue 3: Spreadsheet Thumbnails
- Modify `SpreadsheetPanel._create_row()` to include thumbnail
- Pass `web_image` and `pdf_image` references to panel
- Add click handler to scroll Source to region

#### Issue 4: Layout Restructure
- Remove `_build_right_panel()` Text Comparison section
- Use `PanedWindow` for resizable layout
- Make Spreadsheet a separate dockable/resizable panel

---

## Troubleshooting

### App Won't Close
```powershell
Get-Process python* | Stop-Process -Force
```

### Import Error Check
```powershell
py -3 -m py_compile app\gui\unified_app.py
```

---

## Phase 6: OCR/編集機能の移植と拡張 (2026-01-11)

### 目的
レガシー `OCRappBackupFile` から実証済み機能を移植し、新機能を追加

### 移植元ファイル

| ファイル | 場所 | 機能 |
|:--|:--|:--|
| `engine_clustering.py` | OCR_reborn/app/core/ | 近接クラスタリング + 孤立吸収 |
| `interactive_canvas.py` | 251220_NewOCR_B4Claude/app/gui/ | 矩形編集 (ドラッグ作成/選択/削除) |
| `matcher.py` | 251220_NewOCR_B4Claude/app/core/ | テキストマッチング (Jaccard+difflib) |
| `analyzer.py` | 251220_NewOCR_B4Claude/app/core/ | コンテンツ分析 + 自動ペアリング |

### 新規実装

| 機能 | 説明 |
|:--|:--|
| **テキストベースオニオンレイヤー** | 画像合成ではなく、テキストクラスター境界を重ね表示 |
| **即時セル反映** | 手動エリア選択 → シート行に即座に反映 |
| **シンクロ率表示** | 各行/全体のテキスト一致率をリアルタイム表示 |

### 実装フェーズ

1. **Phase A**: ClusteringEngine + TextMatcher 移植
2. **Phase B**: InteractiveCanvas 移植
3. **Phase C**: テキストベースオニオンレイヤー実装
4. **Phase D**: 即時セル反映 + シンクロ率表示

### 仕様書
詳細は `implementation_plan.md` を参照

---

## Phase 7: Advanced Proofing System (広告検版コアスキャナー)

**Goal**: 重大差分の取りこぼしゼロ / 監査性 / 運用速度 / 継続改善

### アーキテクチャ

```
Web/PDF入力
  → Capture/Render (Playwright / pypdfium2)
  → Text-first Extract (DOM/PDF Text Layer)
  → Region Proposal + Selective OCR (必要領域のみ)
  → Normalize (全角半角/空白/記号)
  → Paragraphize (行グループ/クラスタ/ロール推定)
  → Fields Extract (価格/日付/URL/寸法/型番)
  → Table Extract (grid化/ヘッダ推定)
  → Visual Alignment (ORB+Homography)
  → Matching (paragraph/table/cell)
  → Diff Classify (text/field/table diff)
  → Rules Engine (severity決定)
  → Review Queue (危険箇所のみ表示)
  → Evidence Pack (crop/overlay/meta.json)
  → Spreadsheet Export (即時反映)
  → Human Feedback Log (教師データ蓄積)
```

### 上級オプション

| 機能 | 説明 |
|:--|:--|
| 構造化フィールド抽出 | 価格/日付/URL等を個別抽出し許容差ルール適用 |
| テーブル比較 | セル対応付け/行列挿入削除検知 |
| 広告ドメイン辞書 | ブランド/禁止表現/表記ルール |
| 重大度ルールエンジン | CRITICAL/MAJOR/MINOR + risk_reason |
| Evidence Pack | left/right/overlay crop + evidence.json |
| Human-in-the-loop | 教師データJSONL蓄積 |

### 主要ファイル

| ファイル | 説明 |
|:--|:--|
| `app/core/schemas.py` | Pydantic統一スキーマ |
| `app/core/fields_extract.py` | 構造化フィールド抽出 |
| `app/core/table_extract.py` | テーブルgrid化 |
| `app/core/rules_engine.py` | 重大度判定 |
| `app/config/rules.yaml` | 差分ルール定義 |
| `app/dictionary/` | 広告ドメイン辞書 |

### Spreadsheet列定義

```
run_id, page_left, page_right, element_kind, 
left_text_norm, right_text_norm, field_types,
diff_type, severity, risk_reason, score_total,
evidence_left_crop, evidence_right_crop, evidence_overlay_crop,
status, reviewer, comment
```

---

## Phase 8: Advanced Proofing OCR TODO Checklist (2026-01-11)

**ゴール:** 重大差分の取りこぼしゼロ / 監査性 / 運用速度 / 継続改善

### 0) Pipeline Core

| Task | File | Status |
|:--|:--|:--|
| Web Ingest (Playwright) | `app/pipeline/ingest_web.py` | ✅ Done |
| PDF Ingest (pdfminer + pypdfium2) | `app/pipeline/ingest_pdf.py` | ✅ Done |
| OCR Fallback for image PDFs | `app/pipeline/ingest_pdf.py` | ✅ Done |
| Text Normalize (全角半角/空白) | `app/pipeline/normalize.py` | ✅ Done |
| Alignment (ORB + Homography) | `app/pipeline/alignment.py` | ✅ Done |
| Matching (paragraph/table) | `app/pipeline/match.py` | ✅ Done |
| Diff Classify | `app/pipeline/diff.py` | ✅ Done |
| Orchestrator | `app/pipeline/orchestrator.py` | ✅ Done |
| Spreadsheet Export | `app/pipeline/spreadsheet_exporter.py` | ✅ Done |
| Dataset (Human-in-the-loop) | `app/pipeline/dataset.py` | ✅ Done |

### 1) 構造化フィールド抽出

| Task | File | Status |
|:--|:--|:--|
| Price extraction (¥/円/税込/税抜) | `app/core/fields_extract.py` | ✅ Done |
| Date extraction (和暦→西暦) | `app/core/fields_extract.py` | ✅ Done |
| URL/Email/Phone extraction | `app/core/fields_extract.py` | ✅ Done |
| SKU/Dimension extraction | `app/core/fields_extract.py` | ⬜ TODO |
| Field-level diff (許容差ルール) | `app/pipeline/diff.py` | ⬜ TODO |

### 2) テーブル比較

| Task | File | Status |
|:--|:--|:--|
| Table grid extraction | `app/pipeline/table_extract.py` | ✅ Done |
| Header detection | `app/pipeline/table_extract.py` | ✅ Done |
| Cell-level matching | `app/pipeline/match.py` | ⬜ TODO |
| Row/Column insert/delete detection | `app/pipeline/diff.py` | ⬜ TODO |

### 3) 広告ドメイン辞書

| Task | File | Status |
|:--|:--|:--|
| brand_terms.yaml | `app/dictionary/` | ✅ Done |
| legal_phrases.yaml | `app/dictionary/` | ⬜ TODO |
| product_skus.yaml | `app/dictionary/` | ⬜ TODO |
| kana_variants.yaml | `app/dictionary/` | ⬜ TODO |
| Dictionary lookup in normalize | `app/pipeline/normalize.py` | ⬜ TODO |

### 4) 重大度ルールエンジン

| Task | File | Status |
|:--|:--|:--|
| rules.yaml skeleton | `app/config/rules.yaml` | ✅ Done |
| Rules Engine implementation | `app/core/rules_engine.py` | ✅ Done |
| CRITICAL/MAJOR/MINOR classification | `app/core/rules_engine.py` | ✅ Done |
| risk_reason output | `app/pipeline/diff.py` | ⬜ TODO |

### 5) Evidence Pack

| Task | File | Status |
|:--|:--|:--|
| Evidence generator | `app/evidence/generate.py` | ✅ Done |
| Left/Right crop generation | `app/evidence/generate.py` | ✅ Done |
| Overlay crop generation | `app/evidence/generate.py` | ✅ Done |
| evidence.json metadata | `app/evidence/generate.py` | ✅ Done |

### 6) API Endpoints

| Task | Endpoint | Status |
|:--|:--|:--|
| Ingest Web | `POST /api/ingest/web` | ✅ Done |
| Ingest PDF | `POST /api/ingest/pdf` | ✅ Done |
| Run Proofing | `POST /api/proofing/run` | ✅ Done |
| List Issues | `GET /api/issues` | ✅ Done |
| Get Issue | `GET /api/issues/{id}` | ✅ Done |
| Update Issue | `PATCH /api/issues/{id}` | ✅ Done |
| Review Queue | `GET /api/queue` | ✅ Done |
| Match Override | `POST /api/overrides` | ✅ Done |
| Export Results | `GET /api/export/{run_id}` | ✅ Done |
| Save Feedback | `POST /api/dataset/feedback` | ✅ Done |

### 7) Frontend (React)

| Task | Status |
|:--|:--|
| Review Queue display | ✅ Done |
| Severity filtering | ✅ Done |
| Left/Right comparison view | ⬜ TODO |
| Overlay toggle (Onion Skin) | ⬜ TODO |
| Region highlight on click | ⬜ TODO |
| Match override UI | ⬜ TODO |
| Field editor | ⬜ TODO |
| Table editor | ⬜ TODO |

### 8) OCR精度向上 (MEKIKI Desktop)

| Task | File | Status |
|:--|:--|:--|
| ImagePreprocessor (4x Lanczos) | `app/core/image_preprocessor.py` | ✅ Done |
| Gamma correction (0.5) | `app/core/image_preprocessor.py` | ✅ Done |
| Otsu binarization | `app/core/image_preprocessor.py` | ✅ Done |
| Integrate preprocessor with engine_cloud | `app/core/engine_cloud.py` | ✅ Done |
| Web Region display fix | `advanced_comparison_view.py` | ✅ Done |
| Clustering Engine | `app/core/engine_clustering.py` | ✅ Done |
| Spatial Cluster Analyzer | `app/core/spatial_cluster_analyzer.py` | ✅ Done |

---

**Summary:**
- ✅ Done: 37 tasks
- ⬜ TODO: 9 tasks
- 進捗率: **80%**

**Priority TODO:**
1. Field-level diff (許容差)
2. Frontend Overlay View
3. Dictionary integration
4. Cell-level matching

---

## 📊 ハードコード値一覧 (2026-01-12)

### カテゴリ1: タイミング/遅延

| ファイル | 値 | 現在値 | 説明 |
|---------|-----|-------|------|
| `crawler.py:31` | `delay` | 0.5s | リクエスト間遅延 |
| `enhanced_scraper.py:32` | `scroll_delay` | 1.0s | スクロール待機 |
| `enhanced_scraper.py:166,168` | プレロール待機 | 0.8s | 画像読み込み |
| `ingest_web.py:97` | `wait_ms` | 2000ms | ページ待機 |
| `ingest_web.py:132` | `timeout` | 60000ms | ページタイムアウト |

### カテゴリ2: 数量制限

| ファイル | 値 | 現在値 | 説明 |
|---------|-----|-------|------|
| `llm_segmenter.py:214,228,229` | パラグラフ上限 | 20 | フォールバック最大数 |
| `llm_segmenter.py:298,301` | セグメント上限 | 30 | 共通セグメント最大数 |
| `unified_app.py:1089,1097` | ページ上限 | 10 | AI分析最大ページ |
| `crawler.py:29,30` | `max_pages/max_depth` | 50/5 | クロール上限 |
| `visual_analyzer.py:223` | ブロック上限 | 20 | 上位ブロック |

### カテゴリ3: 閾値/スコア

| ファイル | 値 | 現在値 | 説明 |
|---------|-----|-------|------|
| `match.py:48-52` | マッチング重み | 0.4/0.2/0.2/0.2/0.3 | α/β/γ/δ/閾値 |
| `llm_segmenter.py:248` | `min_length` | 8 | 共通文字最小長 |
| `ingest_pdf.py:42` | `confidence` | 1.0 | PDF信頼度固定 |

### カテゴリ4: 画像/レイアウト

| ファイル | 値 | 現在値 | 説明 |
|---------|-----|-------|------|
| `image_utils.py:16,17` | `max_width/height` | 800x600 | サムネイル |
| `ingest_web.py:32,33` | viewport | 1920x1080 | ビューポート |
| `match.py:260,261` | 正規化サイズ | 1920x1080 | レイアウト比較 |
| `llm_segmenter.py:117` | `max_dim` | 1024 | LLM画像最大 |
| `pdf_loader.py:17` | `dpi` | 300 | PDFレンダリング |

---

## 🔧 関数化/設定化提案

### 高優先度（精度に影響）

| 対象 | 提案 | 理由 |
|-----|------|------|
| `match.py` の重み係数 | `MatchConfig` クラス | マッチング精度調整が困難 |
| `min_length=8` | 設定ファイル化 | 言語/ドキュメント種別で最適値が異なる |
| パラグラフ上限20 | パラメータ化 | 長文ドキュメントで不足 |

### 中優先度（速度に影響）

| 対象 | 提案 | 理由 |
|-----|------|------|
| 遅延時間群 | `CrawlConfig` クラス | サイト特性で最適値が異なる |
| `max_pages/max_depth` | UIから設定可能に | ユーザー要件で変動 |
| タイムアウト値 | 環境変数化 | ネットワーク環境依存 |

### 低優先度（UI調整）

| 対象 | 提案 | 理由 |
|-----|------|------|
| サムネイルサイズ | CSS/設定 | 好みで変更可能に |
| 表示文字数制限`[:30]` | 定数化 | 一括変更を容易に |

---

## 📝 実装例

### MatchConfig クラス（提案）
```python
# app/config/match_config.py
@dataclass
class MatchConfig:
    alpha_text: float = 0.4
    beta_embed: float = 0.2
    gamma_layout: float = 0.2
    delta_visual: float = 0.2
    threshold: float = 0.3
    min_match_length: int = 8
    max_paragraphs: int = 20
```

---

## 🎯 Session: WithClaudeAgent (2026-01-13)

### セッション概要

**目標**: Claude Code 連携確立 + PDF パラグラフ検出改善

**結果**: ✅ 完了

### 成果物

| # | 項目 | ファイル |
|---|------|----------|
| 1 | **Claude Agent** | `app/agents/claude_agent.py` |
| 2 | **Multi-Model Advisor** | `app/agents/multi_model_advisor.py` |
| 3 | **Paragraph Detector** | `app/core/paragraph_detector.py` |
| 4 | **OCREngine 改善** | `app/core/ocr_engine.py` (認証自動検索) |
| 5 | **バックアップ** | `26_backups/WithClaudeAgent_20260113_103518/` |

### 確立したワークフロー

```
┌─────────────────────────────────────────────────────────────┐
│  Antigravity + Claude Opus 4                                │
│  🎯 主体: 計画立案、アーキテクチャ設計                      │
├─────────────────────────────────────────────────────────────┤
│  💡 Gemini (参考): 代替案、ユニーク視点                     │
│     → multi_model_advisor で取得・比較                      │
├─────────────────────────────────────────────────────────────┤
│  Claude Code (WSL)                                          │
│  🔧 実行: ファイル編集、タスククローズ                      │
└─────────────────────────────────────────────────────────────┘
```

### API キー設定

```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "..."
$env:GEMINI_API_KEY = "..."

# WSL
export ANTHROPIC_API_KEY="..."
export GEMINI_API_KEY="..."
```

### Claude Code 使用方法

```bash
# WSL で実行
cd /mnt/c/Users/raiko/OneDrive/Desktop/26/OCR
claude "タスクの指示をここに記述"
```

### 次回タスク

1. ~~PDF マルチカラム検出の改善~~ ✅ 完了
2. ~~MEKIKI GUI への ParagraphDetector 統合~~ ✅ 完了
3. Multi-Model Advisor を使った設計レビュー

---

## ✅ CHECKPOINT: AI分析モード成功 (2026-01-13)

### セッション概要

**目標**: AI分析モードでパラグラフ検出精度向上 + サムネイル・Sync Rate表示の維持

**結果**: **✅ 完全成功** - OCRモードとAI分析モードの両方が正常動作

### 成功した構成

| 処理 | Web側 | PDF側 |
|-----|------|------|
| テキスト抽出 | `engine_cloud.py` クラスタリング | PyMuPDF 埋め込みテキスト優先 |
| 座標系 | bbox + y_offset（縦連結対応） | DPIスケール (300/72≈4.166) + y_offset |
| 正規化 | `_normalize_japanese_text()` 日本語スペース削除 | - |
| 画像 | `stitch_images_vertically()` で縦連結 | 同左 |
| OCRフォールバック | - | 埋め込みテキストなし時に `engine_cloud.py` 使用 |

### バックアップ

```
backup_ParagraphSorted_SUCCESS_20260113/
├── advanced_comparison_view.py  (120,119 bytes)
├── engine_cloud.py              (21,910 bytes)
├── paragraph_detector.py        (20,883 bytes)
├── spreadsheet_panel.py         (14,146 bytes)
└── unified_app.py               (65,040 bytes)
```

### 復元コマンド

```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
Copy-Item "backup_ParagraphSorted_SUCCESS_20260113\unified_app.py" "app\gui\unified_app.py" -Force
Copy-Item "backup_ParagraphSorted_SUCCESS_20260113\engine_cloud.py" "app\core\engine_cloud.py" -Force
Copy-Item "backup_ParagraphSorted_SUCCESS_20260113\paragraph_detector.py" "app\core\paragraph_detector.py" -Force
Copy-Item "backup_ParagraphSorted_SUCCESS_20260113\spreadsheet_panel.py" "app\gui\panels\spreadsheet_panel.py" -Force
Copy-Item "backup_ParagraphSorted_SUCCESS_20260113\advanced_comparison_view.py" "app\gui\windows\advanced_comparison_view.py" -Force
```

### 技術的ポイント

#### 1. ハイブリッドアーキテクチャ
```
Web: engine_cloud.py クラスタリング（実績のあるMatch:70設定）
PDF: PyMuPDF page.get_text("dict") → 埋め込みテキスト優先
     ↓ フォールバック
     engine_cloud.py OCR
```

#### 2. 座標系の統一
```python
# PDF: PyMuPDF座標(72DPI) → 画像座標(300DPI)
DPI_SCALE = 300 / 72.0  # ≈ 4.166
scaled_bbox = [
    int(bbox[0] * DPI_SCALE),
    int(bbox[1] * DPI_SCALE + y_offset),
    int(bbox[2] * DPI_SCALE),
    int(bbox[3] * DPI_SCALE + y_offset)
]
```

#### 3. 画像の縦連結
```python
def stitch_images_vertically(images):
    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)
    stitched = Image.new('RGB', (max_width, total_height), (255, 255, 255))
    y_pos = 0
    for img in images:
        stitched.paste(img, (0, y_pos))
        y_pos += img.height
    return stitched
```

#### 4. 日本語テキスト正規化
```python
def _normalize_japanese_text(self, text: str) -> str:
    jp_char = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
    # 日本語文字同士の間のスペースを削除
    text = re.sub(f'({jp_char})[ 　]+({jp_char})', r'\1\2', text)
    return text
```

#### 5. view への画像設定（互換性維持）
```python
# 他の機能との互換性のため view に画像を設定
if stitched_web:
    view.web_image = stitched_web
if stitched_pdf:
    view.pdf_image = stitched_pdf
```

### モード比較

| 項目 | OCR実行モード | AI分析モード |
|-----|-------------|-------------|
| ボタン | 「OCR実行」 | 「🤖 AI分析モード」 |
| Web処理 | engine_cloud.py | engine_cloud.py |
| PDF処理 | engine_cloud.py | PyMuPDF埋め込み優先 |
| 速度 | 高速 | 中速（PDF解析あり） |
| 精度 | 座標ベース | セマンティック＋座標 |
| サムネイル | ✅ | ✅ |
| Sync Rate | ✅ | ✅ |

### 重要な教訓

> **画像とIDの両方が必要**
>
> サムネイル表示には `view.web_image` / `view.pdf_image` の設定が必須。
> また、`ParaSyncPair` と `ParaRegion` の `area_code` / `web_id` / `pdf_id` が
> 一致しないとマッピングに失敗する。

---

## ✅ CHECKPOINT: Case1 - State Management Fix (2026-01-13)

### セッション概要

**問題**: AI分析モードを2回目に実行すると画像・テキスト・シンクロ率が消失する

**原因**:
1. 状態管理の不備 - リストがappendされ続けてインデックスがズレる
2. PDF埋め込みテキスト使用時に画像がレンダリングされない

**結果**: **✅ 修正完了** - 何度実行しても正常に動作

### 修正内容

#### 1. 状態初期化の追加 (unified_app.py L1095-1112)

```python
# ★★★ 状態初期化（State Management Fix）★★★
# 結果データのみクリア（入力画像は保持）
view.sync_pairs = []
view.web_regions = []
view.pdf_regions = []
# Note: view.web_image/pdf_image は入力ソースのため保持

# spreadsheet_panelの結果状態のみクリア
if hasattr(view, 'spreadsheet_panel'):
    view.spreadsheet_panel.sync_pairs = []
    view.spreadsheet_panel.web_map = {}
    view.spreadsheet_panel.pdf_map = {}
    # サムネイル参照もクリア（GC対策）
    if hasattr(view.spreadsheet_panel, '_thumbnail_refs'):
        view.spreadsheet_panel._thumbnail_refs = []
```

#### 2. PDF画像レンダリング追加 (unified_app.py L1212-1219)

```python
# ★ PDFページを画像としてレンダリング（サムネイル用）
# DPI_SCALE (300/72 ≈ 4.17) に合わせてレンダリング
mat = fitz.Matrix(DPI_SCALE, DPI_SCALE)
pix = page.get_pixmap(matrix=mat)
img_data = pix.tobytes("png")
page_img = Image.open(io.BytesIO(img_data))
pdf_images.append(page_img)
```

#### 3. 重複初期化の削除

- 旧L1163-1164の `web_paragraphs = []` / `pdf_paragraphs = []` を削除
- 関数冒頭で一度だけ初期化するように統一

### バックアップ

```
backup_Case1_StateManagementFix_20260113/
├── advanced_comparison_view.py  (123KB)
├── comparison_mixins/
├── paragraph_detector.py        (21KB)
├── spreadsheet_panel.py         (14KB)
└── unified_app.py               (67KB)
```

### 復元コマンド

```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
Copy-Item "backup_Case1_StateManagementFix_20260113\unified_app.py" "app\gui\unified_app.py" -Force
Copy-Item "backup_Case1_StateManagementFix_20260113\spreadsheet_panel.py" "app\gui\panels\spreadsheet_panel.py" -Force
Copy-Item "backup_Case1_StateManagementFix_20260113\advanced_comparison_view.py" "app\gui\windows\advanced_comparison_view.py" -Force
```

### 技術的ポイント

#### 状態管理の原則

```
┌────────────────────────────────────────────────────────────┐
│ 関数開始時                                                  │
│ ├─ 結果データをクリア (sync_pairs, regions, thumbnail_refs) │
│ └─ 入力データは保持 (web_pages, pdf_pages, source images)  │
├────────────────────────────────────────────────────────────┤
│ 処理中                                                      │
│ └─ ローカル変数に新規データを構築                           │
├────────────────────────────────────────────────────────────┤
│ 関数終了時                                                  │
│ └─ 新しいデータでviewを更新                                 │
└────────────────────────────────────────────────────────────┘
```

#### PDF座標と画像の整合性

| 項目 | 値 |
|-----|-----|
| PDF座標系 | 72 DPI (PyMuPDF標準) |
| 画像レンダリング | 300 DPI |
| スケール係数 | `DPI_SCALE = 300/72 ≈ 4.166` |
| bbox変換 | `scaled_bbox = bbox * DPI_SCALE + y_offset` |
| 画像レンダリング | `fitz.Matrix(DPI_SCALE, DPI_SCALE)` |

### 重要な教訓

> **状態管理は関数冒頭で一度だけ**
>
> 複数回実行される可能性がある関数では、必ず冒頭で結果データを初期化する。
> ただし、入力データ（画像ソース等）は初期化してはならない。

> **PDF座標と画像DPIは必ず一致させる**
>
> PyMuPDFのbboxスケーリングと`get_pixmap()`のMatrixは同じ係数を使用する。
> 不一致があるとサムネイルの切り出し位置がズレる。

---

## 🔧 Case2 - AI解析後の画像消失問題 (2026-01-13 → 2026-01-14 修正適用)

### セッション概要

**問題**: OCR実行後は画像・ユニークナンバーが正常に表示されるが、AI解析実行後に消える

**状態**: 🔧 修正適用済み（要テスト）

### 症状

```
1. OCR実行 → 画像 + ユニークナンバー + 選択範囲 ✅ 正常
2. AI解析実行 → 画像 + ユニークナンバー + 選択範囲 ❌ 消失
```

コンソール上は描画成功のログが出力されるが、実際の画面には表示されない。

### 根本原因（特定済み）

Configureイベントのデバウンス処理が`_display_image`のみを呼び出し、`_redraw_regions`を再呼び出ししていなかった。
AI分析モードではタブ切り替えが複数回発生し、Configureイベントがデバウンス後（100ms）に発火。
この時、画像のみ再描画されてリージョンが消失していた。

### 調査項目

| # | 項目 | 状態 |
|---|------|------|
| 1 | Canvas Configure イベント干渉 | ✅ フラグ追加済み |
| 2 | スクロール位置リセット | ✅ 追加済み |
| 3 | タブ切り替えタイミング | ✅ 修正済み |
| 4 | キャンバスアイテム確認 | ✅ デバッグ追加済み |
| 5 | **Configure後のリージョン再描画** | ✅ **修正適用** |
| 6 | **描画完了後のガード期間** | ✅ **修正適用** |

### 修正内容 (2026-01-14 追加)

#### 5. Configureイベントハンドラ改善 (advanced_comparison_view.py L673-697)

```python
def _on_web_canvas_configure(self, event):
    if getattr(self, '_display_in_progress', False):
        return
    if hasattr(self, 'web_image') and self.web_image and event.width > 50:
        if hasattr(self, '_web_resize_job') and self._web_resize_job:
            self.after_cancel(self._web_resize_job)
        # ★ 画像描画後にリージョンも再描画（Case2修正）
        def _redisplay_web():
            self._display_image(self.web_canvas, self.web_image)
            if self.web_regions:
                self._redraw_regions()
        self._web_resize_job = self.after(100, _redisplay_web)
```

#### 6. AI分析モード描画完了後のガード期間 (unified_app.py L1567-1592)

```python
# 描画中フラグを設定してConfigureイベント干渉を防止
view._display_in_progress = True

# タブ切り替え処理...

# 300ms後に描画中フラグをクリア（Configureデバウンス100msより長く）
def _clear_display_flag():
    view._display_in_progress = False
view.after(300, _clear_display_flag)
```

---

### 修正内容 (2026-01-13 既存)

#### 1. 描画中フラグ追加 (advanced_comparison_view.py)

```python
# L78: 描画中フラグ（configureイベント干渉防止）
self._display_in_progress: bool = False

# _display_image() 内で設定/クリア
self._display_in_progress = True  # 開始時
# ... 描画処理 ...
self._display_in_progress = False  # 終了時

# configure ハンドラでチェック
def _on_web_canvas_configure(self, event):
    if getattr(self, '_display_in_progress', False):
        return  # 描画中はスキップ
```

#### 2. スクロール位置リセット (advanced_comparison_view.py L1059-1061)

```python
# スクロールを先頭にリセット
canvas.yview_moveto(0)
canvas.xview_moveto(0)
```

#### 3. タブ切り替えタイミング修正 (unified_app.py L1518-1551)

```python
# 描画前にタブを切り替え
view.view_tabs.set("Web Source")
view.update_idletasks()
view.update()

# Web描画
view._display_image(view.web_canvas, stitched_web)

# PDFタブに切り替え
view.view_tabs.set("PDF Source")
view.update_idletasks()

# PDF描画
view._display_image(view.pdf_canvas, stitched_pdf)

# 最後にWebタブに戻す
view.view_tabs.set("Web Source")
```

#### 4. 遅延デバッグ出力 (unified_app.py L1606-1628)

```python
# 500ms後にキャンバス状態を再確認
def delayed_canvas_check():
    if view.web_canvas:
        all_items = view.web_canvas.find_all()
        image_items = view.web_canvas.find_withtag("image")
        region_items = view.web_canvas.find_withtag("region")
        scroll_y = view.web_canvas.yview()
        scrollregion = view.web_canvas.cget("scrollregion")
        print(f"[AI Mode +500ms] web_canvas: total={len(all_items)}, images={len(image_items)}, regions={len(region_items)}")
        print(f"[AI Mode +500ms] web_canvas scroll: yview={scroll_y}")
        print(f"[AI Mode +500ms] web_canvas scrollregion={scrollregion}")
view.after(500, delayed_canvas_check)
```

### 次回確認事項

1. コンソールのデバッグ出力を確認
   - `[Configure] Web resize triggered` が出ているか
   - `[AI Mode +500ms] web_canvas: total=X` のアイテム数
   - `scrollregion` の値が正常か

2. 可能性のある原因
   - Configure イベントが描画後に発火して画像を再描画している可能性
   - スプレッドシートパネルの更新が何かを上書きしている可能性
   - PhotoImage参照がGCされている可能性

### バックアップ

```
backup_Case2_ImageDisplayDebug_20260113/
├── advanced_comparison_view.py
├── unified_app.py
└── spreadsheet_panel.py
```

### 復元コマンド

```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
Copy-Item "backup_Case2_ImageDisplayDebug_20260113\unified_app.py" "app\gui\unified_app.py" -Force
Copy-Item "backup_Case2_ImageDisplayDebug_20260113\advanced_comparison_view.py" "app\gui\windows\advanced_comparison_view.py" -Force
```

---


---

## Phase 2.0: Semantic Matching (2026-01-23 �v��)

### �w�i
Phase 1.9 ������A�ȉ��̖�肪�c��:
- �Ђ炪�Ȓ����i���r�܂ށj�̌딻��
- �L���X�y�[�X�ɂ�� false negative
- ����e�L�X�g���قȂ镶�͂Ƃ��ĔF�������

### ��ċ@�\

#### P0: �Ђ炪�Ȓ������r�Ή�
- �Ђ炪�ȗD�ʃe�L�X�g���m
- ���r�����m�[�}���C�U�[: �����i�ӂ肪�ȁj  ����
- �V���N���p���O���t�F��

#### P1: �����F���}�b�`���O
- Gemini �������ފ�
- �Z���n���Z�O�����^�[
- �ŏ��P��P�ʂ̓��I����

---

##  �����L�^ (2026-01-23)

**���**: Skills�������s�ɂ��R�A�t�@�C���j��
**�Ώ�**: OCR_backup_20260121_AgentOpsPrep ���畜��
**�����t�@�C��**: advanced_comparison_view.py (193KB)
**���**:  �A�v�����퓮��A61% sync rate�m�F

---
