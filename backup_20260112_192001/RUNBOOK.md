# MEKIKI Proofing System - Runbook

**Last Updated**: 2026-01-12  
**Backup**: `OCR_backup_20260111_002213`

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

