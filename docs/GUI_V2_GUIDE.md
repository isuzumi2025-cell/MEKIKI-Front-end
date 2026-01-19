# 🎨 GUI V2 実装ガイド

## 概要

全体マップ（Macro View）と詳細比較（Micro View）を備えた新しいGUIアーキテクチャです。

---

## 📁 ファイル構成

```
app/gui/
├── main_window_v2.py    # メインウィンドウ（新版）
├── macro_view.py        # 全体マップビュー ✨
├── micro_view.py        # 詳細比較ビュー ✨
└── navigation.py        # ナビゲーションパネル（更新）
```

---

## 🗺️ Macro View（全体マップ）

### 機能

- **Canvasベースの描画**: Web/PDFのサムネイルをグリッド配置
- **マッチング線**: WebとPDFのペアをベジェ曲線で視覚化
- **バウンディングボックス表示**: 各エリアの検出範囲を小さく表示
- **類似度カラーコード**:
  - 🟢 緑: 70%以上
  - 🟡 黄: 40-70%
  - 🔴 赤: 40%未満
- **画像検索エリア**: ドラッグ&ドロップ対応（実装予定）

### 使い方

```python
from app.gui.macro_view import MacroView
from app.core.analyzer import ContentAnalyzer

# Analyzerを準備
analyzer = ContentAnalyzer()
# ... データを追加 ...

# MacroViewを作成
macro = MacroView(
    parent,
    analyzer=analyzer,
    on_detail_click=callback
)

# データを読み込んで描画
macro.load_from_analyzer()
```

### UI構成

```
┌─────────────────────────────────────────────┐
│ 🗺️ 全体マッピングビュー     [再描画] [検索] │
├─────────────────────────────────────────────┤
│                                             │
│  🌐 Web Pages          📁 PDF Pages         │
│  ┌─────┐ ┌─────┐      ┌─────┐ ┌─────┐     │
│  │  1  │ │  2  │      │  1  │ │  2  │     │
│  └─────┘ └─────┘      └─────┘ └─────┘     │
│      ╲        ╱            ╲       ╱        │
│       ╲      ╱              ╲     ╱         │
│        ╲~~~~╱  75%           ╲~~~╱  45%     │
│  ┌─────┐                  ┌─────┐           │
│  │  3  │                  │  3  │           │
│  └─────┘                  └─────┘           │
│                                             │
│                         ┌──────────────┐   │
│                         │  📸 画像検索  │   │
│  Web: 3 | PDF: 3       │   ドロップ   │   │
│  ペア: 2               └──────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 🔍 Micro View（詳細比較）

### 機能

#### **Visualモード**
- **左右分割表示**: WebとPDFを並べて比較
- **同期スクロール**: 両方のキャンバスが同時にスクロール
- **オニオンスキンモード**: 画像を重ね合わせて透過度調整
- **バウンディングボックス**: テキストエリアを視覚化

#### **Textモード**
- **差分ハイライト**:
  - 🟢 緑: 追加された行
  - 🔴 赤: 削除された行
  - ⚪ 白: 一致する行
- **difflibベース**: Pythonネイティブの差分検出

### 使い方

```python
from app.gui.micro_view import MicroView
from app.core.analyzer import MatchedPair

# MicroViewを開く
micro = MicroView(
    parent,
    matched_pair=pair,
    analyzer=analyzer
)
```

### UI構成

```
┌─────────────────────────────────────────────────────┐
│ 🔍 詳細比較            類似度: 75%    [🖼️Visual][📝Text] │
├─────────────────────────────────────────────────────┤
│ [✓同期スクロール]  [🧅オニオンスキン]       [← 戻る] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🌐 Web                    📁 PDF                   │
│  ┌──────────────┐         ┌──────────────┐         │
│  │              │         │              │         │
│  │              │         │              │         │
│  │  [画像表示]   │         │  [画像表示]   │         │
│  │              │         │              │         │
│  │              │         │              │         │
│  └──────────────┘         └──────────────┘         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🎛️ Navigation Panel

### 更新内容

- **🗺️ ビュー** セクションを追加
  - 「🗺️ 全体マップ」ボタン
- 既存の機能を整理

### ボタン一覧

#### ビュー
- 🗺️ 全体マップ

#### 読込
- 🌐 Web一括クロール
- 📁 PDF一括読込

