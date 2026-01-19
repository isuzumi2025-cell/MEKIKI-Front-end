# MEKIKI OCR - APIキー設定ガイド

**最終更新**: 2026-01-19
**対象バージョン**: v1.0.0

---

## 🔐 セキュアなAPIキー管理システム

MEKIKI OCRでは、**暗号化保存によるセキュアなAPIキー管理**を実装しています。

### ✅ 正しい設定方法（推奨）

#### 方法1: GUI経由で設定（最も簡単）

1. **MEKIKI OCRを起動**

2. **設定ボタンをクリック**
   - ナビゲーションパネル下部の「⚙️ API設定」ボタン
   - または、キーボードショートカット: `Ctrl+,`（Comma）

3. **APIキーを入力**
   - **Gemini API Key** (推奨): Google AI Studioで取得
   - OpenAI API Key (オプション)
   - Grok API Key (オプション)
   - Anthropic API Key (オプション)

4. **「保存」をクリック**
   - 自動的に暗号化されて `config/api_keys.json` に保存
   - 環境変数にも設定される

#### 方法2: 手動で設定ファイルを編集

⚠️ **非推奨**: 平文でキーを保存するため、GUI経由での設定を推奨します。

---

## 📁 保存場所

### 新システム（暗号化保存）
```
OCR/
└── config/
    └── api_keys.json  # 暗号化されたAPIキー（XOR + Base64）
```

### 旧システム（非推奨）
```
OCR/
├── .env              # 環境変数ファイル（平文）
└── config.py         # Pythonコード内にハードコード（セキュリティリスク）
```

---

## 🔑 APIキーの取得方法

### Gemini API Key（推奨・無料枠あり）

1. **Google AI Studio にアクセス**
   - URL: https://makersuite.google.com/app/apikey
   - または: https://aistudio.google.com/app/apikey

2. **Googleアカウントでログイン**

3. **「Create API Key」をクリック**
   - 既存のGoogle Cloud プロジェクトを選択
   - または「Create API key in new project」で新規作成

4. **生成されたキーをコピー**
   - 形式: `AIzaSy...` (39文字)

5. **MEKIKI OCRの設定画面に貼り付け**

#### 無料枠
- **60 requests per minute (RPM)**
- **1,500 requests per day (RPD)**
- 個人利用・開発用途には十分

---

### OpenAI API Key（オプション）

1. **OpenAI Platform にアクセス**
   - URL: https://platform.openai.com/api-keys

2. **ログイン**

3. **「Create new secret key」をクリック**

4. **生成されたキーをコピー**
   - 形式: `sk-...` (51文字)
   - ⚠️ **一度しか表示されない**のでメモしておく

5. **MEKIKI OCRの設定画面に貼り付け**

#### 料金
- **従量課金制**（無料枠なし）
- GPT-4: $0.03 / 1K tokens（入力）
- GPT-3.5-turbo: $0.0015 / 1K tokens（入力）

---

### Grok API Key（オプション・未対応）

現在、Grok API は公開されていません。

---

### Anthropic API Key（Claude API）

1. **Anthropic Console にアクセス**
   - URL: https://console.anthropic.com/

2. **ログイン**

3. **「Create Key」をクリック**

4. **生成されたキーをコピー**
   - 形式: `sk-ant-...`

5. **MEKIKI OCRの設定画面に貼り付け**

#### 料金
- **従量課金制**（$5の無料クレジット付き）
- Claude 3.5 Sonnet: $3 / 1M tokens（入力）

---

## ⚠️ よくある問題と解決方法

### 問題1: 「APIキーが無効です」エラー

#### 原因と対処

1. **キーにスペースが含まれている**
   - コピー時に前後にスペースが入ることがある
   - 設定画面で再入力（前後のスペースを削除）

2. **キーの期限切れ**
   - Google AI Studioで新しいキーを発行
   - 古いキーを削除

3. **プロジェクトが無効化されている**
   - Google Cloud Console でプロジェクトのステータス確認
   - 請求が有効になっているか確認

4. **API が有効化されていない**
   - Google Cloud Console → APIとサービス
   - 「Generative Language API」を有効化

#### 確認方法

```bash
# コマンドプロンプトで確認
echo %GEMINI_API_KEY%

# または、Pythonで確認
python -c "import os; print(os.getenv('GEMINI_API_KEY'))"
```

---

### 問題2: 「APIタイムアウト」エラー

#### 原因と対処

1. **インターネット接続の問題**
   - ネットワーク接続を確認
   - プロキシ設定を確認

2. **レート制限に達した**
   - 60 RPM（1分あたり60リクエスト）の制限
   - しばらく待ってから再試行

3. **ファイアウォール/アンチウイルス**
   - HTTPS通信がブロックされていないか確認
   - 一時的に無効化してテスト

---

### 問題3: `config.py` の文法エラー

#### 症状
```python
# config.py
GEMINI_API_KEY = "your-api-key-here
# ↑ 閉じ引用符がない
```

