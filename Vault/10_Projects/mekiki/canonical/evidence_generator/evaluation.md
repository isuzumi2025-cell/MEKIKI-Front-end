# evidence_generator カプセル化評価

## 概要

- **ファイル**: `app/evidence/generate.py`
- **行数**: 240行
- **評価日**: 2026-01-29

## 機能

Web/PDF差分の視覚的証拠パック生成器

### 主要クラス

- `EvidenceGenerator` - 証拠生成器
- `EvidencePack` - 証拠パックデータクラス

### 主要機能

1. 左右画像切り抜き（マージン付き）
2. オーバーレイ画像生成（差分可視化）
3. メタデータJSON出力

## 使用例

```python
from app.evidence.generate import generate_evidence

pack = generate_evidence(
    issue_id="ISSUE-001",
    run_id="run_123",
    left_image="web.png",
    right_image="pdf.png",
    left_bbox={"x1": 0, "y1": 0, "x2": 100, "y2": 100},
    right_bbox={"x1": 0, "y1": 0, "x2": 100, "y2": 100}
)
```

## 依存

- PIL/Pillow

## 評価

**独立性**: 高 - 単独で動作可能
**再利用性**: 高 - 差分証拠生成に汎用
