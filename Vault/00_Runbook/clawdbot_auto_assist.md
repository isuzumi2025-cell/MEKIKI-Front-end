# Clawdbot 自律アシスト機能

**作成日**: 2026-01-31  
**目的**: 作業開始前に関連コンテキストを自動収集し、Slack/Antigravityに告知

---

## 概要

Clawdbotが自律的に以下を実行:

1. **問題からキーワード抽出**
2. **Vault/KI検索**
3. **Slack通知**
4. **Antigravityへのブリーフィング提供**

---

## 使い方

### コマンドライン

```bash
python -m app.sdk.notification.auto_assist "canvas thumbnail error"
```

### Python

```python
from app.sdk.notification.auto_assist import auto_assist

# 自動でSlack通知 + コンテキスト生成
context = auto_assist("画像リンクが不安定")
print(context)
```

---

## モジュール構成

| ファイル | 役割 |
|----------|------|
| `context_search.py` | Vault/KI検索 |
| `auto_assist.py` | 自律アシストオーケストレーション |
| `clawdbot_client.py` | Slack通知 |

---

## 出力例

```
============================================================
🤖 CLAWDBOT AUTO-ASSIST BRIEFING
============================================================
Time: 2026-01-31T13:10:00
Problem: canvas thumbnail error

📚 RECOMMENDED READING (before making changes):
  - Vault/10_Projects/mekiki/specs/thumbnail_canvas_link.md

📁 VAULT CONTEXT:
  [10_Projects/mekiki/specs/thumbnail_canvas_link.md]
    > サムネイル→Canvas連動仕様

🧠 KNOWLEDGE ITEMS:
  [multimodal_proofing_system]
    Section 19: Safe UI Update Pattern...

⚠️ WARNINGS:
  ⚠️ 慎重操作ファイル検出: advanced_comparison_view.py
============================================================
```

---

## 統合方法

### Antigravity ワークフロー

`.agent/workflows/start-work.md` で自動呼び出し:

```bash
python -m app.sdk.notification.auto_assist "ユーザーの問題"
```

### 今後の拡張

- [ ] GPT-5.2 Proxy経由での戦略相談
- [ ] 過去の会話ログ検索
- [ ] インシデント自動参照

---

Tags: #Clawdbot #DevTools #Automation #MEKIKI
