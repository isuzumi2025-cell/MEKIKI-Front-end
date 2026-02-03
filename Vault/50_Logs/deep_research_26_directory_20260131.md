# 26 ディレクトリ ディープリサーチレポート

**作成日**: 2026-01-31  
**作成者**: Antigravity  
**目的**: プロジェクト全体の理解と最適化機会の特定

---

## 📊 サマリー

| 指標 | 値 |
|------|-----|
| **総容量** | 約13.7 GB |
| **バックアップ数** | 16 (OCR_backup_*) |
| **メインプロジェクト** | OCR (MEKIKI Proofing System) |
| **サブプロジェクト** | sitemap_pro, ad_proofing_system, LegacyOCR |
| **Zipバックアップ** | 4個 (~826 MB) |

---

## 🏗️ ディレクトリ構造

### Tier 1: アクティブ開発プロジェクト

```
26/
├── OCR/                    ★ メイン (1006 children, 活発な開発)
│   ├── app/               # アプリケーションコード
│   │   ├── core/          # 48モジュール (OCR, マッチング, 分析)
│   │   ├── gui/           # 15ファイル + サブディレクトリ
│   │   ├── sdk/           # 51ファイル (Clawdbot, LLM, Similarity)
│   │   └── utils/         # ユーティリティ
│   ├── Vault/             # Obsidian ナレッジベース (61 children)
│   ├── .agent/            # Antigravity Skills
│   └── config/            # 設定ファイル
│
├── sitemap_pro/           # サイトマップ/クローラー (588 children)
└── ad_proofing_system/    # 別の校正システム (17 children)
```

### Tier 2: バックアップ群

```
OCR_backup_YYYYMMDD_*      # 16個のディレクトリバックアップ
├── 20260107 ~ 20260128    # 約3週間分
├── 最も古い: 20260107
└── 最も新しい: 20260128_224817 (Phase 44直前)
```

### Tier 3: レガシー/アーカイブ

```
LegacyOCR/                 # 旧バージョン (32 children)
OCR_Gemini3_Revision/      # Gemini 3.0実験版 (205 children)
ObsidianVault/             # 旧Obsidian (6 children) ← OCR/Vaultに統合?
```

---

## 🔍 key ファイル分析

### OCR/app/core/ (48モジュール)

| カテゴリ | ファイル | サイズ | 備考 |
|----------|---------|--------|------|
| **OCR** | engine_cloud.py | 22KB | 🔴 Core: クラスタリング |
| | hybrid_ocr.py | 6.9KB | Vision+Gemini融合 |
| | ocr_engine.py | 11KB | Cloud Vision API |
| | gemini_ocr.py | 6.1KB | Gemini直接OCR |
| **マッチング** | sync_matcher.py | 11.5KB | 🔴 Core: Similarity 0.5 |
| | paragraph_matcher.py | 20.8KB | 🔴 Core: 8-char LCS |
| | text_matcher.py | 7.6KB | テキスト比較 |
| **分析** | analyzer.py | 22.4KB | 差分分析 |
| | paragraph_detector.py | 20.9KB | 段落検出 |
| | structure_propagator.py | 15.5KB | 構造伝播 |
| **クローラー** | crawler.py | 23.2KB | Webクローラー |
| | enhanced_scraper.py | 16.9KB | Ultrathink対応 |

### OCR/app/gui/ (15ファイル + 7サブディレクトリ)

| ファイル | サイズ | 備考 |
|---------|--------|------|
| unified_app.py | 78KB | ⚠️ モノリス - 要リファクタリング |
| advanced_comparison_view.py | (windows内) | Phase 44の中心 |
| dashboard.py | 32.6KB | ダッシュボード |
| main_window_v2.py | 33KB | Genius Edition |

---

## ⚠️ 問題点と改善提案

### 1. ストレージ肥大化

**問題**: 16個のディレクトリバックアップ + 4個のZipで推定5GB以上

**提案**:

- Tier 1 バックアップのみ保持 (3個程度)
- 他はZip圧縮してクラウドにアーカイブ

### 2. モノリスファイル

**問題**:

- `unified_app.py` (78KB) - 1700行超
- `advanced_comparison_view.py` (推定200KB+) - 4700行超

