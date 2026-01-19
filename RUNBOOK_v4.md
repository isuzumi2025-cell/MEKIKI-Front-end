# MEKIKI Standalone Edition Runbook v4

**更新日**: 2026-01-19
**バージョン**: v4.0.0

---

## 1. システム概要

| 項目 | 値 |
|------|-----|
| アプリ名 | MEKIKI Proofing System |
| 用途 | Web/PDF比較校正ツール |
| 配布形態 | スタンドアローン (社内配布) |
| メインファイル | `app/gui/unified_app.py` |

---

## 2. 品質基準

### 2.1 機能精度基準

| 機能 | 目標精度 | 測定方法 |
|------|----------|----------|
| OCR認識 | 98%+ | 文字正解率 |
| パラグラフ検出 | 95%+ | F1スコア |
| Sync率計算 | 99%+ | 数値精度 |
| 座標変換 | 100% | ラウンドトリップ検証 |

### 2.2 レスポンス基準

| 操作 | 目標 | 現状 |
|------|------|------|
| リサイズ応答 | <200ms | 150ms ✅ |
| 選択矩形描画 | <50ms | - |
| OCR実行 | <3s | - |

---

## 3. 修復手順

### Phase 0: クリティカル修正

#### 0-A: Coverモードオフセット修正

**対象**: `advanced_comparison_view.py:1328`

```python
# 修正前
canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")

# 修正後
canvas.create_image(-offset_x, -offset_y, anchor="nw", image=photo, tags="image")
```

**検証手順**:

1. Coverモードで画像読み込み
2. 画像中央が表示されることを確認
3. 領域選択の座標が正確か確認

#### 0-B: SelectionMixin イベント連携

**対象**: `advanced_comparison_view.py:2506` (_on_canvas_click)

```python
def _on_canvas_click(self, event):
    # SelectionMixin連携（最高品質）
    if _HAS_SELECTION_MIXIN and hasattr(self, '_on_selection_start'):
        canvas = event.widget
        source = "web" if canvas == self.web_canvas else "pdf"
        self._on_selection_start(event, canvas, source)
    
    # 既存処理を維持（フォールバック）
    # ...
```

**検証手順**:

1. Canvas上でドラッグ選択
2. 緑点線→黄実線への変化確認
3. OCR結果のコンソール出力確認

---

### Phase 1: 高優先度

#### 1-1: インライン領域編集

#### 1-2: Export Excel

#### 1-3: Save/Load Project

---

## 4. 起動コマンド

```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
python app/gui/unified_app.py
```

---

## 5. Git コミット規約

```
feat: 機能追加
fix: バグ修正
```

**現在のHEAD**: `6c4bfbb`
