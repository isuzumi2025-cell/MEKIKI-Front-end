# ➕ 新規プロジェクト作成機能 - 実装完了

## ✅ 実装内容

URLとPDFを指定して、Webクロール・PDF読込・OCR・マッチングを一括実行する「新規プロジェクト作成」機能が完成しました。

---

## 📦 作成されたファイル

### 1. **`app/gui/dialogs/project_dialog.py`** (約500行)
新規プロジェクト作成ダイアログ

**主要機能:**
- ✅ モーダルダイアログ（`CTkToplevel`）
- ✅ **Web設定**: URL入力、深さスライダー、最大ページ数
- ✅ **PDF設定**: ファイル/フォルダ選択
- ✅ **詳細設定**: OCR有効化、類似度閾値
- ✅ 入力検証
- ✅ スクロール可能なUI
- ✅ コールバック機能

### 2. **`app/gui/navigation.py`** (更新)
ナビゲーションパネル

**追加機能:**
- ✅ 「➕ 新規プロジェクト」ボタン（最上部、オレンジ色）
- ✅ コールバック統合

### 3. **`app/gui/main_window_v2.py`** (更新)
メインウィンドウ

**追加機能:**
- ✅ `new_project()`: ダイアログ起動
- ✅ `start_analysis()`: 分析プロセス統合
- ✅ `_show_loading_screen()`: ローディング画面
- ✅ `_crawl_web_pages()`: Webクロール実行
- ✅ `_load_pdf_pages()`: PDF読込実行
- ✅ `_on_analysis_complete()`: 完了処理
- ✅ `_on_analysis_error()`: エラーハンドリング
- ✅ バックグラウンド処理（threading）

### 4. **ドキュメント**
- `docs/NEW_PROJECT_FEATURE.md` - 完全な使用ガイド
- `test_new_project.py` - テストスクリプト

---

## 🎨 UI構成

### プロジェクトダイアログ（700x650px）

```
┌──────────────────────────────────────────────┐
│ ➕ 新規プロジェクト作成                       │
├──────────────────────────────────────────────┤
│ 🌐 Web設定                                   │
│   対象URL: [https://example.com          ]   │
│   深さ:    [=====●=====] 2階層              │
│   最大:    [10] ページ                       │
│                                              │
│ ──────────────────────────────────────────   │
│                                              │
│ 📁 PDF設定                                   │
│   ファイル: [未選択]              [📂 選択]  │
│   フォルダ: [未選択]              [📂 選択]  │
│                                              │
│ ──────────────────────────────────────────   │
│                                              │
│ ⚙️ 詳細設定                                  │
│   [✓] Google Cloud Vision API 使用          │
│   閾値: [=====●=====] 30%                   │
│                                              │
├──────────────────────────────────────────────┤
│  [✖ キャンセル]            [🚀 分析開始]    │
└──────────────────────────────────────────────┘
```

### ローディング画面

```
┌──────────────────────────────────┐
│                                  │
│        🔄 処理中...              │
│                                  │
│   🌐 Webページをクロール中...   │
│                                  │
│   ▓▓▓▓▓▓▓▓▓░░░░░░░░            │
│                                  │
└──────────────────────────────────┘
```

---

## 🚀 使用フロー

### 1. ダイアログ起動

```
ナビゲーション
  ↓ クリック
「➕ 新規プロジェクト」
  ↓
ProjectDialog 表示
```

### 2. 設定入力

```
Web設定:
  - URL: https://example.com
  - 深さ: 2階層
  - 最大: 10ページ

PDF設定:
  - ファイル: document.pdf

詳細設定:
  - OCR: 有効
  - 閾値: 30%
```

### 3. 分析実行

```
「🚀 分析開始」クリック
  ↓
バックグラウンド処理開始
  ↓
┌─────────────────────────┐
│ 1. 🌐 Webクロール        │
│ 2. 📁 PDF読込           │
│ 3. 🔍 OCR実行 (オプション)│
│ 4. ⚡ マッチング         │
└─────────────────────────┘
  ↓
完了ダイアログ表示
  ↓
全体マップ（MacroView）表示
```

---

## 🔧 技術実装

### データフロー

```python
ProjectDialog
  ↓ on_start callback
MainWindow.new_project()
  ↓
MainWindow.start_analysis(config)
  ↓ threading.Thread
  ├─ _crawl_web_pages()      # EnhancedScraper
  ├─ _load_pdf_pages()       # PDFLoader
  ├─ OCR実行                 # OCREngine (オプション)
  └─ compute_auto_matches()  # ContentAnalyzer
  ↓
MacroView.load_from_analyzer()
```

### バックグラウンド処理

```python
def start_analysis(self, config):
    # ローディング画面表示
    self._show_loading_screen()
    
    # 別スレッドで実行
    def _run_analysis():
        try:
            # 処理...
            self.after(0, completion_callback)
        except Exception as e:
            self.after(0, error_callback)
    
    threading.Thread(target=_run_analysis, daemon=True).start()
```

---

## 📊 設定パラメータ

| 項目 | 型 | デフォルト | 範囲/制限 |
|------|-----|-----------|----------|
| URL | str | - | http/https必須 |
| 深さ | int | 2 | 1-5階層 |
| 最大ページ | int | 10 | 1- |
| PDFファイル | str | None | .pdf |
| PDFフォルダ | str | None | - |
| OCR使用 | bool | True | - |
| 閾値 | float | 0.3 | 0.1-0.9 |