#### 処理
- ⚡ 一括マッチング
- 🔍 OCR実行

#### 出力
- 📤 Excel出力
- 💾 プロジェクト保存

#### 設定
- 📂 プロジェクト読込

---

## 🚀 Main Window V2

### 特徴

- **シンプルな設計**: 既存のmain_window.pyから大幅に簡素化
- **ContentAnalyzer統合**: 新しい分析エンジンを中心に設計
- **モジュラー構造**: ビューを切り替え可能

### 起動方法

```bash
# テストデータ付きで起動
python test_gui_v2.py

# 直接起動
python app/gui/main_window_v2.py
```

### アーキテクチャ

```
MainWindow
├── NavigationPanel
│   └── callbacks → MainWindow methods
└── ContentArea
    ├── WelcomeScreen (初期)
    ├── MacroView (切り替え可能)
    └── ...
```

---

## 🧪 テスト

### テストスクリプト

`test_gui_v2.py` - サンプルデータでGUIをテスト

```bash
python test_gui_v2.py
```

**機能:**
- サンプルWebエリア×3を生成
- サンプルPDFエリア×3を生成
- 自動マッチング実行
- GUIを起動して全体マップを表示

---

## 💡 使用例

### 完全なワークフロー

```python
from app.core.ocr_engine import OCREngine
from app.core.analyzer import ContentAnalyzer
from app.gui.main_window_v2 import MainWindow

# 1. エンジン初期化
ocr = OCREngine(credentials_path="credentials.json")
analyzer = ContentAnalyzer(ocr_engine=ocr)

# 2. Web画像を分析
analyzer.analyze_image(
    image_path="web_screenshot.png",
    source_type="web",
    source_id="https://example.com"
)

# 3. PDF画像を分析
analyzer.analyze_image(
    image_path="pdf_page.png",
    source_type="pdf",
    source_id="document.pdf",
    page_num=1
)

# 4. 自動マッチング
analyzer.compute_auto_matches(threshold=0.3)

# 5. GUIを起動
app = MainWindow()
app.analyzer = analyzer
app.show_macro_view()
app.mainloop()
```

---

## 🎨 カスタマイズ

### Macro View の設定

```python
macro_view.thumbnail_size = (250, 180)  # サムネイルサイズ
macro_view.grid_columns = 4             # グリッド列数
macro_view.grid_padding = 25            # グリッド間隔
```

### Micro View のモード切替

```python
# Visualモード
micro_view._switch_mode("visual")

# Textモード
micro_view._switch_mode("text")

# オニオンスキンを有効化
micro_view._toggle_onion_mode()
```

---

## 🐛 トラブルシューティング

### エラー: "ValueError: I/O operation on closed file"

**原因**: UTF-8ラッパーの二重設定

**解決策**: `main_window_v2.py` で条件付きUTF-8設定を使用（既に修正済み）

### エラー: "Analyzerが初期化されていません"

**原因**: OCRエンジンまたはAnalyzerが正しく設定されていない

**解決策**:
```python
analyzer = ContentAnalyzer()  # OCRなしでも動作
# または
ocr = OCREngine("credentials.json")
analyzer = ContentAnalyzer(ocr_engine=ocr)
```

### 画像が表示されない

**原因**: 画像データの読み込みロジックが未実装（プレースホルダー表示）

**今後の実装**: `_load_visual_data()` で実際の画像ファイルを読み込む

---

## 📝 今後の実装予定

### 優先度: 高
- [ ] 実際の画像データ読み込み（MacroView/MicroView）
- [ ] Web一括クロール機能の統合
- [ ] PDF一括読込機能の統合

### 優先度: 中
- [ ] オニオンスキン画像合成の実装
- [ ] 画像検索（VisualSearchEngine）の統合
- [ ] Excel出力（ReportWriter）の統合
- [ ] プロジェクト保存/読込（DataManager）の統合

### 優先度: 低
- [ ] ドラッグ&ドロップ機能
- [ ] サムネイル画像のキャッシング
- [ ] アニメーション効果

---

## 📚 関連ドキュメント

- [Analyzer API ガイド](./ANALYZER_API.md)
- [プロジェクト構造](../README.md)

---

**🎉 GUI V2 実装完了！**

新しいアーキテクチャで、より直感的で強力な比較ツールが実現されました。

