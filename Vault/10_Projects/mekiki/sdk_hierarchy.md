---
type: design
project: mekiki
status: active
tags: [sdk, ocr, similarity, architecture]
created: 2026-01-27
---

# MEKIKI SDK Hierarchy

## Overview

MEKIKIは11個の精度検証済みSDKで構成されています。

```
app/sdk/
├── ocr/           # OCRエンジン統合 (⭐⭐⭐⭐⭐)
├── similarity/    # 類似検索・マッチング (⭐⭐⭐⭐)
├── canvas/        # 座標変換・キャッシュ (⭐⭐⭐⭐)
├── selection/     # 選択ハンドラ (⭐⭐⭐⭐)
├── storyboard/    # コンテ素材抽出 (⭐⭐⭐)
├── notification/  # Clawdbot通知 (⭐⭐⭐)
├── llm/           # GeminiClient (⭐⭐⭐⭐)
├── matching/      # difflib+LCS (⭐⭐⭐⭐)
├── export/        # Excel/PPTX (⭐⭐⭐)
└── scraping/      # Playwright (⭐⭐⭐⭐)
```

## Core Engines

### HybridOCREngine

- **精度**: ⭐⭐⭐⭐⭐ (最高)
- **構成**: Cloud Vision座標 + Gemini言語補正
- **用途**: 比較マトリクス、Sync計算

### CloudOCREngine  

- **精度**: ⭐⭐⭐⭐
- **構成**: Google Vision API直接呼出
- **用途**: 段落クラスタリング

### GeminiClient

- **精度**: ⭐⭐⭐⭐
- **構成**: gemini-2.0-flash + timeout堅牢化
- **用途**: セマンティック補正、マルチモーダル

## Quality Gates

| 指標 | 閾値 |
|:---|:---|
| 段落検出率 | ≥ 95% |
| Sync Rate | ≥ 60% |
| API応答 | ≤ 60s timeout |
