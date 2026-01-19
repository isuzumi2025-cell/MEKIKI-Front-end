# ビジュアル比較画面 - 実装ドキュメント

## 概要
テキストベースの比較画面を廃止し、`InteractiveCanvas`を使った直感的なビジュアル比較画面に刷新しました。

## 実装完了タスク

### ✅ 1. UIの置き換え

#### Before（旧実装）
```
┌─────────────────────────────────────┐
│  シンクロ率: XX%                    │
├──────────────────┬──────────────────┤
│ 🌐 Web:          │ 📁 PDF:          │
│ ┌──────────────┐ │ ┌──────────────┐ │
│ │ テキスト     │ │ │ テキスト     │ │
│ │ ボックス     │ │ │ ボックス     │ │
│ │ (黒背景)     │ │ │ (黒背景)     │ │
│ └──────────────┘ │ └──────────────┘ │
└──────────────────┴──────────────────┘
```

#### After（新実装）
```
┌─────────────────────────────────────┐
│ 🔄 シンクロ率: XX%  💡ヒントメッセージ│
├──────────────────┬──────────────────┤
│ InteractiveCanvas│ InteractiveCanvas│
│ ┌──────────────┐ │ ┌──────────────┐ │
│ │🌐 Web URL    │ │ │📁 PDF File   │ │
│ ├──────────────┤ │ ├──────────────┤ │
│ │   [画像]     │ │ │   [画像]     │ │
│ │   ①②③      │ │ │   ①②③      │ │
│ │  赤枠表示    │ │ │  赤枠表示    │ │
│ └──────────────┘ │ └──────────────┘ │
└──────────────────┴──────────────────┘
```

**変更内容**:
- ❌ **削除**: `CTkTextbox`による左右のテキスト表示エリア
- ✅ **追加**: 左右に2つの`InteractiveCanvas`を配置
- ✅ **改善**: ウィンドウサイズを`1400x800`→`1600x900`に拡大
- ✅ **改善**: ヘッダーに説明テキストを追加

### ✅ 2. データ連携

#### Web側（左）の実装

```python
# Web画像用InteractiveCanvas
web_canvas = InteractiveCanvas(web_frame, width=760, height=700)
web_canvas.pack(fill="both", expand=True, padx=5, pady=5)

# Web画像とエリアデータをロード
if web_page.screenshot_image:
    # エリアデータを準備
    web_areas = []
    if web_page.areas:
        for idx, area in enumerate(web_page.areas):
            web_areas.append({
                "bbox": area.bbox if hasattr(area, 'bbox') else [0, 0, 100, 100],
                "area_id": idx + 1
            })
    
    # PIL Imageから直接読み込む
    web_canvas.load_image_from_pil(
        pil_image=web_page.screenshot_image,
        title=f"🌐 Web: {web_page.url}",
        areas=web_areas
    )
```

**機能**:
- Webページのスクリーンショット画像を表示
- フェーズ1で取得した座標データから赤枠を自動描画
- ヘッダーにWebページのURLを表示

#### PDF側（右）の実装

```python
# PDF画像用InteractiveCanvas
pdf_canvas = InteractiveCanvas(pdf_frame, width=760, height=700)
pdf_canvas.pack(fill="both", expand=True, padx=5, pady=5)

# PDF画像とエリアデータをロード
if pdf_page.page_image:
    # エリアデータを準備
    pdf_areas = []
    if pdf_page.areas:
        for idx, area in enumerate(pdf_page.areas):
            pdf_areas.append({
                "bbox": area.bbox if hasattr(area, 'bbox') else [0, 0, 100, 100],
                "area_id": idx + 1
            })
    
    pdf_filename = Path(pdf_page.filename).name
    
    # PIL Imageから直接読み込む
    pdf_canvas.load_image_from_pil(
        pil_image=pdf_page.page_image,
        title=f"📁 PDF: {pdf_filename} (ページ {pdf_page.page_num})",
        areas=pdf_areas
    )
```

**機能**:
- PDFページの画像を表示
- PyMuPDFで抽出した座標データから赤枠を自動描画
- ヘッダーにPDFファイル名とページ番号を表示

### ✅ 3. ヘッダー表示

#### Web側（左）
```
🌐 Web: https://example.com/page1
```

#### PDF側（右）
```
📁 PDF: document.pdf (ページ 1)
```

**実装方法**:
`InteractiveCanvas`の内蔵ヘッダー機能を活用：
```python
web_canvas.load_image_from_pil(
    pil_image=image,
    title=f"🌐 Web: {url}",  # ✅ ヘッダーに表示
    areas=areas
)
```

## ユーザー操作

### 👁️ 視覚的比較
- 左右の画像を並べて確認
- 赤枠の位置でテキスト領域を視覚的に確認
- エリア番号（①②③...）で対応関係を把握

### 🖱️ インタラクティブ編集

| 操作 | 結果 |
|------|------|
| **左クリック（エリア上）** | エリアを選択（緑色にハイライト）|
| **左ドラッグ（空白）** | 新しいエリアを追加 |
| **右クリック** | クリック位置のエリアを削除 |
| **スクロール** | 大きな画像も閲覧可能 |

### 🎯 使用シナリオ

1. **エリアのズレ確認**
   - 左右の赤枠の位置を比較
   - テキスト抽出精度を視覚的に確認

2. **不要なエリア削除**
   - ヘッダー/フッターなど不要な枠を右クリックで削除
   - ノイズとなるエリアを除外