**提案**:

- 機能別にMixinクラスとして分離
- 現在進行中だが完了していない

### 3. 重複コード

**問題**:

- `OCR/ObsidianVault/` と `OCR/Vault/` が別々に存在
- `sitemap_pro/OCRappBackupFile/` (464 children) 内に重複

**提案**:

- Vault統一 (OCR/Vault/ を正とする)
- sitemap_pro内のバックアップを整理

### 4. 未使用/レガシーコード

**問題**:

- `LegacyOCR/` が残存
- `OCR_Gemini3_Revision/` の位置づけ不明

**提案**:

- 機能を確認し、不要なら削除
- 必要ならOCR本体に統合

---

## 📚 Obsidian Vault 構成

```
OCR/Vault/
├── 00_Runbook/           # 運用ルール (6ファイル)
├── 10_Projects/          # プロジェクト文書 (43ファイル)
├── 20_AI_Strategy/       # AI戦略 (1ファイル)
├── 20_Design/            # 設計文書 (1ファイル)
├── 30_Prompts/           # プロンプト (空)
├── 40_Evals/             # 評価 (1ファイル)
├── 50_Logs/              # ログ・インシデント (7ファイル)
├── 99_Archive/           # アーカイブ (空)
├── architecture.md       # アーキテクチャ図 ★重要
└── index.md              # インデックス
```

---

## 🎯 推奨アクションリスト

### 短期 (今週中)

1. [ ] `project_sanctuary.md` を最新状態に更新
2. [ ] 古いバックアップをZip圧縮して外部ストレージへ
3. [ ] Web OCR 0件問題の根本解決

### 中期 (2週間以内)

1. [ ] `unified_app.py` のMixin分離完了
2. [ ] `ObsidianVault/` を `Vault/` に統合
3. [ ] sitemap_pro内の重複整理

### 長期 (1ヶ月以内)

1. [ ] LegacyOCRの機能評価と判断
2. [ ] 自動バックアップローテーションスクリプト作成
3. [ ] CI/CDパイプライン構築

---

## 📎 参照

- [architecture.md](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/Vault/architecture.md)
- [project_sanctuary.md](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/Vault/00_Runbook/project_sanctuary.md)
- [backup_catalog.md](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/Vault/10_Projects/mekiki/backup_catalog.md)

---

## 🤖 GPT-5.2 戦略レビュー

> **相談日時**: 2026-01-31 08:56  
> **相談元**: Antigravity (Claude)

### 優先順位評価

| 項目 | 優先度 | リスク | 理由 |
|------|--------|--------|------|
| **Web OCR問題** | 🔴 高 | 高 | システム機能が低下中、即時修正必要 |
| **リファクタリング** | 🔴 高 | 中 | Web OCR/HybridOCRがプロジェクト進行に直接影響 |
| **バックアップ最適化** | 🟡 中 | 低 | ディスクスペース問題だが即時性は低い |

### GPT推奨アクション

1. **Web OCR問題**
   - OCRサービス接続状態を確認
   - APIキー・認証トークンの設定見直し
   - 入力データフォーマットの検証

2. **リファクタリング**
   - HybridOCR初期化部分を別モジュールに切り出し
   - 初期化ロジックを明確化
   - 十分なテストを実施

3. **バックアップ**
   - 古いバックアップ自動削除スクリプト作成
   - 保持期間: 30日を推奨

### GPTコード提案

```python
# バックアップ自動クリーンアップ（GPT提案）
import os, glob
from datetime import datetime, timedelta

BACKUP_DIR = 'c:/Users/raiko/OneDrive/Desktop/26'
RETENTION_DAYS = 30

def delete_old_backups():
    pattern = os.path.join(BACKUP_DIR, 'OCR_backup_*')
    files = glob.glob(pattern)
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    for f in files:
        if datetime.fromtimestamp(os.path.getmtime(f)) < cutoff:
            print(f"Would delete: {f}")
            # os.remove(f)  # 実際に削除する場合はコメント解除
```

---

**Antigravity所感**: GPTの分析は的確。Web OCR 0件問題を最優先で解決後、リファクタリングに着手すべき。
