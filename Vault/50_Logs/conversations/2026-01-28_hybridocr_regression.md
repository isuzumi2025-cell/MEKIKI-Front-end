---
date: 2026-01-28
conversation_id: b4923d2c-1344-49bc-8606-08d27487c0e4
topic: AI Analysis Mode Regression Fix
outcome: Under Investigation
---

# 2026-01-28: HybridOCR回帰修正

## ユーザー報告 (全記録)

### 15:55 - 第1回テスト後

1. **Webスキャン**: 比較対象が無いのに色分けが表示される
2. **PDFスキャン**: 同様に色分けが表示される
3. **Sync再計算**: マッチ成立するも、シンクロ率が実際と異なる
4. **同一文言問題**: 不一致文言の中に双方同じ文言が含まれている
5. **HybridOCR**: 応答なし頻発、パラグラフ短文化、PDF抽出失敗

### 15:56 - 追加報告

- 画像サイズがおかしい
- PDFが抽出できていない
- 挙動の遅延が顕著

### 16:17 - Phase 1.8復元後テスト

1. **Webスキャン**: 選択範囲パラグラフ抽出完了だが色分け問題継続
2. **PDFスキャン**: 同様
3. **Sync再計算**: Match成立するも比率が実際と異なる
4. **HybridOCR**:
   - 安定抽出できず
   - 応答なし頻発
   - パラグラフ選択範囲がベンチマークより狭い
   - 緑文字と白文字混合 → 緑文字のみ → PDF情報消失
5. **最終状態**: データが表示されていない (大問題)

### 16:40 - Gemini API無効化後テスト

1. **HybridOCR処理後**: 挙動が安定しない
2. **表示データ**: シートから消失
3. **画像サイズ**: 壊れた
4. **統計**: Web:601, PDF:740, Match:487 だがシート空

**結論**: Gemini API無効化だけでは不十分。根本的な問題が別にある。

## 根本原因調査

### 発見: SemanticDiff でGemini API使用

`app/sdk/similarity/semantic_diff.py` がGemini APIを呼び出している:

- L46-48: `GeminiClient` 初期化
- L88-89: `self.client.generate(prompt)` 呼び出し

これが **応答なし・遅延** の原因。

### 発見: AdvancedComparisonView でもGemini使用

`app/gui/windows/advanced_comparison_view.py` L3422 でGemini呼び出し。

## 次のアクション

- [x] SemanticDiff のGemini呼び出しを無効化 (16:23)
- [x] GeminiClient のgenerate()を無効化 (16:23)
- [x] app/config.py 作成 (DISABLE_GEMINI_API=True)
- [ ] 色分け問題の原因特定 (検証中)

## 実装完了

### 16:23 - Gemini API グローバル無効化

```python
# app/config.py
DISABLE_GEMINI_API = True
USE_HYBRID_OCR = False
```

修正ファイル:

- `app/config.py` (新規作成)
- `app/sdk/similarity/semantic_diff.py`
- `app/sdk/llm/client.py`

Tags: #Log #Regression #Investigation #UserFeedback
