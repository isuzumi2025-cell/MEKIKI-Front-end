# MEKIKI サムネイル-Canvas同期 完成図仕様書 v2.0

> **Version**: 2.0 (2026-01-31)  
> **Target Score**: 9/10+  
> **Status**: 研鑽結果統合版

---

## 🎯 革新ポイント（8/10→9/10+へ）

| 要素 | 現状 | 革新後 |
|------|------|--------|
| ハイライト | 領域枠のみ | **文字レベル差分**＋領域枠 |
| スクロール | 独立 | **双方向同期スクロール** |
| 表示モード | 全表示 | **差分のみモード**切替 |
| ナビゲーション | なし | **次/前の差分ジャンプ** |
| クリック反応 | ハイライトのみ | **ズーム＋センタリング** |

---

## 1. コアアーキテクチャ

### 1.1 ページモデルの根本的違い

```
【PDF: 1枚連続スティッチ】        【Web: ページ切り替え】

┌─────────────┐                  ╔═════════════╗
│   Page 1    │                  ║   Page 1    ║ ← 表示中
├─────────────┤                  ╚═════════════╝
│   Page 2    │  ← スクロール    
├─────────────┤                  ┌─────────────┐
│   Page 3    │                  │   Page 2    │ ← 非表示
└─────────────┘                  └─────────────┘

メソッド: highlight_pdf()       メソッド: highlight_web_page()
座標系: グローバル連続Y          座標系: ページローカル
スクロール: 連続                 切替: ページナビゲーション
```

### 1.2 デュアルハイライトエンジン

```python
class HighlightEngine:
    """PDF/Web両対応ハイライトエンジン"""
    
    def highlight_pdf_stitch(self, canvas, region):
        """PDF連続スティッチモード
        - 座標: グローバルY (page_offset不要)
        - スクロール: yview_moveto()で直接移動
        - ページ切替: 不要
        """
        y = region.global_y  # 連続座標
        self._draw_highlight(canvas, region.rect)
        canvas.yview_moveto(y / self.total_height)
    
    def highlight_web_page(self, canvas, region, current_page):
        """Webページ切り替えモード
        - 座標: ページローカル (各ページ原点=0)
        - ページ切替: region.page_id != current_page なら切替
        - スクロール: 切替完了後にyview
        """
        if region.page_id != current_page:
            self._switch_page(region.page_id)
            self.after(100, lambda: self._draw_highlight(canvas, region.rect))
        else:
            self._draw_highlight(canvas, region.rect)
```

---

## 2. 革新機能詳細

### 2.1 文字レベル差分ハイライト

```python
class CharacterDiffHighlighter:
    """文字レベル差分検出＋ハイライト"""
    
    def highlight_char_diff(self, web_text, pdf_text):
        """
        1. difflib.SequenceMatcher で文字単位差分
        2. 差分箇所に色付きスパン適用
        3. 同一部分は白、差分は緑/赤
        """
        matcher = difflib.SequenceMatcher(None, web_text, pdf_text)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                self._mark_same(i1, i2)
            elif tag == 'replace':
                self._mark_changed(i1, i2, 'yellow')
            elif tag == 'delete':
                self._mark_deleted(i1, i2, 'red')
            elif tag == 'insert':
                self._mark_inserted(j1, j2, 'green')
```

### 2.2 双方向同期スクロール

```python
class SyncScrollController:
    """Web-PDF間の同期スクロール"""
    
    def __init__(self, pdf_canvas, web_canvas):
        self.pdf_canvas = pdf_canvas
        self.web_canvas = web_canvas
        self._bind_scroll_events()
    
    def _on_pdf_scroll(self, event):
        """PDF→Web同期"""
        pdf_y = self.pdf_canvas.yview()[0]
        # PDFのグローバルY → WebのページID＋ローカルY変換
        page_id, local_y = self._pdf_to_web_coords(pdf_y)
        self._switch_web_page_and_scroll(page_id, local_y)
    
    def _on_web_scroll(self, event):
        """Web→PDF同期"""
        page_id = self.current_web_page
        local_y = self.web_canvas.yview()[0]
        # WebのページID＋ローカルY → PDFのグローバルY変換
        global_y = self._web_to_pdf_coords(page_id, local_y)
        self.pdf_canvas.yview_moveto(global_y)
```

### 2.3 差分のみ表示モード

```python
class DiffOnlyFilter:
    """差分のみ表示フィルター"""
    
    def __init__(self, sync_pairs):
        self.all_pairs = sync_pairs
        self.diff_only_mode = False
    
    def toggle_diff_only(self):
        """差分のみ表示切替"""
        self.diff_only_mode = not self.diff_only_mode
        if self.diff_only_mode:
            # similarity < 1.0 のみ表示
            visible = [p for p in self.all_pairs if p.similarity < 0.95]
        else:
            visible = self.all_pairs
        self._update_spreadsheet(visible)
```

### 2.4 次/前の差分ジャンプ

```python
class DiffNavigator:
    """差分間ナビゲーション"""
    
    def __init__(self, sync_pairs):
        self.diff_indices = [
            i for i, p in enumerate(sync_pairs) 
            if p.similarity < 0.95
        ]
        self.current_diff_idx = -1
    
    def jump_next_diff(self):
        """次の差分へジャンプ"""
        if self.current_diff_idx < len(self.diff_indices) - 1:
            self.current_diff_idx += 1
            pair_idx = self.diff_indices[self.current_diff_idx]
            self._highlight_and_scroll(pair_idx)
    
    def jump_prev_diff(self):
        """前の差分へジャンプ"""
        if self.current_diff_idx > 0:
            self.current_diff_idx -= 1
            pair_idx = self.diff_indices[self.current_diff_idx]
            self._highlight_and_scroll(pair_idx)
```

---

## 3. ユニークID体系

| ソース | 形式 | 例 | 座標系 |
|--------|------|-----|--------|
| Web | `Web-P{page}-{seq}` | `Web-P1-001` | ページローカル |
| PDF | `PDF-{seq}` | `PDF-001` | グローバル連続 |

> **注意**: PDFは1枚連続のためページ番号不要

---

## 4. UIコンポーネント追加

```
┌──────────────────────────────────────┐
│  [◀ Prev] [差分: 3/15] [Next ▶]     │  ← 差分ナビゲーション
│  [☐ 差分のみ表示] [🔗 同期スクロール]  │  ← トグルスイッチ
├──────────────────────────────────────┤
│   Canvas表示領域                      │
└──────────────────────────────────────┘
```

---

## 5. 実装優先順位

| Phase | 機能 | 工数 | 効果 |
|-------|------|------|------|
| 1 | デュアルハイライトエンジン | 中 | 🔴 基盤 |
| 2 | 次/前の差分ジャンプ | 小 | 🟢 即効性高 |
| 3 | 差分のみ表示モード | 小 | 🟢 UX向上 |
| 4 | 文字レベル差分 | 大 | 🟡 差別化 |
| 5 | 双方向同期スクロール | 大 | 🟡 先進的 |

---

## 6. 検証チェックリスト

- [ ] PDFクリック → グローバル座標でハイライト
- [ ] Webクリック → ページ切替＋ローカル座標ハイライト  
- [ ] 差分ジャンプ → 次/前ボタン動作
- [ ] 差分のみ表示 → トグル切替
- [ ] 文字レベルハイライト → 差分箇所が色分け
- [ ] 同期スクロール → PDF⇔Web連動

---

Tags: #Specification #Innovation #9-10 #ThumbnailSync #MEKIKI #Phase151
