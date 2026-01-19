# 🔬 Analyzer & OCR Engine API ドキュメント

## 概要

`OCREngine` と `ContentAnalyzer` は、Web画像とPDF画像からテキストを抽出し、自動的にマッチングを行う強力な分析エンジンです。

---

## 📦 クラス: `OCREngine`

Google Cloud Vision APIを使用した高精度OCRエンジン。

### 初期化

```python
from app.core.ocr_engine import OCREngine

ocr = OCREngine(credentials_path="credentials.json")
ocr.initialize()
```

### メソッド

#### `initialize() -> bool`

Vision APIクライアントを初期化します。

- **戻り値**: 成功時 `True`、失敗時 `False`

**使用例:**
```python
if ocr.initialize():
    print("初期化成功")
else:
    print("初期化失敗")
```

---

#### `detect_document_text(image_path: str) -> Optional[Dict]`

画像からドキュメントテキストを検出し、ブロック情報を含む構造化データを返します。

- **引数**:
  - `image_path`: 画像ファイルのパス

- **戻り値**: 
  ```python
  {
      "full_text": str,  # 全体テキスト
      "blocks": [
          {
              "text": str,
              "bbox": [x0, y0, x1, y1],  # バウンディングボックス
              "confidence": float,  # 信頼度 (0.0-1.0)
              "type": "BLOCK" | "PARAGRAPH"
          },
          ...
      ]
  }
  ```

**使用例:**
```python
result = ocr.detect_document_text("screenshot.png")

if result:
    print(f"全体テキスト: {result['full_text']}")
    print(f"検出ブロック数: {len(result['blocks'])}")
```

---

## 📊 クラス: `ContentAnalyzer`

テキスト分析、自動マッチング、類似度計算を行うコアエンジン。

### 初期化

```python
from app.core.analyzer import ContentAnalyzer

analyzer = ContentAnalyzer(ocr_engine=ocr)
```

### データクラス

#### `DetectedArea`

検出されたテキストエリアを表すデータクラス。

```python
@dataclass
class DetectedArea:
    id: str              # 一意のID
    text: str            # テキスト内容
    bbox: List[int]      # [x0, y0, x1, y1]
    confidence: float    # 信頼度
    source_type: str     # "web" or "pdf"
    source_id: str       # URL or ファイル名
    page_num: Optional[int]  # ページ番号
```

#### `MatchedPair`

マッチングされたペアを表すデータクラス。

```python
@dataclass
class MatchedPair:
    web_area: DetectedArea
    pdf_area: DetectedArea
    similarity_score: float
    match_type: str  # "auto" or "manual"
```

---

### メソッド

#### `analyze_image(...) -> List[DetectedArea]`

画像をOCRにかけ、結果を `DetectedArea` のリストに変換して保存します。

**引数:**
- `image_path: str` - 画像ファイルのパス
- `source_type: str` - `"web"` または `"pdf"`
- `source_id: str` - URL またはファイル名
- `page_num: Optional[int]` - ページ番号（PDFの場合）

**戻り値:** `List[DetectedArea]`

**使用例:**
```python
# Web画像を分析
web_areas = analyzer.analyze_image(
    image_path="screenshots/page1.png",
    source_type="web",
    source_id="https://example.com/page1"
)

# PDF画像を分析
pdf_areas = analyzer.analyze_image(
    image_path="pdf_previews/doc_p1.png",
    source_type="pdf",
    source_id="document.pdf",
    page_num=1
)
```

---

#### `compute_auto_matches(...) -> List[MatchedPair]`

WebエリアとPDFエリアを自動的にマッチングします。

**引数:**
- `threshold: float = 0.3` - マッチング閾値 (0.0-1.0)
- `method: str = "hybrid"` - 類似度計算方法
  - `"difflib"`: SequenceMatcher
  - `"jaccard"`: Jaccard係数
  - `"hybrid"`: 両方の平均

**戻り値:** `List[MatchedPair]`

