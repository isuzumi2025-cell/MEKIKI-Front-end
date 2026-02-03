# OCR最適化テクニック（Web検索結果）

**収集日**: 2026-01-31T13:21  
**検索クエリ**: OCR performance optimization parallel processing Gemini API Python

---

## サマリー

Gemini APIとPythonを使用したOCRパフォーマンス最適化の主要手法:

### 1. Gemini API最適化

- **File API活用**: 20MB以上はFile API推奨（レイテンシ改善）
- **media_resolution パラメータ**: 「medium」で十分なケースが多い
- **画像前処理**: 回転補正、ぼやけ除去、クロップ、圧縮で精度向上

### 2. 並列処理（Python側）

| 手法 | 適用場面 | ライブラリ |
|------|----------|-----------|
| **asyncio + aiohttp** | I/O待ち最適化（API呼び出し） | asyncio, aiohttp |
| **threading** | I/Oバウンドタスク | threading |
| **multiprocessing** | CPUバウンドタスク | multiprocessing |

### 3. バッチ処理戦略

- 大量PDFは分割してバッチ処理
- File APIでドキュメント再利用（48時間保持）

---

## MEKIKI適用案

### 現在の実装

```python
# hybrid_ocr.py - 直列処理
for i, chunk in enumerate(chunks):
    corrected = self._call_gemini_correction(chunk)
```

### 最適化案

```python
# asyncio並列版
import asyncio
import aiohttp

async def correct_chunks_parallel(chunks):
    tasks = [call_gemini_async(chunk) for chunk in chunks]
    return await asyncio.gather(*tasks)
```

---

## 参考リンク

- [Google Gemini Vision Guide](https://ai.google.dev)
- [PyImageSearch OCR Optimization](https://pyimagesearch.com)

---

Tags: #OCR #Performance #Gemini #Optimization #WebResearch
