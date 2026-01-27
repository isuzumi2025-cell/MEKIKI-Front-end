# Storyboard Extractor v2 SDK Runbook

**Version**: 2.0.0
**Last Updated**: 2026-01-24
**Status**: 📋 仕様策定中

---

## 概要

コンテ素材抽出ツールのSDK仕様書。比較マトリクスと同じUI構成で素材を表示し、手動範囲選択・シート表示・多形式エクスポートを実現する。

---

## アーキテクチャ

```
app/
├── gui/windows/
│   └── storyboard_extractor.py  # GUI (v2リデザイン)
│
├── pipeline/storyboard/
│   ├── layer_separator.py       # レイヤー分離
│   ├── paragraph_splitter.py    # パラグラフ分割
│   └── image_slicer.py          # 画像分割
│
└── sdk/storyboard/              # NEW: SDK層
    ├── __init__.py
    ├── layer_analyzer.py        # フォントウェイト分析
    ├── layout_exporter.py       # PPTX座標配置
    └── sheet_generator.py       # シートデータ生成
```

---

## GUI仕様

### レイアウト (3パネル構成)

```
┌──────────────────────────────────────────────────────────┐
│ [左] Action Panel │ [中央] Source View (テキスト/画像)    │
│                   │                                      │
│ ・インポート      │  ┌──────────────────────────────┐   │
│ ・レイヤー数表示  │  │  テキスト │ 画像  (タブ切替)   │   │
│   - テキスト: N層 │  │                              │   │
│   - 画像: M層     │  │  [キャンバス: 手動選択対応]  │   │
│ ・エクスポート    │  │                              │   │
│                   │  └──────────────────────────────┘   │
├───────────────────┴──────────────────────────────────────┤
│ [下] 素材シート (スプレッドシート形式)                    │
│ ┌────┬─────────┬─────────┬─────────┬─────────┐          │
│ │ # │ サムネイル │ タイプ  │ レイヤー │ テキスト │          │
│ ├────┼─────────┼─────────┼─────────┼─────────┤          │
│ │ 1  │ [img]   │ Text    │ Bold    │ 見出し... │          │
│ │ 2  │ [img]   │ Image   │ Layer1  │ -        │          │
│ └────┴─────────┴─────────┴─────────┴─────────┘          │
└──────────────────────────────────────────────────────────┘
```

### Source切り替え

| 旧 | 新 |
|----|-----|
| Web タブ | **テキスト** タブ |
| PDF タブ | **画像** タブ |

### Action欄

- **テキストレイヤー数**: フォントウェイト別
  - Bold (700): N個
  - Regular (400): M個
  - Light (300): K個
- **画像レイヤー数**: 抽出画像数

---

## エクスポート仕様

### 1. PowerPoint (.pptx)

```python
# 座標ベース配置
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank

for block in text_blocks:
    left = Inches(block.bbox[0] / dpi)
    top = Inches(block.bbox[1] / dpi)
    textbox = slide.shapes.add_textbox(left, top, width, height)
    textbox.text_frame.paragraphs[0].text = block.text
```

### 2. Excel (.xlsx)

| 列 | 内容 |
|----|------|
| A | サムネイル画像 |
| B | タイプ (Text/Image) |
| C | レイヤー名 |
| D | テキスト内容 |
| E | 座標 (x, y, w, h) |

レイヤークラスターごとにシート分割。

### 3. CSV

```csv
id,type,layer,text,x,y,width,height
1,text,Bold,"見出しテキスト",100,50,200,30
2,image,Layer1,,300,100,400,300
```

### 4. PNG

各素材を個別PNG画像として出力。

---

## SDK API

### LayerAnalyzer

```python
from app.sdk.storyboard import LayerAnalyzer

analyzer = LayerAnalyzer(layer_result)
stats = analyzer.get_layer_stats()
# {
#   "text_layers": {"Bold": 5, "Regular": 12},
#   "image_layers": 3
# }
```

### LayoutExporter

```python
from app.sdk.storyboard import LayoutExporter

exporter = LayoutExporter(layer_result)
exporter.to_pptx("output.pptx")  # 座標配置再現
exporter.to_excel("output.xlsx") # クラスター別シート
exporter.to_csv("output.csv")
exporter.to_png("output_dir/")
```

### SheetGenerator

```python
from app.sdk.storyboard import SheetGenerator

generator = SheetGenerator(layer_result)
rows = generator.get_sheet_data()
# [{"id": 1, "thumb": PIL.Image, "type": "text", ...}, ...]
```

---

## タスクチェックリスト

### Phase 3.0-A: GUI リデザイン

- [ ] 3パネルレイアウト構築
- [ ] テキスト/画像タブ切り替え
- [ ] Action欄にレイヤー数表示
- [ ] 手動範囲選択 (SelectionMixin統合)
- [ ] 素材シート表示

### Phase 3.0-B: エクスポート拡張

- [ ] PowerPoint座標配置エクスポート
- [ ] Excelクラスター別シート
- [ ] CSVメタデータ出力
- [ ] PNG個別画像出力

### Phase 3.0-C: SDK実装

- [ ] LayerAnalyzer
- [ ] LayoutExporter
- [ ] SheetGenerator

---

## 依存ライブラリ

```bash
pip install python-pptx openpyxl pillow
```

---

Tags: #MEKIKI #StoryboardExtractor #SDK #Runbook #Phase3.0