3. **エリアの追加**
   - 抽出漏れがある場合、ドラッグで新規エリアを作成
   - 重要なテキスト領域を補完

## コードの詳細

### 比較ウィンドウの構造

```python
def _show_detail_comparison(self, web_page, pdf_page, score):
    """詳細比較ウィンドウを表示（ビジュアル比較版）"""
    
    # 1. ダイアログ作成
    dialog = ctk.CTkToplevel(self)
    dialog.title(f"📊 ビジュアル比較: {web_page.title}")
    dialog.geometry("1600x900")
    
    # 2. ヘッダー（シンクロ率と説明）
    header = ctk.CTkFrame(dialog, height=80, fg_color="#1A1A1A")
    # ... シンクロ率と説明テキストを表示
    
    # 3. 左右分割パネル
    main_paned = tk.PanedWindow(dialog, orient="horizontal")
    
    # 4. 左側: Web用InteractiveCanvas
    web_canvas = InteractiveCanvas(web_frame, width=760, height=700)
    # ... Web画像とエリアデータをロード
    
    # 5. 右側: PDF用InteractiveCanvas
    pdf_canvas = InteractiveCanvas(pdf_frame, width=760, height=700)
    # ... PDF画像とエリアデータをロード
    
    # 6. 閉じるボタン
    close_button = ctk.CTkButton(dialog, text="閉じる", ...)
```

### データフロー

```
ProjectManager
    ↓
web_page.areas, pdf_page.areas (TextArea型)
    ↓
比較ウィンドウ (_show_detail_comparison)
    ↓
エリアデータを辞書型に変換
[{"bbox": [x0,y0,x1,y1], "area_id": 1}, ...]
    ↓
InteractiveCanvas.load_image_from_pil()
    ↓
画像上に赤枠を自動描画
```

### エラーハンドリング

**画像がない場合**:
```python
if web_page.screenshot_image:
    # 画像を表示
    web_canvas.load_image_from_pil(...)
else:
    # タイトルのみ表示
    web_canvas.set_title(f"🌐 Web: {web_page.url} (画像なし)")
```

**ファイルパスとPIL Imageの両方に対応**:
```python
# まずファイルパスで試す
web_canvas.load_data(
    image_path=web_page.screenshot_path if web_page.screenshot_path else None,
    title=...,
    area_data_list=web_areas
)

# ファイルが存在しない場合はPIL Imageから読み込む
if not web_page.screenshot_path or not os.path.exists(web_page.screenshot_path):
    web_canvas.load_image_from_pil(
        pil_image=web_page.screenshot_image,
        title=...,
        areas=web_areas
    )
```

## 呼び出し元

### マッチング結果カードから

```python
# ProjectWindow内のマッチング結果表示
detail_button = ctk.CTkButton(
    card,
    text="🔍 詳細比較",
    command=lambda w=web_page, p=pdf_page, s=score: 
        self._show_detail_comparison(w, p, s)
)
```

**動作**:
1. ユーザーが「🔍 詳細比較」ボタンをクリック
2. `_show_detail_comparison()`が呼ばれる
3. 新しいウィンドウが開き、左右に画像が表示される

## UI/UXの改善点

### Before vs After

| 項目 | Before | After |
|------|--------|-------|
| **表示方式** | テキストのみ | 画像+赤枠 |
| **視認性** | 低（文字だらけ） | 高（ビジュアル）|
| **編集機能** | なし | あり（追加/削除） |
| **座標確認** | 不可能 | 可能（赤枠で表示） |
| **スクロール** | テキストのみ | 画像全体 |
| **直感性** | 低 | 高 |

### ユーザーメリット

1. **視覚的に分かりやすい**
   - テキストを読む必要なし
   - 一目でズレや問題を発見

2. **インタラクティブ**
   - その場で編集可能
   - 試行錯誤が容易

3. **精度向上**
   - テキスト抽出の精度を視覚的に確認
   - 問題箇所を即座に特定

4. **作業効率向上**
   - 左右比較が直感的
   - 赤枠でエリア対応が明確

## テスト方法

### 基本テスト
```python
# プロジェクトウィンドウを開く
project_window = ProjectWindow(root)

# WebとPDFを読み込む
# ... (クロール・PDF読込)

# マッチングを実行
# ... (一括マッチング)

# 詳細比較ボタンをクリック
# → 左右に画像が表示されることを確認
# → 赤枠が正しく表示されることを確認
# → ヘッダーにURL/ファイル名が表示されることを確認
```

### 操作テスト
1. **エリア選択**: 赤枠をクリック → 緑色に変わる
2. **エリア削除**: 赤枠を右クリック → 枠が消える
3. **エリア追加**: 空白をドラッグ → 新しい赤枠が作成される
4. **スクロール**: 画像が大きい場合 → スクロールバーで閲覧可能

## まとめ

✅ **完了した改善**:
1. テキストボックスを`InteractiveCanvas`に置き換え
2. Web画像とPDF画像を左右に並べて表示
3. 座標データに基づく赤枠の自動描画
4. ヘッダーでURL/ファイル名を明示
5. インタラクティブな編集機能（追加/削除/選択）

🎯 **達成した目標**:
- 直感的なビジュアル比較が可能
- ユーザーは左右の画像を見比べながら赤枠のズレを確認
- 不要な枠を右クリックで簡単に削除
- 新しいエリアをドラッグで追加可能

🚀 **今後の拡張可能性**:
- エリア間の対応関係を線で結ぶ
- 差分のハイライト表示
- 類似度スコアをエリアごとに表示
- 編集内容の保存機能

