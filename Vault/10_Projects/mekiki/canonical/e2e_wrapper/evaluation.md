# e2e_wrapper カプセル化評価

## 概要

- **場所**: `app/core/e2e_wrapper/`
- **ファイル数**: 4
- **評価日**: 2026-01-29

## モジュール構成

| ファイル | 行数 | 機能 |
|----------|------|------|
| runner.py | ~420 | E2Eテストランナー |
| processor.py | ~400 | プロセッサ |
| dom_handler.py | ~400 | DOM処理 |
| capture.py | ~280 | キャプチャ |

## 使用例

```python
from app.core.e2e_wrapper import E2ERunner

runner = E2ERunner()
result = runner.execute(test_case)
```

## 評価

**独立性**: 中 - Selenium/Playwright依存
**再利用性**: 高 - E2Eテストフレームワーク
