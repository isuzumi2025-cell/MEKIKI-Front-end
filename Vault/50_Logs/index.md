---
type: index
project: mekiki
status: active
tags: [logs, conversation, antigravity, history]
---

# 会話ログ (Conversation Logs)

> **目的**: Antigravity/ClaudeCode との会話履歴を保存し、システム全体の合理性を検証する

## 構造

```
50_Logs/
├── index.md              # このファイル
├── conversations/        # 会話別ログ
│   └── YYYY-MM-DD_topic.md
├── decisions/            # 重要な意思決定記録
│   └── YYYY-MM-DD_decision.md
└── incidents/            # インシデント対応記録
    └── YYYY-MM-DD_incident.md
```

## ログ記録ポリシー

### 必須記録項目

| 項目 | 内容 |
|------|------|
| 日時 | ISO 8601形式 |
| Conversation ID | Antigravity session ID |
| 目的 | 何を達成しようとしたか |
| 決定事項 | 合意した内容 |
| 次のアクション | TODO化すべき項目 |

### 参照元

- **Antigravity Brain**: `C:\Users\raiko\.gemini\antigravity\brain\{conversation-id}\`
- **Knowledge Items**: `C:\Users\raiko\.gemini\antigravity\knowledge\`
- **Vault Runbook**: `00_Runbook/`

## ログ活用

1. **実装前**: 過去の類似タスクを検索
2. **設計時**: 意思決定の履歴を参照
3. **デバッグ時**: インシデント記録を確認
4. **振り返り**: 効率改善ポイントを抽出

Tags: #Logs #ConversationHistory #Antigravity #MEKIKI
