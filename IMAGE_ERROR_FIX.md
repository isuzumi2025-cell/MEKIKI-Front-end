# 画像表示エラー修正完了報告

## 🐛 エラー内容
```
画像読み込みエラー: 'NoneType' object has no attribute 'read'
```

## 🔍 原因分析
`Image.open(io.BytesIO(bytes))`に`None`または空のバイト列が渡されていました。

**発生箇所:**
1. スクリーンショット取得時にデータが空
2. エラー発生時に`None`が画像として格納される
3. 画像変換時の検証不足

## ✅ 修正内容

### 1. `app/core/scraper.py` - スクレイピング側

#### 修正A: スクリーンショット取得時の検証強化
```python
# Before
viewport_bytes = page.screenshot(full_page=False)
viewport_image = Image.open(io.BytesIO(viewport_bytes))

# After
viewport_bytes = page.screenshot(full_page=False)

# バイトデータの検証
if viewport_bytes and len(viewport_bytes) > 0:
    try:
        viewport_image = Image.open(io.BytesIO(viewport_bytes))
    except Exception as e:
        print(f"⚠️ 1画面画像変換エラー: {str(e)}")
        viewport_image = self._create_placeholder_image("1画面画像取得失敗")
else:
    viewport_image = self._create_placeholder_image("1画面画像取得失敗")
```

#### 修正B: プレースホルダー画像生成メソッド追加
```python
def _create_placeholder_image(self, message: str = "画像なし", width: int = 1280, height: int = 800) -> Image.Image:
    """
    プレースホルダー画像を作成
    グレー背景 + 赤枠 + エラーメッセージ
    """
    img = Image.new('RGB', (width, height), color='#2B2B2B')
    draw = ImageDraw.Draw(img)
    
    # 赤い枠
    margin = 50
    draw.rectangle(
        [margin, margin, width - margin, height - margin],
        outline='#FF4444',
        width=5
    )
    
    # エラーメッセージ
    text = f"⚠️ {message}"
    text_width = len(text) * 10
    text_x = (width - text_width) // 2
    text_y = (height // 2)
    draw.text((text_x, text_y), text, fill='#FF4444')
    
    return img
```

#### 修正C: エラー時のNone回避
```python
# Before
results.append({
    "url": current_url,
    "title": f"取得失敗: {current_url}",
    "text": "",
    "full_image": None,  # ← ここが問題
    "viewport_image": None,
    "depth": depth,
    "error": error_msg
})

# After
error_placeholder = self._create_placeholder_image(f"取得失敗\n{error_msg[:30]}...")

results.append({
    "url": current_url,
    "title": f"取得失敗: {current_url}",
    "text": "",
    "full_image": error_placeholder,  # ✅ プレースホルダーを使用
    "viewport_image": error_placeholder,
    "depth": depth,
    "error": error_msg
})
```

### 2. `app/gui/sync_scroll_canvas.py` - 表示側

#### 修正D: load_imageメソッドの検証強化
```python
def load_image(self, image: Image.Image, title: str = ""):
    # 画像の検証
    if image is None:
        print("⚠️ 警告: 画像がNoneです")
        image = self._create_placeholder_image("画像なし")
    
    if not isinstance(image, Image.Image):
        print(f"⚠️ 警告: 画像の型が不正です: {type(image)}")
        image = self._create_placeholder_image("画像形式エラー")
    
    self.pil_image = image
    
    if title:
        self.header_label.configure(text=title)
    
    # PIL ImageをPhotoImageに変換
    try:
        self.tk_image = ImageTk.PhotoImage(self.pil_image)
    except Exception as e:
        print(f"⚠️ 画像変換エラー: {str(e)}")
        # エラー時はプレースホルダーを使用
        self.pil_image = self._create_placeholder_image(f"変換エラー\n{str(e)[:30]}")
        self.tk_image = ImageTk.PhotoImage(self.pil_image)
    
    # ... 以降の処理
```

#### 修正E: プレースホルダー画像メソッド追加
同様のメソッドを`SyncScrollCanvas`クラスにも追加。

## 📊 修正の効果

### Before（修正前）
```
スクリーンショット失敗
  ↓
None が返る
  ↓
Image.open(io.BytesIO(None))
  ↓
❌ 'NoneType' object has no attribute 'read'
  ↓
アプリクラッシュ
```

### After（修正後）
```
スクリーンショット失敗
  ↓
バイトデータをチェック
  ↓
空 or None なら
  ↓
✅ プレースホルダー画像を生成
  ↓
グレー背景 + 赤枠 + エラーメッセージ
  ↓
正常に表示継続
```

## 🎯 防御レイヤー（多段防御）

1. **データ取得時（scraper.py）**
   - スクリーンショットバイトの検証
   - 変換エラーのキャッチ
   - プレースホルダー生成

2. **エラー時（scraper.py）**
   - Noneを返さない
   - 必ずImageオブジェクトを返す

3. **表示時（sync_scroll_canvas.py）**
   - Noneチェック
   - 型チェック
   - 変換エラーのキャッチ

## 🧪 テストシナリオ

### ケース1: 正常な画像取得
```
✅ 通常通り画像が表示される
```

### ケース2: スクリーンショット失敗
```
✅ グレー背景 + 赤枠 + "1画面画像取得失敗" と表示
✅ アプリは継続動作
```

### ケース3: ページアクセスエラー
```
✅ グレー背景 + 赤枠 + "取得失敗\n[エラー内容]" と表示
✅ リストに赤文字で "❌ URL..." と表示
✅ アプリは継続動作
```

### ケース4: 画像変換エラー
```
✅ グレー背景 + 赤枠 + "変換エラー\n[エラー内容]" と表示
✅ コンソールに警告ログ出力
✅ アプリは継続動作
```

## 📝 追加されたインポート

### scraper.py
```python
from PIL import Image, ImageDraw, ImageFont  # ImageDraw 追加
```

### sync_scroll_canvas.py
```python
from PIL import Image, ImageTk, ImageDraw  # ImageDraw 追加
```

## ✅ 動作確認

```bash
# 構文チェック: 成功
python -m py_compile app/core/scraper.py
python -m py_compile app/gui/sync_scroll_canvas.py
python -m py_compile app/gui/dashboard.py
python -m py_compile app/gui/inspector.py

# 結果: Exit code: 0（全て成功）
```

## 🚀 次のステップ

1. アプリを起動
2. Dashboard を開く
3. Webクロールを実行
4. エラーページがある場合でもプレースホルダー画像が表示されることを確認
5. Inspector でも正常に表示されることを確認

---

**修正日:** 2025年12月22日  
**修正者:** AI Assistant (Claude Sonnet 4.5)  
**ステータス:** ✅ 完了

