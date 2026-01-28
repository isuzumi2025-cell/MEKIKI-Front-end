# LegacyOCR 評価レポート

**評価日**: 2026-01-28
**評価者**: Antigravity + MEKIKI Operations Skill v2.1.0

---

## 概要

LegacyOCRは**現行MEKIKIとは別のCLIプロジェクト**。
広告チラシ向けOCRパイプラインを持つ。

## 構造

```
LegacyOCR/
├── app/
│   ├── ocr/vision.py       # Vision API ラッパー (191行)
│   ├── pipeline/
│   │   ├── paragraph.py    # 段落クラスタリング (257行) ★重要
│   │   └── normalize.py    # 正規化処理
│   └── japanese/checker.py # 日本語チェック
```

## 🎯 現行版にない機能

### 1. ロール推定 (`estimate_role`)

```python
# 段落ロール: headline, body, caption, price, legal
def estimate_role(cluster, avg_font_size, ...):
    if cluster_font_size >= avg_font_size * headline_size_ratio:
        return "headline"
    # 規約キーワードチェック
    legal_keywords = ["規約", "注意", "※", "条項", "免責"]
    if any(keyword in text for keyword in legal_keywords):
        return "legal"
    # 価格判定
    if digit_count / len(text) >= price_digit_ratio:
        return "price"
    return "body"
```

### 2. 3段階パイプライン

1. **Step A**: `normalize_ocr_elements` - 座標ソート、行推定、空白推定
2. **Step B**: `cluster_paragraphs` - 近接×整列×サイズでクラスタリング
3. **Step C**: `estimate_role` - ロール推定

### 3. クリーンなVision APIラッパー

- シリアライズ可能な辞書形式で出力
- 認証方法の複数サポート（サービスアカウント、APIキー、デフォルト）

## 推奨アクション

| 機能 | 優先度 | アクション |
|------|--------|----------|
| ロール推定 | **高** | 現行版に移植検討 |
| 3段階パイプライン | 中 | 参考設計として記録 |
| Vision APIラッパー | 低 | 現行版で同等機能あり |

## 結論

> LegacyOCRには**現行版にない貴重なロール推定機能**あり
> canonical/ に登録して移植候補とする
