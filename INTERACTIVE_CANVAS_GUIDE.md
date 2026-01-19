# InteractiveCanvas - 高度な画像編集ウィジェット

## 概要
`InteractiveCanvas` は、画像上に矩形エリアを表示・編集するための高度なGUIウィジェットです。
CustomTkinterベースで、独立した再利用可能なコンポーネントとして設計されています。

## 特徴

✨ **主要機能**:
- 画像の表示とスクロール対応（大きな画像も閲覧可能）
- 座標データに基づく矩形エリアの自動描画
- マウス操作による直感的な編集
- エリアの選択状態表示（色変更）
- 丸数字（①②③...）によるエリア番号表示

## インストール

```python
from app.gui.interactive_canvas import InteractiveCanvas
```

## 基本的な使い方

### 1. ウィジェットの作成

```python
import customtkinter as ctk
from app.gui.interactive_canvas import InteractiveCanvas

# メインウィンドウ
root = ctk.CTk()

# InteractiveCanvasを作成
canvas = InteractiveCanvas(root, width=800, height=600)
canvas.pack(fill="both", expand=True)

root.mainloop()
```

### 2. 画像とエリアデータの読み込み

```python
# 座標データの準備
area_data_list = [
    {"bbox": [100, 100, 300, 200], "area_id": 1},
    {"bbox": [350, 150, 500, 250], "area_id": 2},
    {"bbox": [120, 300, 400, 450], "area_id": 3}
]

# 画像とエリアを読み込む（推奨メソッド）
canvas.load_data(
    image_path="path/to/image.png",
    title="ファイル名またはURL",
    area_data_list=area_data_list
)
```

### 3. PIL Imageから直接読み込む

```python
from PIL import Image

# PIL Imageオブジェクトを用意
pil_image = Image.open("path/to/image.png")

# エリアデータ
areas = [
    {"bbox": [50, 50, 200, 150]},
    {"bbox": [250, 100, 400, 200]}
]

# 読み込み
canvas.load_image_from_pil(
    pil_image=pil_image,
    title="🌐 https://example.com",
    areas=areas
)
```

## インタラクティブ操作

### マウス操作

| 操作 | 動作 |
|------|------|
| **左クリック（空白）** | 既存エリアがない場所をクリック → ドラッグで新規矩形作成開始 |
| **左ドラッグ** | 黄色の点線で一時矩形を表示 |
| **左ボタン離す** | 矩形を確定（10px以上の場合のみ）|
| **左クリック（エリア上）** | エリアを選択 → 緑色にハイライト |
| **右クリック** | クリック位置のエリアを削除 |

### 視覚的フィードバック

- **通常状態**: 赤枠、赤背景のバッジ
- **選択状態**: 緑枠（太線）、緑背景のバッジ
- **ドラッグ中**: 黄色の点線

## APIリファレンス

### コンストラクタ

```python
InteractiveCanvas(master, width=800, height=600, **kwargs)
```

**引数**:
- `master`: 親ウィジェット
- `width`: キャンバスの幅（ピクセル）
- `height`: キャンバスの高さ（ピクセル）
- `**kwargs`: その他のCTkFrameのオプション

### メソッド

#### `load_data(image_path, title, area_data_list=None)`
画像とエリアデータを読み込む（推奨メソッド）

**引数**:
- `image_path` (str): 画像ファイルのパス
- `title` (str): ヘッダーに表示するタイトル
- `area_data_list` (List[Dict], optional): エリアデータのリスト

**エリアデータ形式**:
```python
[
    {"bbox": [x0, y0, x1, y1], "area_id": 1},
    {"bbox": [x0, y0, x1, y1], "area_id": 2},
    ...
]
```

#### `load_image(image_path, title, areas=None)`
ファイルパスから画像を読み込む

#### `load_image_from_pil(pil_image, title="", areas=None)`
PIL Imageオブジェクトから読み込む

**引数**:
- `pil_image` (PIL.Image.Image): PIL Imageオブジェクト
- `title` (str, optional): ヘッダータイトル
- `areas` (List[Dict], optional): エリアリスト

#### `get_areas() -> List[Dict]`
現在のエリア情報を取得

**戻り値**:
```python
[
    {"id": 1, "bbox": [x0, y0, x1, y1]},
    {"id": 2, "bbox": [x0, y0, x1, y1]},
    ...
]
```

#### `clear()`
キャンバスをクリアしてリセット

#### `set_title(title)`
ヘッダータイトルを設定

**引数**:
- `title` (str): 新しいタイトル

## 実践的な使用例

### 例1: PDFページの表示と編集

