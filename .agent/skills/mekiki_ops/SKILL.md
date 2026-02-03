---
name: MEKIKI Operations
description: Claude Opus 4.5の自律行動支援、改善計画、精度検証、統合最適化スキル
version: 2.3.0
---

# MEKIKI Operations Skill

## 概要

MEKIKIプロジェクトの自律運用を支援するスキル。以下のタスクを実行可能。

## ⚠️ Pre-flight Check（全タスク共通・必須）

> **全タスク開始前に以下を実行すること**

### 必須参照（省略禁止）

1. `Vault/00_Runbook/project_sanctuary.md` 📛 **聖域定義書** ★PRIORITY
2. `Vault/00_Runbook/autonomous_behavior_framework.md`
3. `Vault/00_Runbook/autonomous_methodology.md`
4. `Vault/10_Projects/mekiki/backup_catalog.md` 確認
5. `Vault/50_Logs/incidents/` 過去インシデント確認
6. Clawdbot通知（作業開始）
7. 計画書作成 → ユーザー承認

### 静的解析ゲート（コード変更前必須）★NEW

```bash
# Python文法チェック
python -m py_compile <target_file>

# 型チェック（推奨）
mypy <target_file> --ignore-missing-imports 2>/dev/null || echo "mypy not installed"

# 禁止パターン検出
grep -n "import \*" <target_file> && echo "⚠️ ワイルドカードimport検出"
```

### GPT-5.2 戦略相談（複雑なタスク時）★NEW

```python
from app.utils.gpt_bridge import consult_gpt_strategist
response = consult_gpt_strategist("問題の説明をここに")
```

**ワークフロー**: `/start-work` v2.0.0 で自動実行

---

## 🧠 自律行動ルール（Claude Opus 4.5サポート）★NEW

> **目的**: 短期記憶の限界とずさん処理を自律的に補完する

### 強制行動

| 状況 | 必須アクション |
|------|--------------|
| タスク開始時 | Obsidian参照（省略禁止） |
| 範囲が曖昧 | **必ず質問**してから着手 |
| 用語不明確 | **必ず質問**して確認 |
| 調査タスク | **全対象リストアップ**してから着手 |
| 進捗報告 | **定量的**に報告（N/M形式） |
| エラー発生 | 即座にユーザー通知 |
| 完了報告 | 未調査項目を明示 |

### 質問義務

以下の場合は**作業前に必ず質問**：

```
1. 「全部」「すべて」の範囲が不明確
2. 優先順位が指定されていない
3. 専門用語の解釈が複数ありうる
4. 完了基準が明示されていない
```

### 自己監査チェックリスト

タスク終了前に自問：

```
□ ユーザーの全要求に応えたか？
□ 全対象をカバーしたか？
□ 不明点を質問したか？
□ 定量的進捗を報告できるか？
□ Obsidianに記録したか？
□ インシデントがあれば記録したか？
```

---

## 🚫 アンチパターン防止（必須）

> **2026-01-28 インシデント**: 22バックアップ中3つしか調査せず「完了」と報告

### 調査タスクの必須ルール

1. **全対象をリストアップしてから着手**

   ```powershell
   Get-ChildItem -Directory | Where-Object { $_.Name -match "OCR|backup|Legacy" }
   ```

2. **定量的進捗を報告** (例: 「3/22完了 = 14%」)

3. **未調査項目がある場合は「完了」と報告しない**

4. **インシデント記録**: `Vault/50_Logs/incidents/` に反省点を記載

### 違反時のアクション

- 即座にユーザーに謝罪
- 全対象リストを作成
- 進捗率を再計算して報告

---

## 対応タスク

### 1. 自律的改善計画 (Autonomous Improvement)

**トリガー**: 「改善計画を作成」「最適化提案」

**手順**:

1. `Vault/00_Runbook/` から現行仕様を参照
2. `Vault/50_Logs/` から過去の問題を検索
3. 改善オプションを3つ以上提示
4. ユーザー承認後に実装

### 2. A/Bテスト・精度検証 (Accuracy Verification)

**トリガー**: 「精度比較」「ABテスト」「バックアップと比較」

**手順**:

1. 安定版バックアップを特定 (`OCR_backup_*`)
2. 同一入力データで両バージョンを実行
3. 定量指標を記録:
   - Match数
   - Sync Rate (%)
   - 処理時間 (秒)
   - パラグラフ検出数
4. 結果を `Vault/40_Evals/` に保存

### 3. 統合最適化計画 (Integration Optimization)

**トリガー**: 「統合最適化」「フロント/バックエンド連携」

**手順**:

1. `sitemap_pro/` バックエンド状態確認
2. `app/gui/` フロントエンド依存関係分析
3. ボトルネック特定
4. 最適化計画書作成 → 承認依頼

### 4. タスク申し送り (Remote Handoff)

**トリガー**: 「申し送り作成」「ハンドオフ」

**手順**:

1. 現在の作業状態をサマリ
2. 未完了タスクをリスト化
3. `Vault/50_Logs/decisions/` に意思決定記録
4. Clawdbot経由でSlack通知

### 5. Obsidian情報精査 (Knowledge Curation)

**トリガー**: 「情報整理」「ナレッジ更新」

**手順**:

1. Vault内の重複・矛盾を検出
2. 古い情報をアーカイブ (`99_Archive/`)
3. インデックス更新

### 6. バックアップ評価 (Backup Evaluation) ★NEW

**トリガー**: 「バックアップ評価」「最良実装特定」

**手順**:

1. 全バックアップをスキャン (`Desktop/26/OCR_backup_*`, `LegacyOCR`)
2. 機能別にコードを抽出:
   - サムネイル生成
   - Canvas選択範囲
   - Source連動
   - テキスト抽出
   - 差分ハイライト
3. 評価基準で採点:
   - 動作確実性 (40%)
   - コード簡潔性 (20%)
   - エラーハンドリング (20%)
   - 整合性 (20%)
4. Top5を `Vault/10_Projects/mekiki/backup_registry.md` に記録
5. 最良を `Vault/10_Projects/mekiki/canonical/` にコピー

### 7. 正本登録 (Canonical Registration) ★NEW

**トリガー**: 「正本登録」「canonical登録」

**手順**:

1. 最良実装ファイルを特定
2. `Vault/10_Projects/mekiki/canonical/` にコピー
3. 変更履歴を記録
4. 現行コードとの差分を生成
5. ユーザー承認後に本番反映

### 8. 会話ログマイニング (Conversation Mining) ★NEW

**トリガー**: 「過去会話検索」「ログマイニング」

**手順**:

1. `.gemini/antigravity/brain/*/` をスキャン
2. 関連キーワードで検索
3. 過去の意思決定・成功パターンを抽出
4. `Vault/50_Logs/` に統合

---

## 自動化ポリシー

| 操作 | 自動/承認 |
|------|-----------|
| Obsidian読み取り | 自動 |
| Obsidianログ書き込み | 自動 |
| Clawdbot通知 | 自動 |
| バックアップ評価 | 自動 |
| canonical登録 | **承認必須** |
| コード変更 | **承認必須** |
| 設計変更 | **承認必須** |

---

## 参照

- `Vault/00_Runbook/autonomous_methodology.md`
- `Vault/00_Runbook/mekiki_operations.md`
- `Vault/10_Projects/mekiki/backup_registry.md`
- `Vault/10_Projects/mekiki/canonical/`
- `RUNBOOK_ADDITION_v1.md` Section 8