---

## 🎯 主要機能

### 入力検証

```python
def _validate_inputs(self) -> bool:
    # URL検証
    if not url or not url.startswith("http"):
        messagebox.showwarning("入力エラー", "...")
        return False
    
    # PDF検証
    if not pdf_file and not pdf_folder:
        messagebox.showwarning("入力エラー", "...")
        return False
    
    return True
```

### リアルタイムフィードバック

- **スライダー**: 値が変更されると即座にラベル更新
  ```python
  def _on_depth_change(self, value):
      depth = int(value)
      self.depth_label.configure(text=f"{depth}階層")
  ```

- **ファイル選択**: 選択後に即座にパス表示
  ```python
  file_name = Path(file_path).name
  self.pdf_path_label.configure(text=file_name, text_color="white")
  ```

### エラーハンドリング

```python
try:
    # 分析処理...
except Exception as e:
    print(f"❌ エラー: {str(e)}")
    messagebox.showerror("エラー", f"...")
    self._show_welcome()  # ウェルカム画面に戻る
```

---

## 🎨 UI設計のポイント

### 1. **色分け**
- 新規プロジェクトボタン: `#FF6F00`（オレンジ）← 目立つ
- 実行ボタン: `#4CAF50`（緑）← 肯定的
- キャンセルボタン: `gray`（灰色）← 控えめ

### 2. **スクロール可能**
- `CTkScrollableFrame`使用
- 小さい画面でも全項目にアクセス可能

### 3. **モーダル**
- `transient()` + `grab_set()`
- 入力完了まで他の操作をブロック

### 4. **中央配置**
- 画面中央に自動配置
  ```python
  x = (screen_width // 2) - (dialog_width // 2)
  y = (screen_height // 2) - (dialog_height // 2)
  self.geometry(f"+{x}+{y}")
  ```

---

## 🧪 テスト

### テストスクリプト

```bash
python test_new_project.py
```

**実行内容:**
1. MainWindow V2を起動
2. 「➕ 新規プロジェクト」ボタンをクリック
3. ダイアログで設定を入力
4. 分析実行をテスト

---

## 📈 実装統計

| ファイル | 行数 | 機能 |
|---------|------|------|
| `project_dialog.py` | ~500 | ダイアログUI |
| `navigation.py` | +10 | ボタン追加 |
| `main_window_v2.py` | +200 | 分析統合 |
| **合計** | **~710** | **3ファイル** |

---

## 🔜 今後の実装

### 短期
- [ ] PDFフォルダの再帰的読み込み完全実装
- [ ] EnhancedScraperとの完全統合
- [ ] OCR結果の詳細表示

### 中期
- [ ] クロール進捗のリアルタイム表示
- [ ] 設定のプリセット保存/読込
- [ ] クロールのキャンセル機能

### 長期
- [ ] クロール結果のプレビュー画面
- [ ] 詳細なログビューア
- [ ] エラーリカバリー機能

---

## 💡 使用例

### コード例

```python
# アプリ起動
from app.gui.main_window_v2 import MainWindow
app = MainWindow()
app.mainloop()

# 操作フロー:
# 1. 「➕ 新規プロジェクト」クリック
# 2. URL入力: https://example.com
# 3. PDF選択: document.pdf
# 4. 「🚀 分析開始」クリック
# 5. 処理完了後、全体マップ表示
```

### 設定例

```python
config = {
    "url": "https://www.portcafe.net/demo/jrkyushu/jisha-meguri/",
    "depth": 2,
    "max_pages": 10,
    "pdf_file": "C:/Documents/sample.pdf",
    "pdf_folder": None,
    "use_ocr": True,
    "threshold": 0.3
}
```

---

## 🎊 達成した目標

| 要件 | 状態 | 実装 |
|------|------|------|
| 入力ダイアログ | ✅ | ProjectDialog完成 |
| ナビゲーション統合 | ✅ | ボタン追加完了 |
| 分析プロセス統合 | ✅ | start_analysis実装 |
| ローディング画面 | ✅ | _show_loading_screen実装 |
| バックグラウンド処理 | ✅ | threading使用 |
| エラーハンドリング | ✅ | try-except完備 |
| 入力検証 | ✅ | _validate_inputs実装 |
| 完了通知 | ✅ | messagebox + 自動遷移 |

---

## 🌟 技術ハイライト

### 1. **モーダルダイアログ**
```python
self.transient(master)  # 親ウィンドウに紐付け
self.grab_set()         # 他の操作をブロック
```

### 2. **非同期処理**
```python
def start_analysis(config):
    def _run_analysis():
        # 重い処理...
        self.after(0, lambda: callback())
    
    threading.Thread(target=_run_analysis, daemon=True).start()
```

### 3. **リアルタイム更新**
```python
self.after(0, lambda: self._update_loading_message("処理中..."))
```

### 4. **入力検証**
```python
if not url.startswith("http"):
    messagebox.showwarning("エラー", "...")
    return False
```

---

**🎉 新規プロジェクト作成機能の実装完了！**

直感的なUIで、URLとPDFを指定するだけで、複雑な分析プロセスを自動実行できるようになりました。
バックグラウンド処理により、GUIがフリーズすることなく、快適な操作体験を提供します。