**使用例:**
```python
# 自動マッチング実行
pairs = analyzer.compute_auto_matches(
    threshold=0.3,
    method="hybrid"
)

# 結果を表示
for pair in pairs:
    print(f"類似度: {pair.similarity_score:.2%}")
    print(f"Web: {pair.web_area.text[:30]}...")
    print(f"PDF: {pair.pdf_area.text[:30]}...")
```

---

#### `add_manual_pair(...) -> MatchedPair`

手動でペアを追加します。

**引数:**
- `web_area: DetectedArea`
- `pdf_area: DetectedArea`

**戻り値:** `MatchedPair`

**使用例:**
```python
pair = analyzer.add_manual_pair(
    web_area=selected_web_area,
    pdf_area=selected_pdf_area
)
```

---

#### `find_differences(text1: str, text2: str) -> List[Dict]`

2つのテキスト間の差分を検出します。

**引数:**
- `text1: str` - テキスト1
- `text2: str` - テキスト2

**戻り値:**
```python
[
    {
        "type": "add" | "delete" | "change",
        "text": str,
        "line": int
    },
    ...
]
```

**使用例:**
```python
differences = analyzer.find_differences(
    web_text,
    pdf_text
)

for diff in differences:
    if diff["type"] == "add":
        print(f"+ {diff['text']}")
    elif diff["type"] == "delete":
        print(f"- {diff['text']}")
```

---

#### `get_statistics() -> Dict`

統計情報を取得します。

**戻り値:**
```python
{
    "web_areas_count": int,
    "pdf_areas_count": int,
    "matched_pairs_count": int,
    "average_similarity": float
}
```

---

## 🚀 完全なワークフロー例

```python
from app.core.ocr_engine import OCREngine
from app.core.analyzer import ContentAnalyzer

# 1. 初期化
ocr = OCREngine(credentials_path="credentials.json")
ocr.initialize()

analyzer = ContentAnalyzer(ocr_engine=ocr)

# 2. Web画像を分析
web_areas = analyzer.analyze_image(
    image_path="screenshots/web_page.png",
    source_type="web",
    source_id="https://example.com"
)

# 3. PDF画像を分析
pdf_areas = analyzer.analyze_image(
    image_path="pdf_previews/doc_p1.png",
    source_type="pdf",
    source_id="document.pdf",
    page_num=1
)

# 4. 自動マッチング
pairs = analyzer.compute_auto_matches(
    threshold=0.4,
    method="hybrid"
)

# 5. 統計情報を表示
stats = analyzer.get_statistics()
print(f"マッチング済みペア: {stats['matched_pairs_count']}")
print(f"平均類似度: {stats['average_similarity']:.2%}")

# 6. 差分を確認
for pair in pairs:
    diffs = analyzer.find_differences(
        pair.web_area.text,
        pair.pdf_area.text
    )
    if diffs:
        print(f"差分あり: {len(diffs)}箇所")
```

---

## ⚙️ 設定ガイド

### Google Cloud Vision API の設定

1. **Google Cloud Console** にアクセス
2. **Vision API** を有効化
3. **サービスアカウント** を作成
4. **認証キー（JSON）** をダウンロード
5. ダウンロードしたファイルを `credentials.json` として、プロジェクトルートに配置

```
project_root/
├── credentials.json  ← ここに配置
├── main.py
└── app/
```

---

## 🔧 トラブルシューティング

### エラー: "認証ファイルが見つかりません"

**解決策:** `credentials.json` がプロジェクトルートに配置されているか確認してください。

### エラー: "google-cloud-vision がインストールされていません"

**解決策:**
```bash
pip install google-cloud-vision>=3.0.0
```

### エラー: "OCR結果が取得できませんでした"

**原因:** 
- 画像ファイルが存在しない
- 画像形式が対応していない
- Vision APIの割り当てを超えている

**解決策:** 画像パスとフォーマットを確認し、Google Cloud Consoleで割り当てを確認してください。

---

## 📝 まとめ

- **OCREngine**: Google Cloud Vision APIの統合
- **ContentAnalyzer**: テキスト分析と自動マッチング
- **DetectedArea**: 検出されたエリアのデータ構造
- **MatchedPair**: マッチング結果のデータ構造

これらのクラスを組み合わせることで、強力なWeb-PDF比較システムを構築できます。

