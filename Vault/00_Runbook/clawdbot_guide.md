# Clawdbot使用ガイド

**目的**: Slack通知の送信

---

## クイックスタート

```python
from app.sdk.notification.clawdbot_client import notify_slack

# メッセージ送信
notify_slack("🔧 作業開始: HybridOCR修正")

# チャンネル指定
notify_slack("完了！", channel="context")
```

---

## 詳細な使い方

### SlackNotificationClientクラス

```python
from app.sdk.notification.clawdbot_client import SlackNotificationClient

client = SlackNotificationClient()

# 可用性チェック
if client.is_available():
    # メッセージ送信
    client.send_message("context", "Hello from MEKIKI!")
    
    # スレッド返信
    client.send_message("context", "返信です", thread_ts="1234567890.123")
    
    # ファイルアップロード
    client.upload_file("context", "report.xlsx", comment="レポート")
```

---

## 設定

### トークン保存場所

WSL: `/home/raiko/.clawdbot/clawdbot.json`

```json
{
  "channels": {
    "slack": {
      "botToken": "xoxb-xxxxx"
    }
  }
}
```

---

## 開発ワークフロー統合

### 作業開始通知

```python
notify_slack("🚀 タスク開始: {task_name}")
```

### 作業完了通知

```python
notify_slack("✅ 完了: {task_name}\n結果: Web {count}件抽出")
```

### エラー通知

```python
notify_slack("❌ エラー: {error_message}")
```

---

## 参照

- [clawdbot_client.py](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/app/sdk/notification/clawdbot_client.py)
