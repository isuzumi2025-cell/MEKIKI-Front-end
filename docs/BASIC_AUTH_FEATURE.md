# 🔐 Basic認証機能実装ガイド

## 概要

Basic認証が必要なWebサイトでもスクレイピングできるように、新規プロジェクトダイアログとクローラーにBasic認証機能を追加しました。

---

## 📦 実装されたファイル

### 1. **`app/gui/dialogs/project_dialog.py`**
- ✅ Basic認証チェックボックス追加
- ✅ ユーザー名入力フィールド
- ✅ パスワード入力フィールド（マスク表示）
- ✅ チェックボックス連動の有効/無効切り替え
- ✅ 認証情報を結果に含める

### 2. **`app/core/enhanced_scraper.py`**
- ✅ `crawl_site`メソッドで`username`/`password`パラメータ受け取り
- ✅ Playwright `http_credentials`設定
- ✅ エイリアス`EnhancedScraper`追加（後方互換性）

### 3. **`app/gui/main_window.py`**
- ✅ `_crawl_web_pages`メソッドに認証パラメータ追加
- ✅ `start_analysis`から認証情報を渡す
- ✅ 認証情報のログ出力

---

## 🎨 UI構成

### ProjectDialog - Basic認証エリア

```
┌─────────────────────────────────────┐
│ 🌐 Web設定                          │
│                                     │
│ 対象URL: [https://example.com   ]  │
│ クロール深さ: [====●====] 2階層    │
│ 最大ページ数: [10] ページ           │
│                                     │
│ [✓] Basic認証を使用する             │
│                                     │
│ ユーザー名: [username            ]  │
│ パスワード:  [*******            ]  │
│                                     │
└─────────────────────────────────────┘
```

---

## 🚀 使用方法

### 1. ダイアログで認証情報を入力

```
1. 「➕ 新規プロジェクト」をクリック
   ↓
2. Web設定エリアで:
   - [✓] Basic認証を使用する チェック
   ↓
3. ユーザー名とパスワードを入力
   - ユーザー名: admin
   - パスワード: password123
   ↓
4. 「🚀 分析開始」クリック
```

### 2. 自動的にクローラーに渡される

認証情報は`start_analysis`メソッドを通じて`_crawl_web_pages`に渡され、Playwrightの`http_credentials`として設定されます。

---

## 🔧 技術実装

### ダイアログ側の実装

#### 1. チェックボックスとフィールド

```python
# Basic認証チェックボックス
self.use_auth_checkbox = ctk.CTkCheckBox(
    auth_frame,
    text="Basic認証を使用する",
    command=self._toggle_auth_fields
)

# ユーザー名
self.auth_username_entry = ctk.CTkEntry(
    username_frame,
    placeholder_text="username",
    state="disabled"  # 初期状態は無効
)

# パスワード（マスク表示）
self.auth_password_entry = ctk.CTkEntry(
    password_frame,
    placeholder_text="password",
    show="*",  # マスク表示
    state="disabled"
)
```

#### 2. 有効/無効の切り替え

```python
def _toggle_auth_fields(self):
    """Basic認証フィールドの有効/無効を切り替え"""
    if self.use_auth_checkbox.get():
        # チェックON → 有効化
        self.auth_username_entry.configure(state="normal")
        self.auth_password_entry.configure(state="normal")
    else:
        # チェックOFF → 無効化
        self.auth_username_entry.configure(state="disabled")
        self.auth_password_entry.configure(state="disabled")
```

#### 3. 結果に含める

```python
def _on_start_analysis(self):
    self.result = {
        "url": self.url_entry.get().strip(),
        # ... 他の設定 ...
        "use_auth": self.use_auth_checkbox.get(),
        "auth_user": self.auth_username_entry.get().strip() if self.use_auth_checkbox.get() else None,
        "auth_pass": self.auth_password_entry.get().strip() if self.use_auth_checkbox.get() else None
    }
```

---

### クローラー側の実装

#### EnhancedWebScraper - crawl_site

```python
def crawl_site(
    self,
    base_url: str,
    max_pages: int = 50,
    same_domain_only: bool = True,
    username: Optional[str] = None,  # ✅ 追加
    password: Optional[str] = None   # ✅ 追加
) -> List[Dict]:
    """サイト内をクローリング"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=self.headless)
        
        context_options = {
            'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
            'device_scale_factor': 2.0
        }
        
        # ✅ Basic認証設定
        if username and password:
            context_options['http_credentials'] = {
                'username': username,
                'password': password
            }
        
        context = browser.new_context(**context_options)
        page = context.new_page()
        
        # クローリング処理...
```

