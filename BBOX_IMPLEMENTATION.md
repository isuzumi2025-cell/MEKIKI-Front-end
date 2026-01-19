# バウンディングボックス（座標情報）実装ドキュメント

## 概要
テキスト抽出時にバウンディングボックス（座標情報）を同時に取得し、UI側で画像上にテキスト位置を表示できるようにしました。

## 実装完了タスク

### ✅ タスク 1: PDFローダーの改修 (`app/utils/pdf_loader.py`)

#### 実装内容
- **PyMuPDFの`get_text("dict")`メソッドを使用**してテキストブロックごとの情報を取得
- 各テキストブロックについて以下の情報を抽出:
  - `text`: テキスト内容
  - `bbox`: 矩形座標 `[x0, y0, x1, y1]`
  - `area_id`: 自動採番されたエリアID

#### データ構造
```python
{
    "text": "抽出された特定の文言",
    "bbox": [x0, y0, x1, y1],  # スケーリング済み座標
    "area_id": 1  # 自動採番
}
```

#### 座標スケーリング
- PDFの座標はDPI（デフォルト400）に応じてスケーリング
- スケール係数: `self.dpi / 72.0`
- これにより、画像サイズと座標が一致

#### コード例
```python
# get_text("dict")でブロック情報を取得
text_dict = page.get_text("dict")
blocks = text_dict.get("blocks", [])

for block in blocks:
    if block.get("type") == 0:  # テキストブロック
        block_text = ""
        bbox = block.get("bbox", [0, 0, 0, 0])
        
        # ブロック内の行を結合
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "")
            block_text += "\n"
        
        block_text = block_text.strip()
        if block_text:
            # 座標をスケーリング
            scaled_bbox = [
                bbox[0] * scale,
                bbox[1] * scale,
                bbox[2] * scale,
                bbox[3] * scale
            ]
            areas.append({
                "text": block_text,
                "bbox": scaled_bbox,
                "area_id": area_id_counter
            })
            area_id_counter += 1
```

### ✅ タスク 2: Webクローラーの改修 (`app/core/crawler.py`)

#### 実装方針
Playwrightでの要素ごとの正確な位置取得は技術的に複雑なため、**暫定対応**として以下を実装:

#### 暫定実装
- **スクリーンショット全体を1つの巨大なエリアとして扱う**
- 画像のサイズ（width, height）を取得し、全体を覆う矩形として定義
- これにより後のフェーズで手動分割が可能

#### データ構造
```python
{
    "text": "ページ全体のテキスト",
    "bbox": [0, 0, img_width, img_height],  # 画像全体
    "area_id": 1
}
```

#### コード例
```python
# 暫定版: 画像全体を1つのエリアとして扱う
img_width, img_height = img_view.size if img_view else (1280, 800)
areas = [{
    "text": text,
    "bbox": [0, 0, img_width, img_height],
    "area_id": 1
}]
```

#### 将来の改善案
Playwrightで要素ごとの位置を取得する方法:
```javascript
// JavaScript側での実装例
const elements = await page.$$('p, h1, h2, h3, div');
for (const element of elements) {
    const box = await element.boundingBox();
    const text = await element.textContent();
    // box.x, box.y, box.width, box.height
}
```

## データフロー全体像

### 1. PDF処理フロー
```
PDF読み込み
  ↓
PyMuPDF (fitz) でテキストブロック抽出
  ↓
各ブロックごとに {text, bbox, area_id} を生成
  ↓
ProjectManager に areas として保存
  ↓
UI側で InteractiveCanvas に表示
```

### 2. Web処理フロー
```
Webクロール
  ↓
Playwright でテキストとスクリーンショット取得
  ↓
画像全体を1つの {text, bbox, area_id} として生成
  ↓
ProjectManager に areas として保存
  ↓
UI側で InteractiveCanvas に表示（手動分割可能）
```

## ProjectManager のデータ構造

### TextArea クラス
```python
@dataclass
class TextArea:
    """テキスト領域のデータ構造（bbox付き）"""
    text: str
    bbox: List[float]  # [x0, y0, x1, y1]
    area_id: Optional[int] = None
```

### WebPage クラス
```python
@dataclass
class WebPage:
    """Webページのデータ構造"""
    url: str
    title: str
    text: str
    screenshot_path: Optional[str] = None
    page_id: Optional[int] = None
    areas: Optional[List[TextArea]] = None  # ✅ bbox付きエリアリスト
    screenshot_image: Optional[object] = None
    error: Optional[str] = None
```

### PDFPage クラス
```python
@dataclass
class PDFPage:
    """PDFページのデータ構造"""
    filename: str
    page_num: int
    text: str
    image_path: Optional[str] = None
    page_id: Optional[int] = None
    areas: Optional[List[TextArea]] = None  # ✅ bbox付きエリアリスト
    page_image: Optional[object] = None
```

## UI連携

### InteractiveCanvas での表示
- `areas` リストを受け取り、各エリアを矩形として描画
- 各矩形には `area_id` に基づいた番号バッジを表示
- ユーザーは矩形を:
  - **左ドラッグ**: 新しい矩形を作成
  - **右クリック**: 既存の矩形を削除
  - **クリック**: 矩形を選択

### 使用例
```python
# PDF読み込み
results = pdf_loader.load_pdfs_from_folder("./pdfs")
for result in results:
    project_manager.add_pdf_page(
        filename=result["filename"],
        page_num=result["page_num"],
        text=result["text"],
        areas=[TextArea(**a) for a in result["areas"]],  # ✅ bbox情報
        page_image=result["page_image"]
    )

# UI側でキャンバスに表示
interactive_canvas.load_image_from_pil(
    page.page_image,
    title=f"PDF: {page.filename}",
    areas=[{"bbox": a.bbox, "area_id": a.area_id} for a in page.areas]
)
```

## テスト方法

### PDF処理のテスト
```python
from app.utils.pdf_loader import PDFLoader

loader = PDFLoader(dpi=400)
results = loader.load_pdfs_from_folder("./test_pdfs")

for result in results:
    print(f"ファイル: {result['filename']}")
    print(f"ページ: {result['page_num']}")
    print(f"エリア数: {len(result['areas'])}")
    
    for area in result['areas']:
        print(f"  エリア#{area['area_id']}: {area['text'][:50]}...")
        print(f"  座標: {area['bbox']}")
```

### Web処理のテスト
```python
from app.core.crawler import WebCrawler

crawler = WebCrawler(max_pages=5)
results = crawler.crawl("https://example.com")

for result in results:
    print(f"URL: {result['url']}")
    print(f"エリア数: {len(result['areas'])}")
    
    for area in result['areas']:
        print(f"  エリア#{area['area_id']}: bbox={area['bbox']}")
```

## まとめ

✅ **完了した項目**:
1. PDFローダーでテキストブロックごとのbbox情報を取得
2. PDFの戻り値データ構造を座標付きに変更（`area_id`も追加）
3. Webクローラーで暫定的な位置情報を実装
4. ProjectManagerのデータ構造が座標情報を保持

🎯 **達成したゴール**:
- `ProjectManager`が保持する`WebPage`および`PDFPage`のデータ構造に座標情報が含まれる
- UI側で画像上にテキスト位置を表示できる基盤が完成
- 手動での矩形編集も可能

🔮 **今後の拡張可能性**:
- Webクローラーで要素ごとの正確な位置取得（Playwrightの`boundingBox()`利用）
- OCRエンジンでの文字認識結果にもbbox情報を追加
- エリア間の関連性分析（隣接エリアの結合など）

