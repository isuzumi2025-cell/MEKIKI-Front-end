---
type: index
status: active
created: 2026-01-27
---

# 🗂️ MEKIKI Knowledge Vault

> **Purpose**: Obsidian Vaultとして構成されたMEKIKIプロジェクトの知識ベース。Antigravity/Claude Codeから参照可能。

## Quick Links

### 📚 Runbook

- [[00_Runbook/mekiki_operations]] - 運用手順

### 🏗️ Projects

- [[10_Projects/mekiki/sdk_hierarchy]] - SDK構成
- [[10_Projects/sitemap_pro/architecture]] - バックエンドAPI
- [[10_Projects/sitemap_pro/design]] - 設計仕様書

### 🎨 Design

- _(Coming soon)_

### 💬 Prompts

- _(Coming soon)_

### 📊 Evals

- _(Coming soon)_

### 📝 Logs

- _(Coming soon)_

---

## Vault Structure

```
Vault/
├── 00_Runbook/          # 運用手順
├── 10_Projects/         # プロジェクト別ドキュメント
│   ├── mekiki/
│   └── sitemap_pro/
├── 20_Design/           # 設計ドキュメント
├── 30_Prompts/          # AIプロンプトテンプレート
├── 40_Evals/            # 評価・ベンチマーク
└── 50_Logs/             # 実行ログ・トレース
```

## Frontmatter Standard

すべてのノートは以下のYAML frontmatterを持つ:

```yaml
---
type: [runbook|design|prompt|eval|log]
project: [mekiki|sitemap_pro|clawdbot]
status: [active|frozen|draft]
tags: [関連タグ]
created: YYYY-MM-DD
---
```
