# シート連携ID不一致問題

## 問題概要

サムネイルクリック→Sourceハイライトが正しい位置に表示されない

## 根本原因

| 場所 | ID形式 | 例 |
|------|--------|-----|
| SyncPair.web_id | ParagraphEntry.id | `W-001` |
| spreadsheet_panel.web_map キー | EditableRegion.area_code | `Col0-W1_P-20` |

**キー形式が異なるため、regionが見つからない→pair.bboxが使われるが座標系が異なる**

## 解決策候補

### A: ParagraphEntryにarea_codeを使う（根本解決）

- `paragraph_matcher.py`の`create_paragraph_entries_from_clusters`でidをarea_code形式に変更
- マッチング結果とregionが一致

### B: spreadsheet_panelでキーの両方を登録（暫定）

- `web_map`にid(W-001形式)とarea_code両方でregionを登録
- 互換性維持

## 選択

TBD
