# multi_model_advisor カプセル化評価

## 概要

- **ファイル**: `app/agents/multi_model_advisor.py`
- **行数**: 172行
- **評価日**: 2026-01-29

## 機能

Claude + Geminiのマルチモデル意見比較ユーティリティ

### 主要クラス

- `MultiModelAdvisor` - マルチモデルアドバイザー
- `Opinion` - 意見データクラス

### 主要機能

1. Claude意見取得（主体）
2. Gemini意見取得（参考）
3. 比較結果フォーマット

## 使用例

```python
from app.agents.multi_model_advisor import MultiModelAdvisor

advisor = MultiModelAdvisor()
result = advisor.compare(question, claude_opinion)
print(advisor.format_comparison(result))
```

## 依存

- anthropic
- google-generativeai

## 評価

**独立性**: 高 - 単独で動作可能
**再利用性**: 高 - 意思決定支援ツール
