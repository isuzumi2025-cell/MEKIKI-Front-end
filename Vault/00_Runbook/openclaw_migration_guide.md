# OpenClaw vs Clawdbot 比較・導入ガイド

> **作成日**: 2026-02-03  
> **目的**: デバッグ・リサーチ遠隔連携のためのOpenClaw導入検討

---

## 📊 エグゼクティブサマリー

| 項目 | Clawdbot (現行) | OpenClaw (後継) |
|------|-----------------|-----------------|
| **ステータス** | 安定・運用中 | 活発開発中 |
| **主機能** | Slack通知、GPT-5.2連携 | 自律タスク実行、マルチプラットフォーム |
| **自己増殖** | なし | あり（設定で制御可） |
| **リスク** | 低 | 中（設定次第） |
| **推奨** | 維持 | 段階的並行導入 |

---

## 🔄 進化の経緯

```
Clawdbot (2025.11)
    │ Anthropic商標要請
    ▼
Moltbot (2025.12)
    │ 最終リブランド
    ▼
OpenClaw (2026.01)  ← 現在の最新版
```

---

## ⚖️ 機能比較

### 現在のClawdbot構成 (MEKIKI)

```
app/sdk/notification/
├── clawdbot_client.py      # Slack通知
└── slack_bidirectional.py  # 双方向Slack
```

| 機能 | 実装状況 |
|------|----------|
| Slack通知 | ✅ 動作中 |
| GPT-5.2連携 | ✅ LiteLLM Proxy経由 |
| Guardrail | ⏳ 計画中 |
| 自律タスク実行 | ❌ なし |

### OpenClawの追加機能

| 機能 | 説明 | リスク |
|------|------|--------|
| **Auto-spawn** | Daemonが自動起動 | 低 |
| **Self-building Skills** | API学習して自動スキル作成 | **中** |
| **Agent Orchestration** | サブエージェントのspawn/管理 | **高** |
| **Multi-platform** | WhatsApp/Telegram/Discord対応 | 低 |
| **Brain Router** | セッション・権限管理 | 低 |

---

## ⚠️ 懸念事項と対策

### 自己増殖機能の詳細

OpenClawの「自己増殖」は2種類あります：

#### 1. Auto-spawn Mode (デフォルト)

- Daemonプロセスの自動起動
- **リスク: 低** - 単なるプロセス管理

#### 2. Agent Orchestration (オプション)

- タスクをサブタスクに分解し、子エージェントを生成
- **リスク: 高** - リソース競合、コスト増

### 無効化設定

```json
// ~/.openclaw/openclaw.json
{
  "daemon": {
    "auto_spawn": false  // Auto-spawnを無効化
  },
  "skills": {
    "agent_orchestration": {
      "enabled": false   // 子エージェント生成を無効化
    },
    "self_building": {
      "enabled": false   // 自動スキル作成を無効化
    }
  },
  "limits": {
    "max_concurrent_tasks": 1,
    "max_api_calls_per_task": 10,
    "timeout_seconds": 60
  }
}
```

---

## 🎯 MEKIKI統合における影響分析

### プラス面

| 項目 | 現状 | OpenClaw導入後 |
|------|------|---------------|
| **デバッグ支援** | 手動 | 遠隔自動診断可能 |
| **リサーチ連携** | Grok単体 | マルチプラットフォーム並列調査 |
| **Obsidian連携** | 読み取りのみ | 双方向同期可能 |
| **通知** | Slackのみ | Telegram/Discord追加可 |

### マイナス面（リスク）

| リスク | 発生条件 | 軽減策 |
|--------|----------|--------|
| **リソース競合** | Agent Orchestration有効時 | `enabled: false` で無効化 |
| **API コスト増** | 自律タスクの過剰実行 | `max_api_calls` 制限 |
| **コンテキスト分散** | 複数子エージェント生成時 | 単一エージェントモード使用 |
| **セキュリティ** | 深いシステムアクセス | Permission制限、Guardrail維持 |

---

## 📋 段階的導入プラン

### Phase 0: 並行運用準備 (推奨開始点)

```bash
# WSLでOpenClawをインストール（Clawdbotと別環境）
pip install openclaw

# 設定ファイル作成（制限付き）
cat > ~/.openclaw/openclaw.json << 'EOF'
{
  "daemon": {"auto_spawn": false},
  "skills": {
    "agent_orchestration": {"enabled": false},
    "self_building": {"enabled": false}
  },
  "channels": {
    "slack": {"botToken": "YOUR_EXISTING_TOKEN"}
  }
}
EOF
```

### Phase 1: 読み取り専用テスト

| タスク | 詳細 |
|--------|------|
| Obsidian検索 | クエリテスト |
| Slack読み取り | メッセージ取得テスト |
| ログ監視 | 挙動確認 |

### Phase 2: 制限付きデバッグ連携

```python
# 制御された呼び出し例
from openclaw import OpenClaw

claw = OpenClaw(
    mode="restricted",
    max_api_calls=5,
    allow_spawn=False
)

# デバッグ診断（読み取り専用）
result = claw.diagnose("HybridOCR coordinate mismatch")
```

### Phase 3: 本格統合判断

Phase 2完了後、以下を評価：

- [ ] API使用量は許容範囲内か
- [ ] レスポンス品質は十分か
- [ ] 既存ワークフローとの干渉はないか

---

## 🛡️ 既存フレームワークとの統合

現在のMEKIKI Orchestra Systemは維持しつつ、OpenClawを**追加レイヤー**として導入：

```
┌─────────────────────────────────────────────────────────────┐
│                 MEKIKI Orchestra System (維持)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────┐    ┌───────────┐    ┌───────────────────┐   │
│  │Antigravity│◄──►│ Clawdbot  │◄──►│     Slack         │   │
│  │ (Claude)  │    │ (維持)     │    │     (双方向)      │   │
│  └───────────┘    └───────────┘    └───────────────────┘   │
│        │                                                    │
│        │ ★ 新規追加                                         │
│        ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  OpenClaw (制限付きモード)                           │   │
│  │  - デバッグ診断のみ                                  │   │
│  │  - 自己増殖: 無効                                    │   │
│  │  - リサーチ支援                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ 結論と推奨

### 推奨アプローチ

1. **Clawdbotは維持** - 現行のSlack通知・Orchestra Systemは変更しない
2. **OpenClawは制限付き並行導入** - 自己増殖機能を無効化した状態でテスト
3. **段階的評価** - Phase毎にリスクと効果を評価

### 導入判断基準

| 条件 | 本格導入 | 並行運用維持 | 見送り |
|------|----------|-------------|--------|
| API使用量 | 許容範囲内 | やや超過 | 大幅超過 |
| 品質 | 期待以上 | 期待通り | 期待以下 |
| 安定性 | 問題なし | 軽微な問題 | 重大な問題 |
| 干渉 | なし | 軽微 | 重大 |

---

## 📚 参照

- [Clawdbot使用ガイド](clawdbot_guide.md)
- [Clawdbot Proxy Architecture](clawdbot_proxy_architecture.md)
- [Orchestra System](orchestra_system.md)
- [自律行動フレームワーク](autonomous_behavior_framework.md)
- [OpenClaw公式ドキュメント](https://openclaw.ai/docs)
- [OpenClaw GitHub](https://github.com/psteinberger/openclaw)

---

Tags: #OpenClaw #Clawdbot #Migration #MEKIKI #Orchestra
