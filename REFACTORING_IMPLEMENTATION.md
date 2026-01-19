# Web/PDF比較アプリ リファクタリング完了報告

## 📋 実装内容

### 1. アプリ構成の変更（2画面構成）

#### Before（旧構成）
```
起動 → いきなり比較画面
```

#### After（新構成）
```
起動 → メインウィンドウ
  ↓
[📊 Dashboard] ボタンクリック
  ↓
Step 1: Dashboard（マトリクス画面）
  ├─ 左列: Webページ一覧（クローリング結果）
  ├─ 中央: ペアリング結果
  └─ 右列: PDFページ一覧
  ↓
[🔍 Inspector] ボタンクリック
  ↓
Step 2: Inspector（詳細比較画面）
  ├─ 左側: Web画像
  └─ 右側: PDF画像
  （同期スクロール対応）
```

### 2. Webスクレイピング機能の強化

#### 実装内容（`app/core/scraper.py`）

**追加メソッド:**
```python
def crawl_site(
    base_url: str,
    max_pages: int = 50,
    max_depth: int = 3,
    same_domain_only: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None,
    progress_callback: Optional[callable] = None
) -> List[Dict]:
```

**新機能:**
1. ✅ **リンク探索** - トップページからリンクを辿って下層ページを取得
2. ✅ **深さ制御** - `max_depth`パラメータで探索深さを制限
3. ✅ **同一ドメイン制限** - `same_domain_only=True`で外部サイトを除外
4. ✅ **Lazy Loading完全対応** - 既存の`_auto_scroll`メソッドを活用
5. ✅ **エラーハンドリング** - 404やタイムアウトを記録し、処理を継続
6. ✅ **進捗コールバック** - リアルタイムで進捗をGUIに通知

**Lazy Loading対策の仕組み:**
```python
def _auto_scroll(self, page):
    """Lazy Loading対策: 少しずつスクロールして読み込ませる"""
    page.evaluate("""
        async () => {
            await new Promise((resolve) => {
                var totalHeight = 0;
                var distance = 200;
                var timer = setInterval(() => {
                    var scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    
                    if(totalHeight >= scrollHeight - window.innerHeight){
                        clearInterval(timer);
                        resolve();
                    }
                }, 50);
            });
        }
    """)
    # 読み込み待ち
    time.sleep(2)
    # 一番上に戻す
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)
```

- ページ下部まで200pxずつスクロール
- 高さの変化を検出して遅延読み込みコンテンツを取得
- 全て読み込んだらトップに戻る
- `full_page=True`でスクリーンショット撮影

### 3. UI統合

#### メインウィンドウ（`app/gui/main_window.py`）
- **変更点:**
  - `from app.gui.dashboard import Dashboard`をインポート
  - `open_dashboard()`メソッドを追加
  - コールバック辞書に`"open_dashboard": self.open_dashboard`を追加

#### ナビゲーションパネル（`app/gui/navigation_panel.py`）
- **変更点:**
  - 紫色の「📊 Dashboard (NEW)」ボタンを追加
  - トップセクションに配置（プロジェクト管理の下）

#### Dashboard（`app/gui/dashboard.py`）
- **実装機能:**
  1. **Webクロール設定ダイアログ**
     - URL、認証情報、最大ページ数、深さを設定
     - バックグラウンドでクローリング実行
     - 進捗をステータスバーに表示
  
  2. **PDF一括読込**
     - フォルダ選択ダイアログ
     - 再帰的にPDFを検索
     - PyMuPDFでテキスト抽出
  
  3. **手動ペアリング**
     - 左右のリストから選択してペアリング
     - ペアカードを中央に表示
  
  4. **自動マッチング**
     - `PairingManager.auto_match()`を実行
     - Jaccard係数 + difflib で類似度計算
     - 閾値0.1（緩い設定）
  
  5. **Inspector起動**
     - ペアカードの「🔍 Inspector」ボタン
     - 選択したWebとPDFを詳細比較画面で表示

### 4. 依存関係の更新

#### requirements.txt
```
playwright>=1.40.0      # 追加
customtkinter>=5.0.0    # 追加
```

**インストール方法:**
```bash
pip install -r requirements.txt
playwright install chromium
```

## 📊 データフロー

