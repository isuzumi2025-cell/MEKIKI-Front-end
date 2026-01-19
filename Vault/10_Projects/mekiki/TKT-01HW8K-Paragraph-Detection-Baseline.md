---
type: ticket
project: mekiki
status: active
created: 2026-01-13
updated: 2026-01-13
tags: [paragraph, detection, f1, evaluation]
---

# TKT-01HW8K-Paragraph-Detection-Baseline

## Problem
長文比較のためのパラグラフ自動検出が不安定で、Web/PDFの段落対応付けが崩れる。

## Context
- 媒体: PDF（座標付きテキスト）、Web（DOM構造）、OCR（画像）
- 現状パイプライン: OCRクラスタリング → 全文比較 → LLMパラグラフ生成
- 再現手順: AI分析モード実行時、Web Textが空になるケースあり

## Constraints
- 処理時間: 1ページあたり5秒以内
- 精度: Boundary F1 >= 0.80
- 互換: Python 3.11, Windows 10/11

## Acceptance Criteria
- [ ] Boundary F1 >= 0.80（評価セット10件で）
- [ ] 手動修正回数/ページ <= 2
- [ ] Over-split率 <= 15%
- [ ] Over-merge率 <= 10%
- [ ] 回帰テストに追加済み

## Test Data
- Vault/40_Evals/sample_001 ~ sample_010

## Notes
- 参考仕様: RUNBOOK-Main.md Section 6
- ADR: ADR-20260113-paragraph-detection-strategy.md