#### 対処

**このファイルは直接編集しないでください。**

MEKIKI OCRの新システムでは、`config.py`を直接編集する必要はありません。

正しい設定方法：
1. MEKIKI OCRを起動
2. 「⚙️ API設定」ボタンをクリック
3. GUIでAPIキーを入力
4. 保存

---

### 問題4: 古い `.env` ファイルとの競合

#### 症状
- GUI で設定したキーが反映されない
- 古いキーが使われている

#### 対処

1. **`.env` ファイルを削除または名前変更**
   ```
   OCR/.env → OCR/.env.backup
   ```

2. **config.py を確認**
   - 以下のコードが含まれているか確認：
   ```python
   from app.config.api_manager import get_api_manager
   _USE_NEW_API_MANAGER = True
   ```

3. **アプリを再起動**

---

## 🔧 トラブルシューティング

### デバッグモード

APIキー読み込みの詳細を確認：

```python
# config.py の最後に追加
if __name__ == "__main__":
    print("=== API Key Debug Info ===")
    print(f"Using new API manager: {_USE_NEW_API_MANAGER}")
    print(f"Gemini API Key: {'✅ Set' if Config.GEMINI_API_KEY else '❌ Not Set'}")
    print(f"OpenAI API Key: {'✅ Set' if Config.OPENAI_API_KEY else '❌ Not Set'}")
    print(f"Grok API Key: {'✅ Set' if Config.GROK_API_KEY else '❌ Not Set'}")
    print(f"Anthropic API Key: {'✅ Set' if Config.ANTHROPIC_API_KEY else '❌ Not Set'}")
```

実行：
```bash
python config.py
```

---

## 📚 設定ファイルの構造

### config/api_keys.json（暗号化）

```json
{
  "gemini_api_key": "encrypted_base64_string_here",
  "openai_api_key": null,
  "grok_api_key": null,
  "anthropic_api_key": null,
  "created_at": "2026-01-19T10:30:00",
  "updated_at": "2026-01-19T10:30:00"
}
```

⚠️ **このファイルは手動で編集しないでください。**
暗号化されているため、直接編集すると破損します。

### 暗号化の仕組み

```python
# 暗号化: XOR + Base64
def _encrypt(self, text: str) -> str:
    key = self._get_encryption_key()  # PCのホスト名から生成
    encrypted_bytes = bytearray()
    for i, char in enumerate(text.encode('utf-8')):
        encrypted_bytes.append(char ^ key[i % len(key)])
    return base64.b64encode(encrypted_bytes).decode('utf-8')
```

---

## ✅ チェックリスト

### 初回セットアップ

- [ ] MEKIKI OCRをダウンロード・解凍
- [ ] アプリを起動（MEKIKI.exe）
- [ ] 「⚙️ API設定」を開く
- [ ] Gemini API Keyを入力（必須）
- [ ] 「保存」をクリック
- [ ] 設定成功メッセージを確認
- [ ] アプリを再起動（推奨）
- [ ] OCR機能をテスト

### 動作確認

- [ ] 「🤖 Gemini OCR」ボタンが有効
- [ ] 画像を読み込んでOCR実行
- [ ] エラーが出ない
- [ ] OCR結果が表示される

### トラブル時

- [ ] logs/mekiki_error.log を確認
- [ ] APIキーを再入力
- [ ] インターネット接続を確認
- [ ] ファイアウォール設定を確認
- [ ] 診断レポート生成（エラーダイアログで「📤 レポート送信」）

---

## 🆘 サポート

### ログファイル

エラー発生時は以下のログを確認：

```
OCR/
└── logs/
    ├── mekiki.log         # 全ログ（JSON形式）
    ├── mekiki_error.log   # エラーログのみ
    └── diagnostic.log     # 診断モード時の詳細ログ
```

### サポート連絡先

- **メール**: support@mekiki-project.example.com
- **Issue Tracker**: https://github.com/your-org/mekiki/issues

### 診断レポート送信

1. エラーダイアログで「📤 レポート送信」をクリック
2. 生成されたZIPファイルを保存
3. サポートにメール添付で送信

---

## 🔒 セキュリティのベストプラクティス

### DO（推奨）
- ✅ GUI経由でAPIキーを設定
- ✅ 定期的にキーをローテーション
- ✅ 使用しないキーは削除
- ✅ APIキー使用量をモニタリング

### DON'T（非推奨）
- ❌ APIキーをGitにコミット
- ❌ APIキーをスクリーンショットで共有
- ❌ APIキーをプレーンテキストでメール送信
- ❌ 複数人で同じキーを共有

---

## 📖 関連ドキュメント

- **DEPLOYMENT.md** - 配布ガイド
- **ISSUE_ANALYSIS_REPORT.md** - 問題分析レポート
- **QUICK_FIX_SUMMARY.md** - クイックリファレンス

---

**最終更新**: 2026-01-19 by MEKIKI Development Team
