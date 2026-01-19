# Claude Code 指示書: Score/Web ID/Thumb 列の表示問題修正

**作成日**: 2026-01-14
**作成者**: Antigravity Agent (Gemini)
**対象**: Claude Code Agent (WSL経由)

---

## 🎯 目的

`Live Comparison Sheet` において、**Score** 列、**Web ID / Thumb** 列が空欄になる問題を修正する。

---

## 📋 現状

### ログ出力（正常）
データは全て正しく作成されています：
```
[Row 0] web_id=Col0-W4_P-53, pdf_id=Col0-P2_emb_263, sim=1.00
  web_bbox=[2550, 179168, 2576, 179225], pdf_bbox=[2420, 5219, 2440, 5241]
  web_image=True, pdf_image=True
  Score: 100%, color=#4CAF50
  Web ID: Col0-W4_P-53
  Web Thumb created: True
```

### UI表示（問題あり）
- **Score列**: 空（100%等が表示されない）
- **Web ID/Thumb列**: 空（IDもサムネイルも表示されない）
- **PDF ID/Thumb列**: サムネイルは表示されている
- **Web Text/PDF Text列**: 正常に表示されている

---

## 🔍 根本原因の推定

`spreadsheet_panel.py` の `_create_row` メソッドで、固定幅フレームに対して以下の組み合わせを使用しています：

```python
score_frame = ctk.CTkFrame(row, fg_color=bg, width=60, height=120)
score_frame.pack(side="left", fill="y", padx=1)
score_frame.pack_propagate(False)  # ← この設定がCTkFrameと相性が悪い可能性
```

**CustomTkinter**（ctk）のCTkFrameは標準のtkinter.Frameとは内部実装が異なり、`pack_propagate(False)` が期待通りに動作しない場合があります。

---

## ✅ 推奨修正方法

### オプション1: pack_propagate(False) を削除し、明示的なサイズ指定に変更

```python
# Before
score_frame = ctk.CTkFrame(row, fg_color=bg, width=60, height=120)
score_frame.pack(side="left", fill="y", padx=1)
score_frame.pack_propagate(False)

# After
score_frame = ctk.CTkFrame(row, fg_color=bg, width=60)
score_frame.pack(side="left", fill="y", padx=1, ipadx=0, ipady=0)
# pack_propagate(False) を削除
```

### オプション2: grid レイアウトに変更

packの代わりにgridを使用して、より明示的なセル配置を行う。

### オプション3: CTkFrameの代わりにtk.Frameを使用

CTkFrameではなく標準のtk.Frameを使って、`pack_propagate(False)` が正しく動作するようにする。

---

## 📁 対象ファイル

**ファイルパス**: `C:/Users/raiko/OneDrive/Desktop/26/OCR/app/gui/panels/spreadsheet_panel.py`

### 修正箇所

#### 1. Score列（行207-211付近）
```python
score_frame = ctk.CTkFrame(row, fg_color=bg, width=60, height=120)
score_frame.pack(side="left", fill="y", padx=1)
score_frame.pack_propagate(False)  # ← 削除または修正
```

#### 2. Web ID + Thumbnail 列（行213-216付近）
```python
web_id_frame = ctk.CTkFrame(row, fg_color=row_bg, width=120, height=120)
web_id_frame.pack(side="left", fill="y", padx=1)
web_id_frame.pack_propagate(False)  # ← 削除または修正
```

#### 3. PDF ID + Thumbnail 列（行262-265付近）
```python
pdf_id_frame = ctk.CTkFrame(row, fg_color=row_bg, width=120, height=120)
pdf_id_frame.pack(side="left", fill="y", padx=1)
pdf_id_frame.pack_propagate(False)  # ← 削除または修正
```

---

## 🧪 検証方法

1. アプリを起動: `py -3 run_unified.py`
2. PDFとWebページを読み込む
3. 「AI分析モード」ボタンをクリック
4. `Live Comparison Sheet` を確認:
   - Score列に「100%」「93%」等のパーセンテージが表示されるか
   - Web ID/Thumb列にIDとサムネイルが表示されるか
   - PDF ID/Thumb列は既に動作しているので参考にする

---

## 📝 補足情報

- **PDF ID/Thumb列は正常に動作している**ため、その実装を参考にしてください
- デバッグログは維持して、修正後も動作確認ができるようにしてください
- `_create_thumbnail_from_bbox` メソッドと `_on_thumbnail_click_bbox` メソッドは問題なく動作しています
