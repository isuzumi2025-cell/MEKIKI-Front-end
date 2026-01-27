---
type: runbook
project: mekiki
status: active
tags: [operations, procedures, v12.4.6]
created: 2026-01-27
---

# MEKIKI Operational Runbook

> **Purpose**: 運用手順の正本。Antigravity/Claude Codeから参照される。

## Quick Start

```powershell
# MEKIKI起動
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
python main.py

# バックエンド起動 (sitemap_pro)
cd c:\Users\raiko\OneDrive\Desktop\26\sitemap_pro
uvicorn app.main:app --port 8001
```

## Core Workflows

### 1. Web/PDF比較

1. 🌐 Web読み込み → URL入力、クロール実行
2. 📄 PDF読み込み → ファイル選択
3. 🟣 ハイブリッドOCR → 段落検出実行
4. 🔗 Sync再計算 → マッチング確認

### 2. コンテ素材抽出

1. 📄 PDF読み込み → ストーリーボード対象PDF
2. テキスト抽出 → 素材シートに反映
3. 画像抽出 → サムネイル生成

## Safety Protocols

### バックアップ作成

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item -Path ".\OCR" -Destination "..\OCR_backup_$timestamp" -Recurse -Force
```

### 精度劣化時のリバート

```powershell
# 安定版からの復元
copy "path\to\backup\module.py" ".\OCR\app\core\module.py"
git add . && git commit -m "revert: Restore stable version"
```

## Related Documents

- [[sitemap_pro/design]] - バックエンド設計
- [[sitemap_pro/architecture]] - API仕様
- [[20_Design/sdk_hierarchy]] - SDK構成
