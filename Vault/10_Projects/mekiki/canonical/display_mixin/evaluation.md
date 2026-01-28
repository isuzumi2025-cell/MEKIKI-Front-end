# display_mixin.py 評価レポート

**評価日**: 2026-01-28
**評価者**: Antigravity + MEKIKI Operations Skill v2.1.0

---

## ソース比較

| 項目 | SUCCESS版 | 現行版 | 評価 |
|------|-----------|--------|------|
| 行数 | 212 | 227 | 現行が+15行 |
| `_display_image` | ✅ 同一 | ✅ 同一 | 同等 |
| `_highlight_region_on_canvas` | ✅ 同一 | ✅ 同一 | 同等 |
| `_redraw_regions` | シンプル版 | バッジ付き | **現行優位** |
| `_stitch_pages_vertically` | ✅ 同一 | ✅ 同一 | 同等 |

## 詳細差分

### `_redraw_regions` の違い

**SUCCESS版** (L104-170):

- area_code テキストラベルのみ
- 未同期リージョンは赤色 `#F44336`

**現行版** (L104-185):

- ★ 丸数字バッジ追加（①②③...）
- ★ 未同期リージョンは灰色 `#808080`
- sync_number+1 をバッジ表示
- バッジ背景矩形付き

## 結論

| 機能 | 採用版 | 理由 |
|------|--------|------|
| `_display_image` | どちらでも可 | 同一 |
| `_highlight_region_on_canvas` | どちらでも可 | 同一 |
| `_redraw_regions` | **現行版** | バッジ機能が優れている |

## 未実装・改善希望

1. **スクロール位置調整**: `yview_moveto` の計算が不正確（高さではなくscrollregion使用すべき）
2. **ハイライト消去**: `canvas.delete("highlight")` がない（累積表示される可能性）
3. **DPI考慮なし**: 高DPIディスプレイ対応なし

## 推奨アクション

- [x] 現行版を canonical として登録（バッジ機能が優れている）
- [ ] スクロール計算を scrollregion ベースに修正
- [ ] highlight タグの自動消去を追加