---

### MainWindow側の統合

#### start_analysis

```python
def start_analysis(self, config: Dict):
    """分析を開始"""
    # ✅ 認証情報のログ出力
    if config.get('use_auth'):
        print(f"Basic認証: 有効（ユーザー: {config.get('auth_user')}）")
    
    def _run_analysis():
        # ✅ クローラーに認証情報を渡す
        web_results = self._crawl_web_pages(
            config['url'],
            config['depth'],
            config['max_pages'],
            username=config.get('auth_user') if config.get('use_auth') else None,
            password=config.get('auth_pass') if config.get('use_auth') else None
        )
```

#### _crawl_web_pages

```python
def _crawl_web_pages(
    self,
    url: str,
    depth: int,
    max_pages: int,
    username: Optional[str] = None,  # ✅ 追加
    password: Optional[str] = None   # ✅ 追加
) -> List:
    """Webページをクロール"""
    from app.core.enhanced_scraper import EnhancedWebScraper
    
    scraper = EnhancedWebScraper()
    results = scraper.crawl_site(
        base_url=url,
        max_pages=max_pages,
        username=username,  # ✅ 渡す
        password=password   # ✅ 渡す
    )
```

---

## 📊 データフロー

```
ProjectDialog
  ↓
  use_auth: True
  auth_user: "admin"
  auth_pass: "password123"
  ↓
MainWindow.start_analysis(config)
  ↓
MainWindow._crawl_web_pages(
  username=config.get('auth_user'),
  password=config.get('auth_pass')
)
  ↓
EnhancedWebScraper.crawl_site(
  username=username,
  password=password
)
  ↓
Playwright browser.new_context(
  http_credentials={
    'username': username,
    'password': password
  }
)
```

---

## 🔐 セキュリティ

### 注意事項

1. **平文保存なし**: パスワードはメモリ内のみで保持され、ファイルには保存されません
2. **マスク表示**: UIではパスワードが`*`でマスクされます
3. **HTTPS推奨**: Basic認証は暗号化されていないため、HTTPS経由での使用を推奨します

### 今後の改善案

- [ ] 認証情報の暗号化保存
- [ ] 認証情報のプリセット管理
- [ ] OAuth2対応
- [ ] セッション管理

---

## 🧪 テスト

### 手動テスト手順

1. **Basic認証が必要なサイトを用意**
   - テスト用: http://httpbin.org/basic-auth/user/pass

2. **ダイアログでテスト**
   ```
   URL: http://httpbin.org/basic-auth/user/pass
   [✓] Basic認証を使用する
   ユーザー名: user
   パスワード: pass
   ```

3. **実行して確認**
   - 認証が成功してページが取得される
   - ログに「Basic認証: 有効」と表示される

---

## 💡 使用例

### 例1: 基本的な使用

```python
# ダイアログ入力:
{
    "url": "https://example.com/protected",
    "use_auth": True,
    "auth_user": "admin",
    "auth_pass": "secret123",
    "depth": 2,
    "max_pages": 10
}

# 結果:
# ✅ Basic認証でログイン
# ✅ 保護されたページをスクレイピング
# ✅ リンクをたどってクローリング
```

### 例2: 認証なし

```python
# ダイアログ入力:
{
    "url": "https://example.com",
    "use_auth": False,  # チェックOFF
    # auth_userとauth_passはNone
}

# 結果:
# ✅ 通常のスクレイピング
# ✅ 認証情報なし
```

---

## 🎯 実装のポイント

### 1. **チェックボックス連動**

チェックON/OFFで入力フィールドの有効/無効が切り替わる

### 2. **条件付き取得**

```python
auth_user = entry.get() if checkbox.get() else None
```

認証を使用しない場合は`None`を渡す

### 3. **Playwright統合**

```python
context_options['http_credentials'] = {
    'username': username,
    'password': password
}
```

Playwrightの標準機能でBasic認証を実現

---

## 📝 まとめ

### ✅ 実装済み機能

- [x] ダイアログにBasic認証フィールド追加
- [x] チェックボックス連動の有効/無効切り替え
- [x] パスワードのマスク表示
- [x] クローラーへの認証情報の受け渡し
- [x] Playwright `http_credentials` 設定
- [x] 認証情報のログ出力

### 🔜 今後の拡張

- [ ] 認証情報の保存機能
- [ ] 複数の認証設定プリセット
- [ ] OAuth2/OpenID Connect対応
- [ ] セッションCookie対応

---

**🔐 Basic認証機能の実装完了！**

これで、Basic認証が必要なサイトでも問題なくスクレイピングできるようになりました。