```python
from app.utils.pdf_loader import PDFLoader
from app.gui.interactive_canvas import InteractiveCanvas

# PDFを読み込む
loader = PDFLoader(dpi=400)
results = loader.load_pdfs_from_folder("./pdfs")

# 最初のページを表示
first_page = results[0]

canvas.load_image_from_pil(
    pil_image=first_page["page_image"],
    title=f"📁 {first_page['filename']} (ページ {first_page['page_num']})",
    areas=first_page["areas"]
)

# ユーザーが編集後、エリア情報を取得
edited_areas = canvas.get_areas()
print(f"編集後のエリア数: {len(edited_areas)}")
```

### 例2: Webページのスクリーンショット表示

```python
from app.core.crawler import WebCrawler
from app.gui.interactive_canvas import InteractiveCanvas

# Webページをクロール
crawler = WebCrawler(max_pages=5)
results = crawler.crawl("https://example.com")

# 最初のページを表示
first_result = results[0]

if not first_result.get("error"):
    canvas.load_image_from_pil(
        pil_image=first_result["screenshot_image"],
        title=f"🌐 {first_result['url']}",
        areas=first_result["areas"]
    )
```

### 例3: プロジェクト管理画面での使用

```python
import customtkinter as ctk
from app.gui.interactive_canvas import InteractiveCanvas
from app.core.project_manager import ProjectManager

class ProjectWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        # InteractiveCanvasを配置
        self.canvas = InteractiveCanvas(self, width=800, height=600)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        # プロジェクトマネージャー
        self.project_manager = ProjectManager()
    
    def show_web_page(self, page_id):
        """Webページを表示"""
        page = self.project_manager.get_web_page_by_id(page_id)
        
        if page and page.screenshot_image:
            # エリアデータを変換
            areas = []
            if page.areas:
                areas = [
                    {"bbox": area.bbox, "area_id": idx + 1}
                    for idx, area in enumerate(page.areas)
                ]
            
            # キャンバスに表示
            self.canvas.load_image_from_pil(
                pil_image=page.screenshot_image,
                title=f"🌐 {page.url}",
                areas=areas
            )
    
    def show_pdf_page(self, page_id):
        """PDFページを表示"""
        page = self.project_manager.get_pdf_page_by_id(page_id)
        
        if page and page.page_image:
            # エリアデータを変換
            areas = []
            if page.areas:
                areas = [
                    {"bbox": area.bbox, "area_id": idx + 1}
                    for idx, area in enumerate(page.areas)
                ]
            
            # キャンバスに表示
            self.canvas.load_image_from_pil(
                pil_image=page.page_image,
                title=f"📁 {page.filename} (ページ {page.page_num})",
                areas=areas
            )
```

## エリア番号の表示

エ��ア番号は丸数字で表示されます：

- 1〜20: ①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳
- 21以上: 通常の数字（21, 22, 23...）

## 内部実装の詳細

### データ構造

```python
# 内部で管理されるエリアデータ
{
    "id": int,              # エリアID（1から開始）
    "bbox": [x0, y0, x1, y1],  # 座標
    "rect_id": int,         # Canvas上の矩形ID
    "badge_bg_id": int,     # バッジ背景のID
    "badge_text_id": int,   # バッジテキストのID
    "selected": bool        # 選択状態
}
```

### 座標変換

スクロール時も正確な座標を取得するため、`canvas.canvasx()`と`canvas.canvasy()`を使用：

```python
x = self.canvas.canvasx(event.x)
y = self.canvas.canvasy(event.y)
```

### ガベージコレクション対策

PIL ImageをPhotoImageに変換した際、参照を保持して自動削除を防止：

```python
self.tk_image = ImageTk.PhotoImage(self.pil_image)  # 参照を保持
```

## トラブルシューティング

### 画像が表示されない

**原因**: PIL Imageの参照が失われている
**解決策**: `self.tk_image`に参照を保持

### クリック位置がずれる

**原因**: スクロール時の座標変換が不正確
**解決策**: `canvasx()`/`canvasy()`を使用

### エリアが削除されない

**原因**: 座標判定が正しくない
**解決策**: bbox範囲内判定のロジックを確認

## まとめ

`InteractiveCanvas`は、画像上のテキスト領域を視覚的に編集するための完全なソリューションです。

✅ **完全な機能**:
- 画像表示とスクロール
- 座標データの可視化
- インタラクティブな編集
- 選択状態の管理
- 丸数字バッジ表示

🎯 **使いやすさ**:
- シンプルなAPI
- 独立したコンポーネント
- 他の画面から簡単にimport可能

🚀 **拡張性**:
- カスタマイズ可能なスタイル
- イベントコールバック対応可能
- 複数のデータソースに対応

