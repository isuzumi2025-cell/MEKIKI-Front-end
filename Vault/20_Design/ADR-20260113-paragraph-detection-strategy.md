---
type: adr
project: mekiki
status: active
created: 2026-01-13
updated: 2026-01-13
tags: [paragraph, detection, architecture]
---

# ADR-20260113-Paragraph-Detection-Strategy

## Decision
段落検出は「レイアウト＋文脈」ベースで行い、座標クラスタリングとLLMセマンティック分割を併用する。

## Context
- 従来の改行ベース段落検出は精度が不安定
- PDFとWebで段落の表現が異なる
- OCR結果は座標情報を持つが、読み順が崩れやすい

## Options
### A: 改行ベース（シンプル）
- 改行を段落区切りとして使用
- Pros: 実装が簡単
- Cons: 精度が低い

### B: 座標クラスタリング（現状）
- bbox座標で行をグループ化
- Pros: 視覚的レイアウトを反映
- Cons: パラメータ調整が困難

### C: LLMセマンティック分割（採用）
- 全文をLLMに渡し、意味的に段落分割
- Pros: 高精度、言語理解
- Cons: API呼び出しコスト、遅延

### D: ハイブリッド（最終採用）
- 座標クラスタリング + LLMセマンティック分割の2段階
- Web: DOM構造優先 → LLMで補正
- PDF: 座標抽出 → LLMで段落化
- OCR: bbox → 行クラスタリング → LLMで段落化

## Consequences
### Pros
- 高精度（F1 >= 0.80目標）
- 媒体種別に対応可能
- 段階的に改善可能

### Cons
- 実装複雑度が増す
- LLM APIコストが発生

### Mitigations
- ローカルLLM（Ollama）でコスト削減
- キャッシュで重複呼び出し回避
- フォールバックで座標ベースを維持
