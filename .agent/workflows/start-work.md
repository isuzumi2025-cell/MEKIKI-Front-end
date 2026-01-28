---
description: 作業開始時の必須Obsidian参照・自律行動ワークフロー
version: 2.0.0
---

# /start-work ワークフロー

> **目的**: Claude Opus 4.5の短期記憶限界を補完し、ずさん処理を防止する

// turbo-all

---

## Phase 1: 強制参照（省略禁止）

### 1.1 自律行動フレームワーク確認

```
view_file c:\Users\raiko\OneDrive\Desktop\26\OCR\Vault\00_Runbook\autonomous_behavior_framework.md
```

### 1.2 メソドロジー参照

```
view_file c:\Users\raiko\OneDrive\Desktop\26\OCR\Vault\00_Runbook\autonomous_methodology.md
```

### 1.3 過去インシデント確認

```
list_dir c:\Users\raiko\OneDrive\Desktop\26\OCR\Vault\50_Logs\incidents
```

### 1.4 バックアップカタログ確認

```
view_file c:\Users\raiko\OneDrive\Desktop\26\OCR\Vault\10_Projects\mekiki\backup_catalog.md
```

---

## Phase 2: 質問フェーズ（必須）

**以下を自問し、不明点があれば必ずユーザーに質問：**

1. タスクの範囲は明確か？
2. 優先順位は理解したか？
3. 用語の解釈に曖昧さはないか？
4. 完了基準は明確か？

```python
# 質問がある場合
notify_user(
    BlockedOnUser=True,
    Message="以下の点を確認させてください:\n1. ...\n2. ..."
)
```

---

## Phase 3: 全対象リストアップ（部分着手禁止）

**調査タスクの場合：**

```powershell
Get-ChildItem -Directory | Where-Object { $_.Name -match "OCR|backup|Legacy" }
```

**全対象をリストにして、進捗率を報告できる状態にしてから着手**

---

## Phase 4: Clawdbot通知

```python
from app.sdk.notification.clawdbot_client import get_clawdbot_client
client = get_clawdbot_client()
client.send_message("#mekiki-ops", """🚀 [Antigravity] 作業開始
📋 タスク: [タスク名]
📊 対象数: [N]件
🎯 完了基準: [明確な基準]""")
```

---

## Phase 5: 計画書作成 → ユーザー承認

1. implementation_plan.md に計画記載
2. notify_user で承認依頼
3. 承認後に実装開始

---

## ⚠️ 禁止事項

- Phase 1-2を省略すること
- 質問せずに曖昧なまま進行すること
- 「代表的なサンプルで十分」という判断
- 部分完了を「完了」と報告すること
- 定量情報なしの進捗報告

---

## 参照

- `Vault/00_Runbook/autonomous_behavior_framework.md`
- `SKILL.md` v2.2.0
- `Vault/50_Logs/incidents/`
