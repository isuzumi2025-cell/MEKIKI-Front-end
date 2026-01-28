# cluster_matcher カプセル化評価

## 概要

- **場所**: `app/core/cluster_matcher/`
- **ファイル数**: 7
- **評価日**: 2026-01-29

## モジュール構成

| ファイル | 行数 | 機能 |
|----------|------|------|
| anchor_matcher.py | ~300 | アンカーマッチング |
| cross_aligner.py | ~340 | クロスアライメント |
| layout_detector.py | ~250 | レイアウト検出 |
| syntax_matcher.py | ~290 | 構文マッチング |
| selection_simulator.py | ~300 | 選択シミュレーション |
| image_comparator.py | ~170 | 画像比較 |
| range_optimizer.py | ~300 | 範囲最適化 |

## 使用例

```python
from app.core.cluster_matcher import CrossAligner, LayoutDetector

aligner = CrossAligner()
detector = LayoutDetector()
```

## 評価

**独立性**: 中 - 相互依存あり
**再利用性**: 高 - テキストマッチングに汎用
