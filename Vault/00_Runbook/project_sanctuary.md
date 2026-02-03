# MEKIKI Project Sanctuary - 聖域定義書
>
> **Purpose**: 全エージェント共通の「触ってはいけない聖域」と「絶対ルール」  
> **Status**: Active - 全セッション開始時に必ず参照

---

## 🚨 必読: エージェントへの強制リセット命令

**記憶が飛んだ場合**: このファイルを再読してから作業を再開すること。

---

## 1. 聖域リスト（触るな危険）

### 絶対不可侵ファイル

| パス | 理由 |
|------|------|
| `.env` | APIキー格納 - 絶対に削除・上書きしない |
| `Vault/00_Runbook/*` | 運用ルールの正本 |
| `credentials.json` | Google Cloud認証 |
| `.antigravityrules` | エージェント行動規範 |

### 慎重操作ファイル（変更前に必ず確認）

| パス | 理由 |
|------|------|
| `app/gui/unified_app.py` | メインアプリ - 1700行超のモノリス |
| `app/gui/windows/advanced_comparison_view.py` | 比較ビュー - 4700行超 |
| `app/core/ocr_engine.py` | Cloud Vision API連携 |

---

## 2. 現在の最優先課題

### Phase 44: 非対称混合モード

- **目標**: Web/PDF間の正確なマッチングと表示
- **area_code形式**: `P{page}-{seq}` (Web), `PDF-{seq}` (PDF)
- **座標系**: ページ相対座標

### 未解決バグ

1. ~~HybridOCR Engine初期化失敗~~ → ✅ 修正済み (Phase 139: 並列処理対応)
2. AI Analysis Mode自動トリガー → `_run_ai_analysis_mode`が呼ばれる
3. ~~Web OCR 0件~~ → ✅ HybridOCR修正で解決

### 新規追加機能 (Phase 140-142)

- `orchestra.py`: マルチエージェント議論システム (GPT/Gemini/Obsidian/Slack)
- `auto_assist.py`: 自律コンテキスト検索
- Producer-Reviewer パターン: GPT→Gemini相互レビュー
- HybridOCR並列処理: ThreadPoolExecutorで4x高速化
- **[NEW]** `slack_bidirectional.py`: Slack双方向連携（遠隔表示/コマンド入力/調査結果配信）
- **[NEW]** `ab_test_framework.py`: Antigravity vs Clawdbot A/Bテスト
- **[NEW]** `slack_listener.py`: コマンド受信リスナー ✅ 動作確認済み
- **[NEW]** [[slack_commands]]: Slackコマンドリファレンス（10コマンド対応）
- **[NEW]** [[orchestra_system]]: Orchestra System仕様書

---

## 3. アーキテクチャ命令

### 3.1 コード修正時の必須チェック

```bash
# 変更前に必ず実行
python -m py_compile <target_file>

# 型チェック（利用可能な場合）
mypy <target_file> --ignore-missing-imports
```

### 3.2 禁止事項

- ❌ 既存関数の削除（必ず非推奨→移行→削除の順）
- ❌ 変数名の一括置換（影響範囲を確認してから）
- ❌ importの削除（未使用に見えても将来使用の可能性）

### 3.3 推奨事項

- ✅ 新機能は新ファイルに分離
- ✅ 変更箇所にコメントで日付と理由を記載
- ✅ 大規模変更前にバックアップ作成

---

## 4. エージェント間連携プロトコル

```
[Obsidian] ──読取─→ [Antigravity/Claude]
     ↓                      ↓
  正本管理              コード実装
     ↓                      ↓
[GPT-5.2 Bridge] ←─相談─→ [検証・テスト]
     ↓                      ↓
  戦略立案              Slack報告
```

### 責務分担

| エージェント | 役割 | 制限 |
|--------------|------|------|
| Antigravity (Claude) | コード実装・デバッグ | 聖域ファイル変更禁止 |
| GPT-5.2 | 戦略立案・アーキテクチャ | 直接コード変更禁止 |
| Clawdbot (WSL) | オーケストレーション | 監視・承認フロー |

---

## 5. 緊急時プロトコル

### 破壊検知時

1. 即座に `git stash` で変更を退避
2. このファイルを再読
3. `Vault/30_Incidents/` に障害報告を作成
4. 元の問題に戻る前にアーキテクチャ確認

### セッション再開時

1. このファイルを読む
2. `task.md` の進捗を確認
3. 未完了タスクから再開

---

**最終更新**: 2026-01-31  
**次回レビュー**: 重大なアーキテクチャ変更時
