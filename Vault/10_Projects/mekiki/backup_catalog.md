# MEKIKI バックアップカタログ

**更新日**: 2026-01-29
**評価者**: Antigravity + MEKIKI Operations Skill v2.1.0
**調査状況**: ✅ 22/22 完了

---

## バックアップ一覧（評価済）

| # | バックアップ名 | 評価 | 優先度 |
|---|---------------|------|--------|
| 1 | OCR_MEKIKI_v1_Final_20260117 | ✅ 完了 | 最高 |
| 2 | backup_ParagraphSorted_SUCCESS_20260113 | ✅ 完了 | 高 |
| 3 | OCR_backup_20260128_224817 | 安全バックアップ | - |
| 4 | OCR_GoogleVisionAPI_AImode_Backup_20260114 | ✅ 完了 | - |
| 5 | OCR_backup_20260109_TransitionToMEKIKI | ✅ 完了 | - |
| 6-22 | その他16バックアップ | ✅ 完了 | - |

## 評価結果サマリ

| ファイル | SUCCESS版 | 現行版 | 採用 | 理由 |
|----------|-----------|--------|------|------|
| display_mixin.py | 212行 | 227行 | 現行版 | バッジ機能 |
| spreadsheet_panel.py | 338行 | 759行 | 現行版 | 仮想スクロール |
| engine_cloud.py | 483行 | 483行 | 同一 | - |
| paragraph_detector.py | 609行 | 609行 | 同一 | - |

## 現行版に統合済みモジュール

| モジュール | 場所 | 発見バックアップ |
|------------|------|-----------------|
| claude_agent | app/agents/ | MEKIKI_v1_Final |
| multi_model_advisor | app/agents/ | MEKIKI_v1_Final |
| evidence | app/evidence/ | MEKIKI_v1_Final |
| cluster_matcher | app/core/ | GoogleVisionAPI_AImode |
| e2e_wrapper | app/core/ | GoogleVisionAPI_AImode |

## 未実装・改善希望（バックアップでは解決できない）

| 機能 | 優先度 | 対象 | 状態 |
|------|--------|------|------|
| スクロール計算修正 | 高 | display_mixin | ✅ 2026-01-29 |
| 差分ハイライト復元 | 高 | spreadsheet_panel | ✅ 既に実装済み |
| highlight自動消去 | 中 | display_mixin | - |
| Sync Rate列追加 | 中 | spreadsheet_panel | - |
| パラメータ設定ファイル化 | 低 | engine_cloud | - |

## 結論

SUCCESS版との比較により、**現行版が全般的に優位**と判定。
22バックアップ完全調査の結果、移植すべき新規コードは発見されなかった。
未実装機能は新規開発が必要。
