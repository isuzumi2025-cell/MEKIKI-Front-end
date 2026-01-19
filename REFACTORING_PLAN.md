# リファクタリング計画書

## アーキテクチャ概要

### 新しい2画面構成

```
起動
  ↓
┌─────────────────────────────────────┐
│ Dashboard (Matrix) 画面             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│ ┌─────────────┐  ┌─────────────┐  │
│ │ Web Pages   │  │ PDF Pages   │  │
│ │ ├ URL 1     │  │ ├ Page 1    │  │
│ │ ├ URL 2 ←→  │  │ ├ Page 2    │  │
│ │ └ URL 3     │  │ └ Page 3    │  │
│ └─────────────┘  └─────────────┘  │
│                                     │
│ [Auto-Match] [Inspect Selected]    │
└─────────────────────────────────────┘
         ↓ (Inspectクリック)
┌─────────────────────────────────────┐
│ Inspector (Comparison) 画面         │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│ ┌────────────┬────────────┐        │
│ │ Web Canvas │ PDF Canvas │        │
│ │  [画像]    │  [画像]    │ ← 同期スクロール
│ │            │            │        │
│ └────────────┴────────────┘        │
│ [Onion Skin] [Export] [Back]       │
└─────────────────────────────────────┘
```

## Phase 1: Backend強化

### app/core/scraper.py
- 遅延読み込み対応（Lazy Loading）
- ページ下部までスクロールしてからスクリーンショット
- 複数解像度対応（サムネイル + フルサイズ）

### app/core/pairing_manager.py (NEW)
- WebとPDFのペアリング情報を管理
- 自動マッチング結果の保存
- ペアの追加・削除・編集

## Phase 2: Dashboard画面

### app/gui/dashboard.py (NEW)
- 左右2列のリスト表示
- サムネイル + テキスト表示
- ドラッグ&ドロップでペアリング
- Auto-Matchボタン
- 選択したペアでInspector起動

### app/gui/thumbnail_list.py (NEW)
- サムネイル付きスクロール可能リスト
- チェックボックスで選択
- ソート・フィルター機能

## Phase 3: Inspector画面

### app/gui/inspector.py (NEW)
- 左右分割のPanedWindow
- 同期スクロール機能
- オニオンスキンモード切替
- エクスポート機能

### app/gui/sync_scroll_canvas.py (NEW)
- tkinter.Canvasベース
- マウスホイール・スクロールバー同期
- ズーム機能
- 画像の動的読み込み

## データフロー

```
User Input
    ↓
Dashboard
    ├→ WebCrawler → Web画像リスト
    ├→ PDFLoader → PDF画像リスト
    └→ Auto-Match → ペアリング結果
          ↓
    PairingManager (保存)
          ↓
    Inspector (選択されたペア)
          ├→ SyncScrollCanvas (Web)
          └→ SyncScrollCanvas (PDF)
```

## クラス設計

### Dashboard
- `__init__(parent)`: 初期化
- `load_web_pages()`: Web画像を読み込み
- `load_pdf_pages()`: PDF画像を読み込み
- `auto_match()`: 自動マッチング実行
- `create_pairing()`: 手動ペアリング
- `open_inspector()`: Inspector起動

### Inspector
- `__init__(parent, web_page, pdf_page)`: 初期化
- `setup_sync_scroll()`: 同期スクロール設定
- `toggle_onion_skin()`: オニオンスキン切替
- `export_comparison()`: 比較結果エクスポート

### SyncScrollCanvas
- `__init__(parent, image)`: 初期化
- `bind_scroll_partner()`: スクロールパートナー設定
- `on_scroll()`: スクロールイベント処理
- `sync_to_partner()`: パートナーと同期

### PairingManager
- `add_pair(web_id, pdf_id)`: ペア追加
- `remove_pair(pair_id)`: ペア削除
- `get_pairs()`: 全ペア取得
- `auto_match(web_pages, pdf_pages)`: 自動マッチング

## 実装順序

1. ✅ Phase 1: Scraper強化（Lazy Loading）
2. ✅ Phase 1: PairingManager作成
3. ✅ Phase 2: ThumbnailList作成
4. ✅ Phase 2: Dashboard作成
5. ✅ Phase 3: SyncScrollCanvas作成
6. ✅ Phase 3: Inspector作成
7. ✅ 統合テスト
8. ✅ UI/UX調整

