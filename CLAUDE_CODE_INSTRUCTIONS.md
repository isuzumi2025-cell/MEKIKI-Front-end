# MEKIKI Proofing System - 画面表示問題の修正

## 🔴 現在の問題（スクリーンショット参照）

### 1. Live Comparison Sheet - メタデータ列が空白

**対象ファイル**: `app/gui/windows/advanced_comparison_view.py`

#### 問題の詳細

- **Score** 列: 空白（同期スコアが表示されていない）
- **Web ID / Thumb** 列: 空白（WebページのID番号とサムネイル画像が表示されていない）
- **PDF ID / Thumb** 列: 空白（PDFページのID番号とサムネイル画像が表示されていない）

#### 期待される動作

各行に以下を表示する必要がある：

- **Score**: `Match: 87%` のような同期率スコア
- **Web ID / Thumb**:
  - UniqueなID番号（例: `W-001`）
  - 小さなサムネイル画像（60x80px程度）
- **PDF ID / Thumb**:
  - UniqueなID番号（例: `P-004`）
  - 小さなサムネイル画像（60x80px程度）

#### 実装方法

以前のOCR機能コードから**サムネイル生成・表示メソッド**を転用すること。

参照先の可能性：

```
c:/Users/raiko/OneDrive/Desktop/26/OCR/app/gui/
├── ocr_canvas.py  # 旧OCR機能のキャンバス実装
├── thumbnail_generator.py  # サムネイル生成ロジック（存在する場合）
└── cluster_viewer.py  # バウンディングボックス表示実装
```

---

### 2. Web/PDF Sourceウィンドウ - 画像が小さく表示される

**対象ファイル**: `app/gui/windows/advanced_comparison_view.py`

#### 問題の詳細

- Web SourceウィンドウとPDF Sourceウィンドウの画像周囲に**大きな余白**がある
- 画像がウィンドウサイズに対して縮小されすぎている
- ウィンドウいっぱいに画像が表示されていない

#### 期待される動作

- ウィンドウサイズに合わせて画像を**余白なく**自動拡大/縮小
- アスペクト比を維持しつつ、**ウィンドウいっぱい**に表示
- ウィンドウリサイズ時に動的に再描画

#### 実装アプローチ

```python
# 疑似コード例
def fit_image_to_canvas(self, image, canvas_width, canvas_height):
    """
    画像をキャンバスサイズに余白なくフィット
    
    Args:
        image: PIL Image
        canvas_width: キャンバスの幅
        canvas_height: キャンバスの高さ
    
    Returns:
        リサイズされたPhotoImage
    """
    img_width, img_height = image.size
    
    # アスペクト比を維持しつつ最大化
    width_ratio = canvas_width / img_width
    height_ratio = canvas_height / img_height
    scale = max(width_ratio, height_ratio)  # 余白をなくすためにmax使用
    
    new_width = int(img_width * scale)
    new_height = int(img_height * scale)
    
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(resized)
```

---

### 3. Overviewウィンドウ - ページサムネイルの表示

**現状**: 正常に表示されている ✅

---

## 📋 修正チェックリスト

### 優先度: High 🔴

- [ ] Live Comparison SheetのScore列にスコア表示を実装
- [ ] Live Comparison SheetのWeb ID/Thumb列にIDとサムネイル表示を実装
- [ ] Live Comparison SheetのPDF ID/Thumb列にIDとサムネイル表示を実装
- [ ] Web/PDF Sourceウィンドウの画像表示を余白なしに修正

### 優先度: Medium 🟡

- [ ] ウィンドウリサイズ時の画像再描画イベントハンドラ追加
- [ ] サムネイル画像のキャッシュ機構実装（パフォーマンス向上）

---

## 🔧 実装の注意点

### 1. サムネイル生成

- `PIL.Image.thumbnail()` または `Image.resize()` を使用
- サムネイルサイズ: 60x80px（Web/PDF列に収まるサイズ）
- アスペクト比を維持

### 2. CustomTkinterでの画像表示

- `CTkLabel` + `ImageTk.PhotoImage` を使用
- 画像オブジェクトへの参照を保持（GC対策）

```python
self.thumbnail_refs = []  # クラス変数で参照を保持
```

### 3. Scoreの計算

- 既存の`text_comparator.py`の類似度計算ロジックを使用
- テキストマッチング率: `difflib.SequenceMatcher` or `fuzzywuzzy`

---

## 📁 関連ファイル

```
c:/Users/raiko/OneDrive/Desktop/26/OCR/
├── app/gui/windows/advanced_comparison_view.py  # メイン修正対象
├── app/core/text_comparator.py  # スコア計算ロジック
└── app/utils/image_utils.py  # 画像処理ユーティリティ（要確認）
```

---

## 🎯 期待される結果

修正後の表示：

- **Live Comparison Sheet**: 各行にID、サムネイル、スコアがすべて表示される
- **Web/PDF Source**: 画像が余白なくウィンドウいっぱいに表示される
- **Overview**: 現状維持（既に正常）

---

## 🧪 テスト方法

1. アプリを起動
2. Web読み込み/PDF読み込みでデータを読み込む
3. ハイブリッドOCRを実行
4. Live Comparison Sheetで以下を確認：
   - Score列に `Match: XX%` が表示される
   - Web ID/Thumb列にIDと画像が表示される
   - PDF ID/Thumb列にIDと画像が表示される
5. Web/PDF Sourceウィンドウをリサイズして画像が余白なく表示されることを確認