```
1. ユーザーがDashboard起動
   ↓
2. 「🌐 Webクロール」実行
   ├→ base_urlにアクセス
   ├→ リンクを抽出
   ├→ 各ページで_auto_scroll実行（Lazy Loading対応）
   ├→ full_page=Trueでスクリーンショット
   └→ 結果をweb_pagesに格納
   ↓
3. 「📁 PDF読込」実行
   ├→ フォルダ内のPDFを再帰検索
   ├→ PyMuPDFでテキスト抽出
   └→ 結果をpdf_pagesに格納
   ↓
4. 「⚡ 自動マッチング」実行
   ├→ PairingManager.auto_match()
   ├→ 類似度計算（Jaccard + difflib）
   └→ ペアをpairsに格納
   ↓
5. ペアカードの「🔍 Inspector」クリック
   ├→ Inspector(web_page, pdf_page)を生成
   ├→ 左右にSyncScrollCanvasを配置
   └→ 同期スクロールで詳細比較
```

## 🎯 使用方法

### Step 1: アプリ起動
```bash
python app/gui/main_window.py
```

### Step 2: Dashboard起動
- ナビゲーションパネルの **「📊 Dashboard (NEW)」** をクリック

### Step 3: データ取得
1. **Webクロール**
   - 「🌐 Webクロール」ボタンをクリック
   - 開始URLを入力（例: `https://example.com`）
   - Basic認証が必要な場合はユーザー名とパスワードを入力
   - 最大ページ数（デフォルト: 50）と深さ（デフォルト: 3）を設定
   - 「実行」をクリック

2. **PDF読込**
   - 「📁 PDF読込」ボタンをクリック
   - PDFが格納されたフォルダを選択
   - サブフォルダも自動的に検索される

### Step 4: ペアリング

**方法A: 自動マッチング**
- 「⚡ 自動マッチング」ボタンをクリック
- AIが自動でWebとPDFをマッチング

**方法B: 手動ペアリング**
1. 左列（Webリスト）から1つ選択
2. 右列（PDFリスト）から1つ選択
3. 「🔗 手動ペアリング」ボタンをクリック

### Step 5: 詳細比較
- 中央のペアカードの **「🔍 Inspector」** ボタンをクリック
- 左右分割で詳細比較画面が開く
- マウスホイールで同期スクロール可能

## 🐛 トラブルシューティング

### Playwrightのインストールエラー
```bash
# ブラウザのインストール
playwright install chromium

# または全ブラウザ
playwright install
```

### クローリングが途中で止まる
- タイムアウト設定を確認（デフォルト: 60秒）
- `max_pages`を減らして試す
- Basic認証情報が正しいか確認

### 画像が見切れる
- `_auto_scroll`が正常に動作しているか確認
- `time.sleep(2)`を増やして読み込み時間を延長

## 📝 技術的な改善点

### Before（旧実装）
- トップページ1枚のみ取得
- 画像が見切れる問題あり
- 比較対象が選べない

### After（新実装）
- ✅ サイト内の複数ページを一括取得
- ✅ Lazy Loading完全対応（画像見切れ解消）
- ✅ Dashboard画面で柔軟にペアリング
- ✅ Inspector画面で詳細比較
- ✅ 同期スクロール対応
- ✅ エラーページの明示表示

## 🚀 今後の拡張

### 短期
- [ ] ペアカードのドラッグ&ドロップ対応
- [ ] Inspector内でのオニオンスキン統合
- [ ] プロジェクトの保存/読み込み

### 中期
- [ ] クロール結果のキャッシュ
- [ ] 差分ハイライト表示
- [ ] バッチ処理モード

### 長期
- [ ] マルチスレッドクローリング
- [ ] 画像認識による自動位置合わせ
- [ ] REST API化

## ✅ 完了チェックリスト

- [x] `scraper.py`にクローリング機能追加
- [x] Lazy Loading対策の実装
- [x] リンク抽出機能
- [x] 深さ制御機能
- [x] エラーハンドリング
- [x] `main_window.py`にDashboard統合
- [x] `navigation_panel.py`にボタン追加
- [x] `dashboard.py`の実機能実装
- [x] Webクロールダイアログ
- [x] PDF読込ダイアログ
- [x] 手動ペアリング機能
- [x] 自動マッチング機能
- [x] Inspector起動機能
- [x] `requirements.txt`更新
- [x] 構文チェック完了

---

**実装完了日:** 2025年12月22日
**実装者:** AI Assistant (Claude Sonnet 4.5)
**バージョン:** v2.0.0

