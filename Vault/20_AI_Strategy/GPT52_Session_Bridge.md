# GPT-5.2 Session Bridge
>
> **Purpose**: GPT-5.2（外部AI軍師）との戦略共有・Antigravity連携ノート

---

## 現在の問題（2026-01-31）

### 1. Web OCR が0件を返す

- **症状**: `Web: 0 | PDF: 859 | Match: 0`
- **原因**: HybridOCR Engine初期化失敗 → AI Analysis Modeにフォールバック → Web OCRスキップ
- **根本原因**: Cloud Vision API認証エラー

### 2. ~~AI Analysis Mode が自動実行される~~ ✅ 解決済み (2026-02-02検証)

- **期待**: `_run_hybrid_ocr()` → `_run_ocr_analysis()` を呼び出し
- **実際**: ~~起動時に `_run_ai_analysis_mode()` が自動トリガー~~ → 修正済み
- **検証結果**: `__init__`にauto-trigger after()呼び出しなし
- **area_code形式**: `Col0-W1_P-1` (AI Mode) vs `P{page}-{seq}` (Phase 44仕様)

### 3. log_diagnostic 未定義エラー（解決済み）

- キャッシュクリアで解決

---

## GPT-5.2からの戦略指示

### 戦略2: Clawdbot Proxy Server (2026-01-31)

WSLでClawdbotを「モデルの翻訳機」として中間に置く。

**仕組み**:

1. Clawdbot側でGPT-5.2を呼び出すローカルサーバー（LiteLLM）
2. Antigravity側は「ローカルのClawdbot」経由でGPT-5.2へリクエスト

**メリット**:

- Guardrail: 「指示の不履行」を監視してからAntigravityにコード受け渡し
- 監視: リクエスト/レスポンスのログ記録
- 制御: 禁止パターンのフィルタリング

**詳細**: [clawdbot_proxy_architecture.md](../00_Runbook/clawdbot_proxy_architecture.md)

### ⚠️ 注意点: Context Window Management (2026-01-31)

GPT-5.2を接続しても「Antigravity側のContext Window Management設定」が適切でないと、IDE側で勝手に情報を削除（Truncate）してしまう。

**症状**: モデルが最強でも「IDEが情報を渡さない」ために短期記憶化

**解決策**:

```
Antigravityの設定ファイル（user_settings.pb 等）で
max_tokens_per_request をGPT-5.2の限界まで引き上げ
```

**設定ファイル位置**: `C:\Users\raiko\.gemini\antigravity\`

- `user_settings.pb` - ユーザー設定
- `mcp_config.json` - MCP設定

---

## 実装状態

### 修正済み

- [x] `_run_hybrid_ocr` 関数作成 (unified_app.py:905-911)
- [x] ハイブリッドOCRボタンのバインディング修正 (unified_app.py:345)
- [x] `_highlight_with_page_conversion` でpage_id直接使用 (advanced_comparison_view.py:757-772)
- [x] `_update_area_list` 安全チェック追加

### 未解決

- [ ] AI Analysis Mode の自動実行を停止
- [ ] HybridOCR Engine 初期化エラー修正
- [ ] Web OCR結果が0件の原因特定

---

## アクション待ち

1. **GPT-5.2からの戦略貼り付け**
2. **Cloud Vision API credentials確認**
3. **AI Mode自動トリガーの発見・無効化**

---

## 参照ファイル

- [[phase44_perfect_prompt]] - Phase 44仕様
- [[implementation_plan]] - 実装計画
- `app/gui/unified_app.py` - メインアプリ
- `app/gui/windows/advanced_comparison_view.py` - 比較ビュー
