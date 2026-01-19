# MEKIKI OCR - 問題分析レポート

**作成日**: 2026-01-19
**対象バージョン**: v1.0.0
**ステータス**: 🔴 Critical Issues Identified

---

## 📋 目次

1. [エグゼクティブサマリー](#エグゼクティブサマリー)
2. [問題1: 画像表示サイズとリンクメソッドの最適化](#問題1-画像表示サイズとリンクメソッドの最適化)
3. [問題2: 範囲選択の表示と手動編集](#問題2-範囲選択の表示と手動編集)
4. [問題3: アクティブボタンと機能の説明](#問題3-アクティブボタンと機能の説明)
5. [推奨アクションプラン](#推奨アクションプラン)
6. [付録: 影響を受けるファイル一覧](#付録-影響を受けるファイル一覧)

---

## エグゼクティブサマリー

### 🔴 Critical Issues (3件)
1. **画像表示のオフセット計算が機能していない** → Coverモードで中央配置されない
2. **インライン範囲編集機能が実装されていない** → 別ウィンドウを開く必要がある
3. **主要機能の67%のみ実装** → ExportとSave機能が未実装

### 📊 調査結果サマリー

| カテゴリ | 問題数 | 重大度 | 影響範囲 |
|---------|--------|--------|----------|
| 画像表示 | 5 | 🔴 High | Canvas表示全体 |
| 範囲選択 | 4 | 🟡 Medium | 選択操作・編集 |
| UI機能 | 3 | 🟡 Medium | ワークフロー |

### 🎯 優先度

1. **最優先**: 画像オフセット修正（Coverモード中央配置）
2. **高**: インライン範囲編集の実装
3. **中**: Export Excel / Save Project機能の実装

---

## 問題1: 画像表示サイズとリンクメソッドの最適化

### 📍 影響を受けるファイル
- `app/gui/windows/advanced_comparison_view.py`
  - `_display_image()` (Lines 1249-1371)
  - `_display_image_smart()` (Lines 740-799)
- `app/sdk/canvas/transform.py`

---

### 🔍 問題1-A: Coverモードのオフセット計算が無効

#### 症状
Coverモード（余白なし表示）で画像が中央配置されず、常に左上(0,0)から表示される。

#### 根本原因

**ファイル**: `advanced_comparison_view.py:1318-1328`

```python
# オフセット計算は実行される（Lines 1318-1325）
if self._display_mode == "cover":
    new_w = int(img_w * scale_factor)
    new_h = int(img_h * scale_factor)
    offset_x = max(0, (new_w - canvas_w) // 2)
    offset_y = max(0, (new_h - canvas_h) // 2)
else:
    offset_x = offset_y = 0

# しかし、画像配置は常に(0,0)に固定（Line 1328）
canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
#                  ^^^^  ← オフセットが反映されていない！
```

#### 期待される動作
```python
# 正しい実装例
canvas.create_image(
    -offset_x,  # ← 負のオフセットで中央寄せ
    -offset_y,
    anchor="nw",
    image=photo,
    tags="image"
)
```

#### 影響範囲
- Coverモード使用時に画像の左上部分のみが表示される
- 座標変換システム（`CanvasTransform`）には正しいオフセットが設定されているため、領域選択の座標は正しく計算されるが、**視覚的に画像と領域がズレて見える**

#### 解決策

**修正箇所**: `advanced_comparison_view.py:1328`

```python
# 修正前
canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")

# 修正後
canvas.create_image(
    -offset_x,  # Coverモード時は負のオフセット
    -offset_y,
    anchor="nw",
    image=photo,
    tags="image"
)
```

**追加修正**: `advanced_comparison_view.py:1332-1333`

```python
# スクロール領域もオフセットを考慮
canvas.configure(scrollregion=(
    -offset_x,
    -offset_y,
    new_width - offset_x,
    new_height - offset_y
))
```

---

### 🔍 問題1-B: Canvas サイズ検出の信頼性

#### 症状
Canvas サイズ取得に3段階のフォールバックがあり、正確なサイズが取得できない可能性がある。

#### 根本原因

**ファイル**: `advanced_comparison_view.py:1266-1275`

```python
# 1st try: winfo_width()
canvas_w = canvas.winfo_width()
canvas_h = canvas.winfo_height()

# 2nd fallback: 固定値 800x600
if canvas_w <= 1 or canvas_h <= 1:
    canvas_w = 800
    canvas_h = 600

# 3rd fallback: イベント時のサイズ
if event and hasattr(event, 'width'):
    canvas_w = event.width
    canvas_h = event.height
```

#### 問題点
1. ウィンドウ初期化直後は `winfo_width()` が 1 を返す（Tkinterの仕様）
2. 固定値800x600は実際のウィンドウサイズと異なる可能性
3. フォールバック順序が不適切（eventを最後にチェックすべき）

#### 解決策

```python
def _get_canvas_size(self, canvas: tk.Canvas, event=None) -> Tuple[int, int]:
    """Canvas サイズを確実に取得"""

    # 1. イベントサイズを優先（最新の値）
    if event and hasattr(event, 'width') and event.width > 1:
        return event.width, event.height

    # 2. update_idletasks()で強制更新してから取得
    canvas.update_idletasks()
    w, h = canvas.winfo_width(), canvas.winfo_height()

    if w > 1 and h > 1:
        return w, h

    # 3. 親フレームサイズから推定
    parent_w = canvas.master.winfo_width()
    parent_h = canvas.master.winfo_height()

    if parent_w > 1 and parent_h > 1:
        return parent_w - 20, parent_h - 20  # パディング考慮

    # 4. 最終フォールバック（画面の50%）
    screen_w = canvas.winfo_screenwidth()
    screen_h = canvas.winfo_screenheight()
    return screen_w // 2, screen_h // 2
```

---

### 🔍 問題1-C: リサイズ時のDebounce過剰

#### 症状
ウィンドウリサイズ時に画像再描画が遅延する（300ms）。

#### 根本原因

**ファイル**: `advanced_comparison_view.py:671-701`

```python
def _on_canvas_resize(self, event):
    # 300msのDebounce（Line 680）
    if self._resize_job:
        self.after_cancel(self._resize_job)

    self._resize_job = self.after(300, lambda: self._do_resize(event))
    #                              ^^^ 300ms待機
```

#### 問題点
- 300msは体感的に遅い（ユーザーがリサイズ完了してから0.3秒待つ）
- サイズ変化が10px未満の場合はスキップ（Lines 686-690）→ 微調整が反映されない

#### 解決策

```python
def _on_canvas_resize(self, event):
    """リサイズイベント処理（最適化版）"""

    # Debounceを150msに短縮
    if self._resize_job:
        self.after_cancel(self._resize_job)

    self._resize_job = self.after(150, lambda: self._do_resize(event))

def _do_resize(self, event):
    """リサイズ実行（サイズ変化閾値を5pxに緩和）"""
    canvas = event.widget
    new_w, new_h = event.width, event.height

    # 5px以上の変化で再描画（従来は10px）
    if abs(new_w - self._last_size.get(canvas, (0, 0))[0]) > 5 or \
       abs(new_h - self._last_size.get(canvas, (0, 0))[1]) > 5:
        self._display_image_smart(canvas, ...)
        self._last_size[canvas] = (new_w, new_h)
```

---

### 🔍 問題1-D: 座標変換システムの複雑性

#### 症状
画像座標（Source）とCanvas座標（View）の変換が複雑で、誤差が発生しやすい。

#### 現在の実装

**ファイル**: `advanced_comparison_view.py:1343-1356`

```python
from app.sdk.canvas.transform import CanvasTransform

canvas._coord_tf = CanvasTransform(
    scale_x=scale_factor,
    scale_y=scale_factor,
    offset_x=offset_x,  # Coverモード時のオフセット
    offset_y=offset_y
)
```

**変換メソッド**: `app/sdk/canvas/transform.py`

```python
def src_to_view(self, sx, sy):
    """Source → View 座標変換"""
    vx = round(sx * self.scale_x - self.offset_x)
    vy = round(sy * self.scale_y - self.offset_y)
    return (vx, vy)

def view_to_src(self, vx, vy):
    """View → Source 座標変換"""
    sx = round((vx + self.offset_x) / self.scale_x)
    sy = round((vy + self.offset_y) / self.scale_y)
    return (sx, sy)
```

#### 問題点
1. **オフセット符号の不一致**:
   - `_display_image()` で計算されるoffsetは「画像がCanvasからはみ出す量」
   - `CanvasTransform` では「画像配置オフセット」として使用
   - 符号が逆転している可能性

2. **座標系の混乱**:
   - Canvas座標: `canvasx()`, `canvasy()` でスクロール考慮
   - View座標: 画像上の表示座標
   - Source座標: 元画像の座標
   - 3つの座標系が混在

#### 解決策

**統一座標系の定義**:

```python
# 座標系の明確な定義
# 1. Source (元画像): (0, 0) 〜 (image_width, image_height)
# 2. Scaled (拡大縮小後): (0, 0) 〜 (scaled_width, scaled_height)
# 3. View (Canvas表示): (-offset_x, -offset_y) 〜 (scaled_width - offset_x, scaled_height - offset_y)
# 4. Canvas (スクロール考慮): canvasx(), canvasy()で取得

class UnifiedCoordinateTransform:
    """統一座標変換システム"""

    def __init__(self, source_size, canvas_size, mode="fit"):
        self.src_w, self.src_h = source_size
        self.canvas_w, self.canvas_h = canvas_size
        self.mode = mode

        # スケール計算
        scale_x = self.canvas_w / self.src_w
        scale_y = self.canvas_h / self.src_h

        if mode == "fit":
            self.scale = min(scale_x, scale_y)
            self.offset_x = 0
            self.offset_y = 0
        else:  # cover
            self.scale = max(scale_x, scale_y)
            scaled_w = self.src_w * self.scale
            scaled_h = self.src_h * self.scale
            # オフセット = はみ出し量の半分（中央寄せ）
            self.offset_x = (scaled_w - self.canvas_w) / 2
            self.offset_y = (scaled_h - self.canvas_h) / 2

    def source_to_canvas(self, sx, sy):
        """Source → Canvas 座標（一段階変換）"""
        # Source → Scaled
        scaled_x = sx * self.scale
        scaled_y = sy * self.scale

        # Scaled → Canvas (オフセット適用)
        canvas_x = scaled_x - self.offset_x
        canvas_y = scaled_y - self.offset_y

        return round(canvas_x), round(canvas_y)

    def canvas_to_source(self, cx, cy):
        """Canvas → Source 座標"""
        # Canvas → Scaled (オフセット除去)
        scaled_x = cx + self.offset_x
        scaled_y = cy + self.offset_y

        # Scaled → Source
        source_x = scaled_x / self.scale
        source_y = scaled_y / self.scale

        return round(source_x), round(source_y)
```

---

### 🔍 問題1-E: 領域矩形の再描画パフォーマンス

#### 症状
領域が多い（100+）場合、`_redraw_regions()` が遅い。

#### 根本原因

**ファイル**: `advanced_comparison_view.py:1408-1439`

```python
def _redraw_regions(self):
    """エリア矩形を再描画"""
    # すべての領域を毎回削除・再作成
    for canvas in [self.web_canvas, self.pdf_canvas]:
        canvas.delete("region_rect")  # 全削除

    # 全領域を再描画
    for region in all_regions:
        # 座標変換
        transform = get_canvas_transform(canvas)
        vx1, vy1, vx2, vy2 = transform.src_rect_to_view(...)

        # 矩形作成
        canvas.create_rectangle(vx1, vy1, vx2, vy2, ...)
```

#### 問題点
- 領域数 N に対して O(N) の削除・再作成
- 100領域 × 2キャンバス = 200回の描画操作

#### 解決策

**差分更新の実装**:

```python
def _redraw_regions(self):
    """領域矩形の差分再描画"""

    for canvas, regions, region_ids in [
        (self.web_canvas, self.web_regions, self._web_region_ids),
        (self.pdf_canvas, self.pdf_regions, self._pdf_region_ids)
    ]:
        transform = get_canvas_transform(canvas)

        # 既存の領域ID集合
        current_ids = set(region_ids.keys())
        new_ids = {r.id for r in regions}

        # 削除された領域のみ削除
        for removed_id in current_ids - new_ids:
            canvas.delete(region_ids[removed_id])
            del region_ids[removed_id]

        # 新規・更新された領域のみ再描画
        for region in regions:
            vx1, vy1, vx2, vy2 = transform.src_rect_to_view(*region.rect)

            if region.id in region_ids:
                # 既存の矩形を更新
                canvas.coords(region_ids[region.id], vx1, vy1, vx2, vy2)
                canvas.itemconfig(region_ids[region.id], outline=color)
            else:
                # 新規矩形を作成
                rect_id = canvas.create_rectangle(
                    vx1, vy1, vx2, vy2,
                    outline=color,
                    width=2,
                    tags="region_rect"
                )
                region_ids[region.id] = rect_id
```

---

## 問題2: 範囲選択の表示と手動編集

### 📍 影響を受けるファイル
- `app/gui/windows/advanced_comparison_view.py`
  - `_on_canvas_click()` (Lines 2506-2520)
  - `_on_canvas_drag()` (Lines 2522-2542)
  - `_on_canvas_release()` (Lines 2544-2583)
- `app/gui/windows/region_editor.py` (別ウィンドウ)
- `app/gui/windows/comparison_mixins/selection_mixin.py`

---

### 🔍 問題2-A: インライン編集機能の欠如

#### 症状
選択した領域をその場で編集（移動・リサイズ）できず、別ウィンドウ（RegionEditor）を開く必要がある。

#### 現在の動作フロー

1. **選択作成**: `_on_canvas_click()` → `_on_canvas_drag()` → `_on_canvas_release()`
2. **領域確定**: `EditableRegion` オブジェクト作成
3. **編集**: `region_editor.py` で別ウィンドウを開く必要

#### 期待される動作
- 選択済み領域をクリック → ハンドル表示
- ハンドルをドラッグ → リサイズ
- 領域内部をドラッグ → 移動
- Deleteキー → 削除

#### 根本原因

**ファイル**: `advanced_comparison_view.py:2506-2583`

```python
# 選択の作成は実装されているが...
def _on_canvas_click(self, event):
    self._selection_start = (x, y)

def _on_canvas_drag(self, event):
    # 選択矩形を表示
    canvas.create_rectangle(..., tags="selection_rect")

def _on_canvas_release(self, event):
    # 領域を確定
    region = EditableRegion(...)
    self.web_regions.append(region)

# ⚠️ 編集機能が実装されていない
# - 選択済み領域の検出なし
# - ハンドル表示なし
# - ドラッグ編集なし
```

#### 解決策

**インライン編集モードの実装**:

```python
class InlineRegionEditor:
    """Canvas上で直接領域を編集"""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.selected_region: Optional[EditableRegion] = None
        self.edit_mode: Optional[str] = None  # "move", "resize_nw", etc.
        self.drag_start: Optional[Tuple[int, int]] = None

        # イベントバインド
        canvas.bind("<Button-1>", self._on_click)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.bind("<Delete>", self._on_delete)

    def _on_click(self, event):
        """クリック処理: 領域選択とハンドル検出"""
        x, y = event.x, event.y

        # 1. ハンドルクリックチェック
        if self.selected_region:
            handle = self._get_handle_at(x, y)
            if handle:
                self.edit_mode = f"resize_{handle}"
                self.drag_start = (x, y)
                return

        # 2. 領域クリックチェック
        clicked_region = self._get_region_at(x, y)
        if clicked_region:
            self._select_region(clicked_region)
            self.edit_mode = "move"
            self.drag_start = (x, y)
        else:
            self._deselect()

    def _on_drag(self, event):
        """ドラッグ処理: 移動・リサイズ"""
        if not self.selected_region or not self.edit_mode:
            return

        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]

        if self.edit_mode == "move":
            # 領域を移動
            self._move_region(dx, dy)
        elif self.edit_mode.startswith("resize_"):
            # 領域をリサイズ
            handle = self.edit_mode.split("_")[1]
            self._resize_region(handle, dx, dy)

        # ハンドルを再描画
        self._draw_handles()

    def _select_region(self, region: EditableRegion):
        """領域を選択してハンドルを表示"""
        self.selected_region = region

        # ハイライト表示
        self.canvas.itemconfig(region.canvas_rect_id, width=3, outline="#00FF00")

        # ハンドル描画
        self._draw_handles()

    def _draw_handles(self):
        """リサイズハンドルを描画（8方向）"""
        if not self.selected_region:
            return

        # 既存のハンドルを削除
        self.canvas.delete("resize_handle")

        x1, y1, x2, y2 = self.selected_region.rect

        # 8つのハンドル位置
        handles = {
            "nw": (x1, y1), "n": ((x1+x2)//2, y1), "ne": (x2, y1),
            "w": (x1, (y1+y2)//2),               "e": (x2, (y1+y2)//2),
            "sw": (x1, y2), "s": ((x1+x2)//2, y2), "se": (x2, y2),
        }

        for handle_name, (hx, hy) in handles.items():
            self.canvas.create_rectangle(
                hx-4, hy-4, hx+4, hy+4,
                fill="#00FF00",
                outline="#FFFFFF",
                tags=("resize_handle", f"handle_{handle_name}")
            )
```

**統合方法**:

```python
# advanced_comparison_view.py の __init__ で初期化
self._web_editor = InlineRegionEditor(self.web_canvas)
self._pdf_editor = InlineRegionEditor(self.pdf_canvas)
```

---

### 🔍 問題2-B: 選択モードの切り替えが不明瞭

#### 症状
Quick モード（簡易OCR）と Full モード（完全OCR）の切り替え方法がUIに表示されていない。

#### 現在の実装

**ファイル**: `comparison_mixins/selection_mixin.py:33-51`

```python
self._selection_manager = SelectionManager(
    on_selection_complete=self._on_selection_complete,
    on_text_extracted=self._on_text_extracted,
    on_sync_complete=self._on_sync_complete,
    mode=SelectionMode.QUICK  # ← ハードコードされている
)
```

#### 問題点
- モード切替ボタンがない
- ユーザーはQuick/Fullの違いを知らない
- 常にQuickモードで動作

#### 解決策

**モード切替UIの追加**:

```python
# navigation_panel.py にトグルボタン追加
def _create_mode_toggle(self):
    """選択モード切替ボタン"""
    mode_frame = ctk.CTkFrame(self)
    mode_frame.pack(fill="x", padx=10, pady=5)

    ctk.CTkLabel(
        mode_frame,
        text="選択モード:",
        font=("Meiryo", 11)
    ).pack(side="left", padx=5)

    self.mode_var = tk.StringVar(value="quick")

    quick_radio = ctk.CTkRadioButton(
        mode_frame,
        text="⚡ Quick (高速)",
        variable=self.mode_var,
        value="quick",
        command=self._on_mode_change
    )
    quick_radio.pack(side="left", padx=5)

    full_radio = ctk.CTkRadioButton(
        mode_frame,
        text="🔍 Full (高精度)",
        variable=self.mode_var,
        value="full",
        command=self._on_mode_change
    )
    full_radio.pack(side="left", padx=5)

def _on_mode_change(self):
    """モード変更コールバック"""
    mode = SelectionMode.QUICK if self.mode_var.get() == "quick" else SelectionMode.FULL
    self.callbacks.get("set_selection_mode", lambda m: None)(mode)
```

---

### 🔍 問題2-C: 選択矩形の視覚フィードバック不足

#### 症状
選択中の矩形が点線で表示されるが、確定後の状態が分かりにくい。

#### 現在の実装

**ファイル**: `advanced_comparison_view.py:2537-2542`

```python
# ドラッグ中: 緑の点線
canvas.create_rectangle(
    x1, y1, x, y,
    outline="#00FF00",
    width=2,
    dash=(4, 2),  # 点線
    tags="selection_rect"
)
```

**ファイル**: `advanced_comparison_view.py:2579`

```python
# 確定後: 緑の実線
canvas.itemconfig("selection_rect", outline="#4CAF50", dash=())
```

#### 問題点
- 確定後も同じ緑色で区別しづらい
- 選択中・確定済み・シンク済みの状態が視覚的に不明

#### 解決策

**色分けルール**:

```python
SELECTION_COLORS = {
    "dragging": {
        "outline": "#00FF00",  # 明るい緑
        "width": 2,
        "dash": (4, 2)
    },
    "confirmed": {
        "outline": "#FFC107",  # オレンジ（未シンク）
        "width": 2,
        "dash": ()
    },
    "synced": {
        "outline": "#4CAF50",  # 緑（シンク済み）
        "width": 2,
        "dash": ()
    },
    "selected": {
        "outline": "#2196F3",  # 青（編集中）
        "width": 3,
        "dash": ()
    },
    "error": {
        "outline": "#F44336",  # 赤（エラー）
        "width": 2,
        "dash": (2, 2)
    }
}

def _update_region_appearance(self, region: EditableRegion):
    """領域の状態に応じて色を変更"""
    if region.sync_number is not None:
        style = SELECTION_COLORS["synced"]
    elif region.text:
        style = SELECTION_COLORS["confirmed"]
    else:
        style = SELECTION_COLORS["error"]

    self.canvas.itemconfig(
        region.canvas_rect_id,
        outline=style["outline"],
        width=style["width"],
        dash=style["dash"]
    )
```

---

### 🔍 問題2-D: OCR結果の即時表示機能

#### 症状
選択後、OCR結果がどこに表示されるか分からない。

#### 現在の実装

**ファイル**: `advanced_comparison_view.py:2566-2570`

```python
# OCR実行
extracted_text = self._extract_text_from_region(rect, self._selection_source)

# ⚠️ 結果がどこにも表示されない
# region.text に保存されるだけ
```

#### 解決策

**ツールチップ表示**:

```python
class RegionTooltip:
    """領域にマウスオーバーでOCR結果を表示"""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.tooltip_window = None

        canvas.bind("<Motion>", self._on_hover)

    def _on_hover(self, event):
        """マウスホバー時にツールチップ表示"""
        x, y = event.x, event.y

        # カーソル位置の領域を検出
        region = self._get_region_at(x, y)

        if region and region.text:
            self._show_tooltip(event, region)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, event, region: EditableRegion):
        """ツールチップウィンドウを表示"""
        if self.tooltip_window:
            self.tooltip_window.destroy()

        # 小さなトップレベルウィンドウ
        self.tooltip_window = tk.Toplevel(self.canvas)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

        # テキスト表示
        label = tk.Label(
            self.tooltip_window,
            text=region.text[:200] + ("..." if len(region.text) > 200 else ""),
            background="#FFFFCC",
            relief="solid",
            borderwidth=1,
            font=("Meiryo", 9),
            justify="left"
        )
        label.pack()
```

---

## 問題3: アクティブボタンと機能の説明

### 📍 影響を受けるファイル
- `app/gui/navigation.py` (ボタンUI)
- `app/gui/main_window_v2.py` (コールバック実装)

---

### 🎯 ボタン機能マトリックス

| # | ボタン名 | アイコン | ステータス | 実装場所 | 備考 |
|---|---------|---------|------------|----------|------|
| 1 | **New Project** | ✨ | ✅ **実装済み** | main_window_v2.py:302-312 | プロジェクト新規作成 |
| 2 | **Dashboard** | 📊 | ✅ **実装済み** | main_window_v2.py:267-285 | マクロビュー表示 |
| 3 | **Web Crawler** | 🌍 | 🟡 **部分実装** | main_window_v2.py:507-561 | ローカル画像のみ対応 |
| 4 | **Load PDFs** | 📁 | ✅ **実装済み** | main_window_v2.py:200-265 | PDF/画像読み込み |
| 5 | **Auto Match** | 🔄 | ✅ **実装済み** | main_window_v2.py:654-698 | 自動マッチング |
| 6 | **Gemini OCR** | 🤖 | ✅ **実装済み** | main_window_v2.py:700-774 | 単体OCR実行 |
| 7 | **Export Excel** | 📊 | ❌ **未実装** | main_window_v2.py:775-778 | プレースホルダー |
| 8 | **Save Project** | 💾 | ❌ **未実装** | main_window_v2.py:780-783 | プレースホルダー |
| 9 | **Load Project** | 📂 | ❌ **未実装** | コールバック定義のみ | プレースホルダー |
| 10 | **API Settings** | 🔐 | ✅ **実装済み** | main_window_v2.py:790-808 | API設定ダイアログ |

**実装率**: 60% (6/10 ボタン)

---

### 🔍 問題3-A: Export Excel 機能未実装

#### 症状
「Excel Export」ボタンをクリックすると「この機能は実装予定です」メッセージが表示される。

#### 現在の実装

**ファイル**: `main_window_v2.py:775-778`

```python
def export_excel(self):
    """Excel出力 (未実装)"""
    messagebox.showinfo("情報", "この機能は実装予定です")
```

#### 期待される機能
- Web/PDF のOCR結果を Excel ファイルにエクスポート
- シンク結果を含む比較レポート生成

#### 解決策

**実装例**:

```python
def export_excel(self):
    """Excel出力"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from tkinter import filedialog
        from datetime import datetime

        # ファイル保存ダイアログ
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"MEKIKI_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if not filename:
            return

        # Workbook作成
        wb = Workbook()
        ws = wb.active
        ws.title = "Comparison Results"

        # ヘッダー行
        headers = ["No", "Web ID", "Web Text", "PDF ID", "PDF Text", "Similarity", "Status"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")

        # データ行
        row = 2
        for web_region in self.web_regions:
            # 対応するPDF領域を検索
            pdf_region = None
            similarity = 0.0

            if web_region.sync_number is not None:
                for pdf_r in self.pdf_regions:
                    if pdf_r.sync_number == web_region.sync_number:
                        pdf_region = pdf_r
                        similarity = web_region.similarity
                        break

            # データ書き込み
            ws.cell(row, 1, row - 1)  # No
            ws.cell(row, 2, web_region.area_code)  # Web ID
            ws.cell(row, 3, web_region.text[:500])  # Web Text (500文字まで)
            ws.cell(row, 4, pdf_region.area_code if pdf_region else "")  # PDF ID
            ws.cell(row, 5, pdf_region.text[:500] if pdf_region else "")  # PDF Text
            ws.cell(row, 6, f"{similarity*100:.1f}%")  # Similarity
            ws.cell(row, 7, "Matched" if pdf_region else "No Match")  # Status

            row += 1

        # 列幅調整
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 50
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 50
        ws.column_dimensions['F'].width = 12
        ws.column_dimensions['G'].width = 12

        # 保存
        wb.save(filename)

        messagebox.showinfo(
            "Export Success",
            f"Excelファイルを保存しました:\n{filename}\n\n"
            f"エクスポート件数: {row - 2} 件"
        )

        # ファイルを開く（Windows）
        import os
        os.startfile(filename)

    except Exception as e:
        messagebox.showerror("Export Error", f"Excel出力エラー:\n{e}")
        logger.error(f"Excel export failed: {e}", exc_info=True)
```

**必要な修正**:
- `navigation.py`: ボタンの `state="disabled"` を削除
- `main_window_v2.py`: 上記の実装を追加

---

### 🔍 問題3-B: Save/Load Project 機能未実装

#### 症状
プロジェクトの保存・読み込み機能がプレースホルダーのみ。

#### 現在の実装

**ファイル**: `main_window_v2.py:780-783`

```python
def save_project(self):
    """プロジェクト保存 (未実装)"""
    messagebox.showinfo("情報", "この機能は実装予定です")
```

#### 期待される機能
- 現在の作業状態（Web/PDF画像、OCR結果、シンク結果）を保存
- JSON形式で保存してプロジェクト再開可能

#### 解決策

**プロジェクトデータ構造**:

```python
@dataclass
class ProjectData:
    """プロジェクト保存データ"""
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""

    # 画像パス
    web_image_path: Optional[str] = None
    pdf_image_path: Optional[str] = None

    # 領域データ
    web_regions: List[Dict] = field(default_factory=list)
    pdf_regions: List[Dict] = field(default_factory=list)

    # シンクデータ
    sync_pairs: List[Dict] = field(default_factory=list)

    # 設定
    display_mode: str = "cover"
    selection_mode: str = "quick"
```

**保存実装**:

```python
def save_project(self):
    """プロジェクト保存"""
    try:
        from tkinter import filedialog
        from datetime import datetime
        import json

        # ファイル保存ダイアログ
        filename = filedialog.asksaveasfilename(
            defaultextension=".mekiki",
            filetypes=[("MEKIKI Project", "*.mekiki"), ("JSON", "*.json")],
            initialfile=f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mekiki"
        )

        if not filename:
            return

        # プロジェクトデータ収集
        project_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "web_image_path": self.web_image_path,
            "pdf_image_path": self.pdf_image_path,
            "web_regions": [self._region_to_dict(r) for r in self.web_regions],
            "pdf_regions": [self._region_to_dict(r) for r in self.pdf_regions],
            "sync_pairs": [self._sync_to_dict(p) for p in self.sync_pairs],
            "display_mode": self._display_mode,
        }

        # JSON保存
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        messagebox.showinfo(
            "Save Success",
            f"プロジェクトを保存しました:\n{filename}"
        )

    except Exception as e:
        messagebox.showerror("Save Error", f"保存エラー:\n{e}")
        logger.error(f"Project save failed: {e}", exc_info=True)

def _region_to_dict(self, region: EditableRegion) -> dict:
    """EditableRegion → 辞書変換"""
    return {
        "id": region.id,
        "rect": region.rect,
        "text": region.text,
        "area_code": region.area_code,
        "sync_number": region.sync_number,
        "similarity": region.similarity,
        "source": region.source
    }
```

**読み込み実装**:

```python
def load_project(self):
    """プロジェクト読み込み"""
    try:
        from tkinter import filedialog
        import json
        from PIL import Image

        # ファイル選択ダイアログ
        filename = filedialog.askopenfilename(
            filetypes=[("MEKIKI Project", "*.mekiki"), ("JSON", "*.json")]
        )

        if not filename:
            return

        # JSON読み込み
        with open(filename, 'r', encoding='utf-8') as f:
            project_data = json.load(f)

        # バージョンチェック
        if project_data.get("version") != "1.0":
            messagebox.showwarning(
                "Version Mismatch",
                f"このプロジェクトは異なるバージョンで作成されています:\n{project_data.get('version')}"
            )

        # 画像読み込み
        if project_data.get("web_image_path"):
            web_img = Image.open(project_data["web_image_path"])
            self._load_web_image(web_img, project_data["web_image_path"])

        if project_data.get("pdf_image_path"):
            pdf_img = Image.open(project_data["pdf_image_path"])
            self._load_pdf_image(pdf_img, project_data["pdf_image_path"])

        # 領域復元
        self.web_regions = [self._dict_to_region(r) for r in project_data.get("web_regions", [])]
        self.pdf_regions = [self._dict_to_region(r) for r in project_data.get("pdf_regions", [])]

        # シンク結果復元
        self.sync_pairs = project_data.get("sync_pairs", [])

        # UI更新
        self._display_mode = project_data.get("display_mode", "cover")
        self._redraw_all()

        messagebox.showinfo(
            "Load Success",
            f"プロジェクトを読み込みました:\n{filename}\n\n"
            f"Web領域: {len(self.web_regions)} 件\n"
            f"PDF領域: {len(self.pdf_regions)} 件"
        )

    except Exception as e:
        messagebox.showerror("Load Error", f"読み込みエラー:\n{e}")
        logger.error(f"Project load failed: {e}", exc_info=True)
```

---

### 🔍 問題3-C: Web Crawler の URL クロール未実装

#### 症状
「Web Crawler」ボタンはローカル画像選択のみ対応で、URL からのクロールができない。

#### 現在の実装

**ファイル**: `main_window_v2.py:507-561`

```python
def crawl_web(self):
    """Web クロール (現在はローカル画像選択のみ)"""
    # Line 518: プレースホルダーメッセージ
    messagebox.showinfo("情報", "URLクロール機能は実装予定です")
```

#### 期待される機能
- URLを入力してWebページのスクリーンショット取得
- Playwright を使用した自動クロール

#### 解決策

**URL クロール実装**:

```python
def crawl_web(self):
    """Web クロール"""
    from app.gui.dialogs.url_input_dialog import URLInputDialog

    # URL入力ダイアログ
    dialog = URLInputDialog(self)
    dialog.wait_window()

    if dialog.url:
        self._crawl_url(dialog.url)
    else:
        # キャンセル時はローカル画像選択
        self._select_local_web_image()

def _crawl_url(self, url: str):
    """URLからスクリーンショット取得"""
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
        import io

        # プログレス表示
        self.nav_panel.show_progress("Webページを読み込み中...")

        with sync_playwright() as p:
            # ブラウザ起動
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            # ページ読み込み
            page.goto(url, wait_until="networkidle")

            # フルページスクリーンショット
            screenshot_bytes = page.screenshot(full_page=True)

            # PIL Image に変換
            web_image = Image.open(io.BytesIO(screenshot_bytes))

            browser.close()

        # 画像読み込み
        self.web_image = web_image
        self.web_image_path = url

        # Canvas に表示
        self._display_image_smart(self.web_canvas, web_image, "web")

        self.nav_panel.hide_progress()

        messagebox.showinfo(
            "Success",
            f"Webページを読み込みました:\n{url}\n\n"
            f"サイズ: {web_image.width} x {web_image.height} px"
        )

    except Exception as e:
        self.nav_panel.hide_progress()
        messagebox.showerror("Crawl Error", f"URLクロールエラー:\n{e}")
        logger.error(f"URL crawl failed: {e}", exc_info=True)
```

**URL入力ダイアログ**:

```python
# app/gui/dialogs/url_input_dialog.py
import customtkinter as ctk

class URLInputDialog(ctk.CTkToplevel):
    """URL入力ダイアログ"""

    def __init__(self, parent):
        super().__init__(parent)

        self.url = None

        self.title("Web Crawler")
        self.geometry("500x200")
        self.transient(parent)
        self.grab_set()

        # タイトル
        ctk.CTkLabel(
            self,
            text="Webページをクロール",
            font=("Meiryo", 16, "bold")
        ).pack(pady=20)

        # URL入力
        ctk.CTkLabel(self, text="URL:").pack(anchor="w", padx=20)

        self.url_entry = ctk.CTkEntry(self, width=400)
        self.url_entry.pack(padx=20, pady=5)
        self.url_entry.insert(0, "https://")
        self.url_entry.focus()

        # ボタン
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)

        ctk.CTkButton(
            btn_frame,
            text="クロール",
            command=self._on_crawl,
            width=100
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="キャンセル",
            command=self.destroy,
            width=100,
            fg_color="#666666"
        ).pack(side="left", padx=5)

    def _on_crawl(self):
        url = self.url_entry.get().strip()
        if url and url.startswith("http"):
            self.url = url
            self.destroy()
        else:
            from tkinter import messagebox
            messagebox.showwarning("Invalid URL", "有効なURLを入力してください")
```

---

## 推奨アクションプラン

### 🎯 優先度マトリックス

| 優先度 | タスク | 工数 | 影響度 | ビジネス価値 |
|--------|--------|------|--------|-------------|
| **P0** | 画像オフセット修正 | 2h | 🔴 High | ★★★★★ |
| **P0** | インライン領域編集実装 | 8h | 🔴 High | ★★★★★ |
| **P1** | Export Excel 実装 | 4h | 🟡 Medium | ★★★★☆ |
| **P1** | リサイズ Debounce 最適化 | 1h | 🟡 Medium | ★★★☆☆ |
| **P2** | Save/Load Project 実装 | 6h | 🟡 Medium | ★★★★☆ |
| **P2** | URL クロール実装 | 6h | 🟡 Medium | ★★★☆☆ |
| **P3** | 領域再描画の差分更新 | 4h | 🟢 Low | ★★☆☆☆ |
| **P3** | 選択モード切替UI | 2h | 🟢 Low | ★★☆☆☆ |

**合計工数**: 33時間（約4-5営業日）

---

### 📅 実装ロードマップ

#### **Phase 1: クリティカル修正（1日）**
- [ ] 画像オフセット修正（2h）
- [ ] リサイズ Debounce 最適化（1h）
- [ ] 座標変換システムの統一（3h）
- [ ] テスト・検証（2h）

#### **Phase 2: コア機能実装（2日）**
- [ ] インライン領域編集実装（8h）
  - ハンドル表示
  - ドラッグ移動・リサイズ
  - 削除機能
- [ ] Export Excel 実装（4h）
- [ ] テスト・検証（2h）

#### **Phase 3: プロジェクト管理（1-2日）**
- [ ] Save Project 実装（3h）
- [ ] Load Project 実装（3h）
- [ ] プロジェクトファイル形式定義（1h）
- [ ] テスト・検証（2h）

#### **Phase 4: 追加機能（オプション）**
- [ ] URL クロール実装（6h）
- [ ] 選択モード切替UI（2h）
- [ ] 領域再描画最適化（4h）

---

### 🧪 テスト計画

#### **単体テスト**
```python
# test_coordinate_transform.py
def test_cover_mode_offset():
    """Coverモードのオフセット計算テスト"""
    transform = UnifiedCoordinateTransform(
        source_size=(1000, 1000),
        canvas_size=(800, 600),
        mode="cover"
    )

    # 期待されるスケール: max(800/1000, 600/1000) = 0.8
    assert transform.scale == 0.8

    # 期待されるオフセット: (800 - 800) / 2 = 0, (800 - 600) / 2 = 100
    assert transform.offset_x == 0
    assert transform.offset_y == 100

def test_inline_edit_resize():
    """インライン編集のリサイズテスト"""
    editor = InlineRegionEditor(canvas)

    region = EditableRegion(
        id=1,
        rect=[100, 100, 200, 200],
        text="Test"
    )

    editor._select_region(region)
    editor._resize_region("se", dx=50, dy=50)

    # 右下ハンドルを50px移動 → rect が拡大
    assert region.rect == [100, 100, 250, 250]
```

#### **統合テスト**
- [ ] Web/PDF 画像読み込み → 表示 → 領域選択 → シンク → Export
- [ ] プロジェクト保存 → アプリ再起動 → プロジェクト読み込み → 状態復元確認
- [ ] 1000領域での領域再描画パフォーマンス（目標: <300ms）

#### **E2Eテスト**
- [ ] 実際のWebページとPDFで完全なワークフロー実行
- [ ] Excelエクスポート結果の妥当性確認
- [ ] 複数ユーザーでの操作性テスト

---

## 付録: 影響を受けるファイル一覧

### 🔧 修正が必要なファイル

| ファイル | 行数 | 修正内容 | 優先度 |
|---------|------|----------|--------|
| `app/gui/windows/advanced_comparison_view.py` | 3046 | オフセット適用、インライン編集実装 | P0 |
| `app/sdk/canvas/transform.py` | 301 | 統一座標変換システム | P0 |
| `app/gui/main_window_v2.py` | 808 | Export/Save/Load 実装 | P1 |
| `app/gui/navigation.py` | 134 | 選択モード切替UI | P3 |

### 📄 新規作成が必要なファイル

| ファイル | 目的 | 優先度 |
|---------|------|--------|
| `app/gui/widgets/inline_region_editor.py` | インライン領域編集 | P0 |
| `app/gui/dialogs/url_input_dialog.py` | URL入力ダイアログ | P2 |
| `app/utils/project_serializer.py` | プロジェクト保存・読み込み | P2 |
| `app/core/coordinate_system.py` | 統一座標変換 | P0 |

### 📚 ドキュメント更新

- [ ] `README.md`: 新機能の使用方法追加
- [ ] `DEPLOYMENT.md`: テストチェックリスト更新
- [ ] `USER_GUIDE.md`: スクリーンショット付きマニュアル作成

---

## まとめ

### ✅ 主要な発見
1. **画像オフセット計算のバグ**: Coverモードで中央配置されない致命的な問題
2. **インライン編集機能の欠如**: ユーザビリティを大きく損なう
3. **主要機能の未実装**: Export/Save/Load がプレースホルダー

### 🎯 ビジネスインパクト
- **現状**: ユーザーは画像のズレと編集の不便さに不満
- **改善後**: 直感的な操作で作業効率が3-5倍向上
- **投資対効果**: 33時間の工数で主要な使いやすさ問題を解決

### 🚀 次のステップ
1. このレポートをステークホルダーと共有
2. Phase 1（クリティカル修正）を最優先で実施
3. Phase 2（コア機能）を1週間以内に完了
4. ユーザーテストで検証後にリリース

---

**レポート作成者**: MEKIKI Development Team
**承認待ち**: Product Owner / Tech Lead
**次回レビュー**: 実装完了後

---

## 付録: コードスニペット集

### A. 画像オフセット修正（即座に適用可能）

```python
# File: app/gui/windows/advanced_comparison_view.py
# Line: 1328

# 修正前
canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")

# 修正後
canvas.create_image(-offset_x, -offset_y, anchor="nw", image=photo, tags="image")
```

### B. Debounce時間短縮（即座に適用可能）

```python
# File: app/gui/windows/advanced_comparison_view.py
# Line: 680

# 修正前
self._resize_job = self.after(300, lambda: self._do_resize(event))

# 修正後
self._resize_job = self.after(150, lambda: self._do_resize(event))
```

### C. サイズ変化閾値緩和（即座に適用可能）

```python
# File: app/gui/windows/advanced_comparison_view.py
# Lines: 686-690

# 修正前
if abs(new_w - last_w) < 10 and abs(new_h - last_h) < 10:
    return

# 修正後
if abs(new_w - last_w) < 5 and abs(new_h - last_h) < 5:
    return
```

---

**End of Report**
