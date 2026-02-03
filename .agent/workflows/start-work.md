---
description: 作業開始時の必須Obsidian参照・自律行動ワークフロー
---

# /start-work - 作業開始ワークフロー

> **目的**: Myopic改変を防止し、関連コンテキストを自動収集してから作業開始

---

## 1. Obsidian必須参照（自動実行）

// turbo-all

```bash
# Project Sanctuaryを読む（聖域・禁止事項確認）
cat Vault/00_Runbook/project_sanctuary.md
```

```bash
# 未解決バグリストを確認
grep -r "未解決\|TODO\|FIXME" Vault/00_Runbook/ --include="*.md" | head -20
```

---

## 2. コンテキスト自動検索

問題に関連するドキュメントを検索:

```bash
python -c "from app.sdk.notification.context_search import assist_with_context; print(assist_with_context('ユーザーの問題キーワード'))"
```

---

## 3. GPT-5.2 Session Bridge確認

```bash
cat Vault/20_AI_Strategy/GPT52_Session_Bridge.md
```

戦略指示があれば従う。

## 3.5. Orchestra System確認

```bash
# Orchestra System仕様を確認
cat Vault/00_Runbook/orchestra_system.md
```

自律運用ガイドラインに従う。

---

## 4. Knowledge Items (KI) 確認

関連KIがあれば読む:

- `C:\Users\raiko\.gemini\antigravity\knowledge\`

---

## 5. 作業開始チェックリスト

作業開始前に以下を確認:

- [ ] project_sanctuary.md を読んだ
- [ ] 関連コンテキストを検索した
- [ ] 過去の類似インシデントを確認した
- [ ] 変更対象が「慎重操作ファイル」か確認した

---

## 6. 完了報告

作業完了時はClawdbotに通知:

```python
from app.sdk.notification.clawdbot_client import notify_slack
notify_slack("✅ [Antigravity] タスク完了: {タスク名}\n結果: {定量的結果}")
```
