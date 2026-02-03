# MEKIKI Architecture v12.4.6 - 依存関係図

**最終更新**: 2026-01-30
**目的**: 全モジュールの依存関係を可視化し、Phase 44クラスの複雑問題の調査起点とする

---

## システム全体構成

```mermaid
graph TB
    subgraph "🖥️ Entry Points"
        MAIN[main.py]
        MAIN_V2[main_v2.py]
        RUN_UNIFIED[run_unified.py]
    end

    subgraph "🎨 GUI Layer"
        UNIFIED[unified_app.py<br/>Legacy UI Hub]
        MAIN_WIN_V2[main_window_v2.py<br/>Genius Edition]
        ADV_VIEW[advanced_comparison_view.py<br/>⭐ Phase 44 Core]
        SPREAD_PANEL[spreadsheet_panel.py<br/>Live Comparison Sheet]
    end

    subgraph "🔬 OCR & Analysis"
        HYBRID_OCR[hybrid_ocr.py<br/>Vision+Gemini Fusion]
        ENGINE_CLOUD[engine_cloud.py<br/>🔴 Match:70 Strict Clustering]
        PARA_DETECTOR[paragraph_detector.py<br/>Multi-column Layout]
        SYNC_MATCHER[sync_matcher.py<br/>🔴 Similarity 0.5]
        PARA_MATCHER[paragraph_matcher.py<br/>🔴 8-char LCS Anchor]
    end

    subgraph "📄 PDF/Web Ingestion"
        PDF_LOADER[pdf_loader.py]
        WEB_CRAWLER[crawler.py]
        ENHANCED_SCRAPER[enhanced_scraper.py<br/>Ultrathink Stitching]
    end

    subgraph "🧩 SDK Modules"
        SIMILARITY[similarity/embedding_search.py]
        CLAWDBOT[notification/clawdbot_client.py]
        LLMCLIENT[llm/llm_client.py<br/>Gemini 2.0 Flash]
    end

    subgraph "💾 Data Models"
        PAGE_DATA[page_data.py]
        SYNC_PAIR[SyncPair dataclass]
        PARA_REGION[ParaRegion object]
    end

    %% Critical Path: Phase 44
    MAIN --> UNIFIED
    UNIFIED --> ADV_VIEW
    ADV_VIEW --> SPREAD_PANEL
    SPREAD_PANEL -.->|"⚠️ _on_spreadsheet_row_select"| ADV_VIEW
    ADV_VIEW -.->|"🔥 _highlight_with_page_conversion"| ADV_VIEW
    
    %% OCR Dependencies
    UNIFIED --> HYBRID_OCR
    HYBRID_OCR --> ENGINE_CLOUD
    HYBRID_OCR --> LLMCLIENT
    ENGINE_CLOUD -.->|"🔴 Core File"| PARA_MATCHER
    PARA_MATCHER -.->|"🔴 Core File"| SYNC_MATCHER

    %% Data Flow
    WEB_CRAWLER --> ENHANCED_SCRAPER
    ENHANCED_SCRAPER --> PAGE_DATA
    PDF_LOADER --> PAGE_DATA
    PAGE_DATA --> ADV_VIEW

    %% Analysis Pipeline
    ADV_VIEW --> PARA_DETECTOR
    PARA_DETECTOR --> SYNC_MATCHER
    SYNC_MATCHER --> SYNC_PAIR
    SYNC_PAIR --> SPREAD_PANEL

    classDef critical fill:#ff6b6b,stroke:#c92a2a,stroke-width:3px
    classDef phase44 fill:#ffd43b,stroke:#f59f00,stroke-width:3px
    
    class ENGINE_CLOUD,SYNC_MATCHER,PARA_MATCHER critical
    class ADV_VIEW,SPREAD_PANEL phase44
```

---

## 🔴 Core Files Protection Policy

**以下のファイルは Match:70 検証なしに変更禁止**:

| ファイル | 責務 | 最終安定版 |
|----------|------|-----------|
| `engine_cloud.py` | OCR Clustering (Overlap 0.6, Gap 2.5x) | Match:70 Baseline |
| `sync_matcher.py` | Similarity 0.5, Min 8-char LCS | Match:70 Baseline |
| `paragraph_matcher.py` | 8-char Anchor Matching | Match:70 Baseline |

**変更時の必須手順**:

1. タイムスタンプ付きバックアップ作成
2. 変更後即座にOCRテスト実行
3. Match数が低下した場合は即座にロールバック

---

## 🔥 Phase 44: Canvas画像表示問題

### 問題経路

```mermaid
sequenceDiagram
    participant User
    participant SpreadsheetPanel
    participant AdvancedComparisonView
    participant Canvas

    User->>SpreadsheetPanel: サムネイルクリック
    SpreadsheetPanel->>AdvancedComparisonView: _on_spreadsheet_row_select(pair)
    AdvancedComparisonView->>AdvancedComparisonView: _highlight_with_page_conversion(side, pair)
    AdvancedComparisonView->>Canvas: _display_image(page_idx)
    Canvas-->>AdvancedComparisonView: 画像表示（PhotoImage参照）
    AdvancedComparisonView->>Canvas: create_rectangle() 領域枠描画
    
    Note over Canvas: ⚠️ 問題: 領域枠のみ表示、画像空白
```

### 推定原因

1. **PhotoImage GC問題**: `self._current_image` 参照が保持されていない
2. **Z-order不一致**: 画像が領域枠の下層に隠れている
3. **座標変換エラー**: `transform.src_rect_to_view()` が画面外座標を返している

---

## 🧩 モジュール責務マトリクス

| レイヤー | モジュール | 入力 | 出力 | 依存先 |
|----------|-----------|------|------|--------|
| **Entry** | `unified_app.py` | ユーザー操作 | GUI状態遷移 | `advanced_comparison_view.py` |
| **View** | `advanced_comparison_view.py` | PageData, SyncPair | Canvas描画 | `spreadsheet_panel.py`, `hybrid_ocr.py` |
| **Sheet** | `spreadsheet_panel.py` | SyncPair[] | 行セル | Callback to View |
| **OCR** | `hybrid_ocr.py` | PIL.Image | DetectedArea[] | `engine_cloud.py`, `llm_client.py` |
| **Cluster** | `engine_cloud.py` | DetectedArea[] | Paragraph[] | - |
| **Match** | `sync_matcher.py` | Paragraph[], Paragraph[] | SyncPair[] | - |
| **SDK** | `llm_client.py` | Prompt, Image | JSON Response | Gemini API |

---

## 📦 バックアップ戦略

### Tier 1: Gold Standard

- `OCR_MEKIKI_v1_Final_20260117` - Legacy UI完全版
- `OCR_backup_20260128_224817` - Phase 44直前の安全版

### Tier 2: Feature Baseline

- `OCR_GoogleVisionAPI_AImode_Backup_20260114` - AI Analysis Mode基準

### Tier 3: Emergency Restore

最新の動作確認済みバックアップ（`backup_catalog.md`参照）

---

## 🔍 調査起点

**Phase 44クラスの問題発生時**:

1. この `architecture.md` で**データフロー**を確認
2. **🔥マーク箇所**のログを優先調査
3. **🔴Core Files**は最終手段（バックアップ必須）

**ファイル特定後**:

1. `Vault/50_Logs/incidents/` で類似事例検索
2. `backup_catalog.md` で関連モジュールの安定版特定
3. 4フェーズ調査プロセス適用

---

## 参照

- [MEKIKI Operations Skill](../.agent/skills/mekiki_ops/SKILL.md)
- [Autonomous Behavior Framework](./Vault/00_Runbook/autonomous_behavior_framework.md)
- [Backup Catalog](./Vault/10_Projects/mekiki/backup_catalog.md)
