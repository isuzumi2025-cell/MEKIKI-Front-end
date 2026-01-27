---
type: design
project: sitemap_pro
status: frozen
tags: [backend, fastapi, crawler, architecture]
created: 2026-01-06
---

# Sitemap Pro - システムアーキテクチャドキュメント

## 概要

WebサイトとPDFドキュメントのテキスト抽出・比較・校正システム

---

## システム構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                    統合ビューワー (Browser)                      │
│  http://localhost:8001                                         │
├───────────────────────┬───────────────────────┬─────────────────┤
│    📄 Web Panel       │    📄 PDF Panel        │  📊 比較パネル   │
│  ┌─────────────────┐  │  ┌─────────────────┐  │  ┌───────────┐  │
│  │ スクリーンショット │  │  │ PDF レンダリング  │  │  │ 差分表示  │  │
│  │ + 選択領域       │  │  │ + 選択領域       │  │  │ Sync Rate │  │
│  └─────────────────┘  │  └─────────────────┘  │  └───────────┘  │
└───────────────────────┴───────────────────────┴─────────────────┘
                              ▲
                    ┌─────────┴─────────┐
                    │   Python Backend   │
                    │  (FastAPI Server)  │
                    └─────────┬─────────┘
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ text_       │    │ engines/    │    │ text_       │
   │ extractor   │    │ ocr_engine  │    │ comparator  │
   └─────────────┘    └─────────────┘    └─────────────┘
```

---

## コアモジュール

| モジュール | サイズ | 機能 |
|:---|:---|:---|
| `text_extractor.py` | 16KB | 統合テキスト抽出エンジン |
| `text_comparator.py` | 16KB | テキスト比較・差分エンジン |
| `comparison_viewer.py` | 26KB | 2x3 マトリクスビューワー |
| `engines/ocr_engine.py` | - | Google Cloud Vision API OCR |
| `engines/dom_handler.py` | - | Playwright DOM/XPath 抽出 |

---

## API エンドポイント

### テキスト抽出

| エンドポイント | 機能 |
|:---|:---|
| `POST /extract/web` | Web URL からテキスト抽出 |
| `POST /extract/pdf` | PDF から OCR 抽出 |
| `POST /extract/image` | 画像 OCR |
| `POST /extract/region` | 領域指定 OCR |

### テキスト比較

| エンドポイント | 機能 |
|:---|:---|
| `POST /compare` | 2テキスト比較 |
| `POST /compare/blocks` | ブロック親和性比較 |
| `POST /compare/suggestions` | サジェスト生成 |
| `POST /compare/viewer` | 比較ビューワー HTML |

---

## 起動方法

```bash
cd sitemap_pro
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --port 8001
```

アクセス: <http://localhost:8001>

---

## Related Documents

- [[design]] - 詳細設計書
- [[mekiki/sdk_hierarchy]] - MEKIKIとのSDK連携
