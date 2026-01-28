# バックアップ評価タスク依頼

> **依頼先**: Clawdbot / Antigravity Skills
> **タスク**: MEKIKI Operations SKILL #6「バックアップ評価」
> **優先度**: 高
> **作成日**: 2026-01-28

## 目的

全バックアップから各機能の最良実装を特定し、canonical/に登録する。

## 対象バックアップ

```
c:\Users\raiko\OneDrive\Desktop\26\
├── OCR_backup_20260107
├── OCR_backup_20260107_2135
├── OCR_backup_20260108_111253
├── OCR_backup_20260108_220510
├── OCR_backup_20260109_TransitionToMEKIKI
├── OCR_backup_20260111_002213
├── OCR_backup_20260111_064255
├── OCR_backup_20260111_144703
├── OCR_backup_20260113_AIExperiment
├── OCR_GoogleVisionAPI_AImode_Backup_20260114
├── OCR_backup_20260115_014330
├── OCR_MEKIKI_v1_Final_20260117  ★基準
├── OCR_backup_20260120_180524
├── OCR_backup_20260120_185807
├── OCR_backup_20260120_210154
├── OCR_backup_20260121_AgentOpsPrep
├── backup_Phase1.8_SearchFixes_20260121
└── OCR_backup_20260123_003016
```

## 評価対象機能

| # | 機能 | 検索パターン | 評価ポイント |
|---|------|-------------|-------------|
| 1 | サムネイル→Source連動 | `_on_thumbnail_click` | region.area_code正確性 |
| 2 | Canvas領域描画 | `_redraw_regions`, `_highlight_region_on_canvas` | scale適用 |
| 3 | 画像表示 | `_display_image` | scrollregion設定 |
| 4 | パラグラフ検出 | `ParagraphDetector`, `_build_paragraphs` | bbox精度 |
| 5 | テキスト差分 | `_apply_diff_highlight` | 日本語対応 |
| 6 | OCRエンジン | `CloudOCREngine.extract_text` | クラスタリング品質 |

## 評価基準

| 基準 | 重み | 説明 |
|------|------|------|
| 動作確実性 | 40% | アプリ起動→機能実行→期待結果 |
| コード簡潔性 | 20% | 行数、複雑度 |
| エラーハンドリング | 20% | try-except、fallback |
| 整合性 | 20% | 他機能との連携 |

## 出力先

- 評価結果: `Vault/10_Projects/mekiki/backup_registry.md`
- 最良コード: `Vault/10_Projects/mekiki/canonical/[機能名]/source.py`

## 実行指示

```
トリガー: 「バックアップ評価」
```

SKILL #6の手順に従い、全機能を評価・登録してください。
