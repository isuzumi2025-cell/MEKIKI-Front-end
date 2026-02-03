# MEKIKI Slack Commands Reference

> **Version**: 2.0  
> **Last Updated**: 2026-01-31

---

## 概要

`@mekiki` または `＠mekiki`（全角）でBotに指示を送信できます。

---

## 基本コマンド

| コマンド | 説明 |
|---------|------|
| `@mekiki help` | このヘルプを表示 |
| `@mekiki ping` | 疎通確認（Pong!と返信） |
| `@mekiki status` | 現在の状態を表示 |
| `@mekiki echo <text>` | テキストをそのまま返信 |

---

## 情報コマンド

| コマンド | 説明 |
|---------|------|
| `@mekiki time` | 現在時刻を表示 |
| `@mekiki version` | バージョン情報を表示 |
| `@mekiki uptime` | 稼働時間を表示 |
| `@mekiki info` | システム情報を表示 |

---

## ツールコマンド

| コマンド | 説明 |
|---------|------|
| `@mekiki tasks` | 現在のタスク一覧 |
| `@mekiki obsidian` | Obsidian参照リンク |
| `@mekiki search <query>` | Web検索（準備中） |
| `@mekiki orchestra <task>` | 🎭 Orchestra議論依頼 |

---

## 使用例

```
@mekiki ping
→ 🏓 Pong! (23:05:24)

@mekiki uptime
→ ⏱️ 稼働時間: 0時間 15分 32秒

@mekiki echo Hello World
→ 📢 Hello World
```

---

## 技術情報

- **ファイル**: `app/sdk/notification/slack_listener.py`
- **チャンネル**: #context
- **全角対応**: `＠mekiki` も検出可能
- **ポーリング間隔**: 5秒
