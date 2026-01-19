# MEKIKI OCR - 業務配布ガイド

## 📋 目次

1. [環境要件](#環境要件)
2. [ビルド手順](#ビルド手順)
3. [配布パッケージの構成](#配布パッケージの構成)
4. [インストール手順（エンドユーザー）](#インストール手順エンドユーザー)
5. [トラブルシューティング](#トラブルシューティング)
6. [サポート情報](#サポート情報)

---

## 環境要件

### 開発環境（ビルド用）

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.8 以上
- **必須パッケージ**:
  - PyInstaller >= 5.0
  - customtkinter >= 5.2.0
  - Pillow >= 10.0.0
  - PyMuPDF >= 1.23.0
  - numpy >= 1.24.0
  - openpyxl >= 3.1.0
  - playwright >= 1.40.0
  - google-generativeai >= 0.3.0

### エンドユーザー環境

- **OS**: Windows 10/11 (64-bit)
- **メモリ**: 4GB 以上推奨（8GB推奨）
- **ディスク空き容量**: 500MB 以上
- **インターネット接続**: API使用時に必要

---

## ビルド手順

### 1. 環境準備

```bash
# 仮想環境作成（推奨）
python -m venv .venv

# 仮想環境有効化
.venv\Scripts\activate  # Windows

# 依存関係インストール
pip install -r requirements.txt
pip install pyinstaller
```

### 2. ビルド実行

```bash
# 標準ビルド
python build.py

# クリーンビルド（推奨）
python build.py --clean

# デバッグビルド
python build.py --debug
```

### 3. ビルド結果確認

ビルド成功後、以下のファイルが生成されます:

```
dist/
├── MEKIKI.exe                    # 実行ファイル（単体）
└── MEKIKI_v1.0.0_YYYYMMDD_HHMMSS/
    ├── MEKIKI.exe                # 配布用実行ファイル
    ├── README.txt                # 使用説明書
    └── MEKIKI_v1.0.0_YYYYMMDD_HHMMSS.zip  # 配布パッケージ
```

---

## 配布パッケージの構成

### ファイル構成

```
MEKIKI_v1.0.0_YYYYMMDD_HHMMSS.zip
├── MEKIKI.exe           # 実行ファイル（全機能統合済み）
└── README.txt           # 使用説明書
```

### 実行ファイルに含まれるもの

- ✅ Python ランタイム
- ✅ すべてのPythonライブラリ
- ✅ CustomTkinterテーマ
- ✅ デフォルト設定ファイル
- ✅ エラーハンドリング機構

### 外部依存（ユーザー提供）

- ❗ **APIキー**: Gemini API、OpenAI API など（初回起動時に設定）
- ❗ **インターネット接続**: API使用時のみ必要

---

## インストール手順（エンドユーザー）

### 1. ダウンロード

1. `MEKIKI_v1.0.0_YYYYMMDD_HHMMSS.zip` をダウンロード
2. 任意のフォルダに解凍（例: `C:\Program Files\MEKIKI\`）

### 2. 初回起動

1. `MEKIKI.exe` をダブルクリック
2. Windows Defenderの警告が出た場合:
   - 「詳細情報」をクリック
   - 「実行」をクリック

### 3. 初期設定

#### APIキー設定

1. メニューバー → **設定 → API設定** を開く
2. 使用するAPIキーを入力:
   - **Gemini API Key** (推奨): Google AI Studioで取得
   - OpenAI API Key (オプション)
   - Anthropic API Key (オプション)
3. 「保存」をクリック

#### APIキー取得方法

**Gemini API Key (推奨・無料枠あり)**:
1. https://makersuite.google.com/app/apikey にアクセス
2. Googleアカウントでログイン
3. 「APIキーを作成」をクリック
4. 生成されたキーをコピー

### 4. 使用開始

1. **WebページOCR**:
   - URLを入力 → 「クロール開始」
   - OCRボタンで文字認識

2. **PDF OCR**:
   - PDFファイルを読み込み
   - OCRボタンで文字認識

3. **結果のエクスポート**:
   - 「Excel Export」でExcel形式で保存

---

## トラブルシューティング

### 起動しない

#### 症状: ダブルクリックしても何も起動しない

**原因と対処**:
1. **Windows Defender がブロック**
   - 右クリック → プロパティ → 「ブロックの解除」にチェック

2. **必須DLLが不足**
   - Visual C++ 再頒布可能パッケージをインストール:
     https://aka.ms/vs/17/release/vc_redist.x64.exe

3. **実行権限がない**
   - 右クリック → 「管理者として実行」

#### 症状: エラーメッセージが表示される

**ログ確認**:
```
C:\Users\<ユーザー名>\AppData\Local\MEKIKI\logs\mekiki_error.log
```

または実行ファイルと同じフォルダ内の `logs/` ディレクトリ

### APIキーエラー

#### 症状: 「APIキーが無効です」

**対処**:
1. 設定 → API設定 を開く
2. APIキーを再入力
3. キーに余分なスペースがないか確認
4. API利用上限に達していないか確認

#### 症状: 「APIタイムアウト」

**対処**:
1. インターネット接続を確認
2. ファイアウォール設定を確認
3. しばらく待ってから再試行（レート制限の可能性）

### メモリ不足

#### 症状: 「メモリ不足が発生しました」

**対処**:
1. 他のアプリケーションを閉じる
2. 処理する画像サイズを小さくする
3. PCを再起動して空きメモリを確保

---

## サポート情報

### ログファイル

エラー発生時は以下のログファイルを確認:

```
logs/
├── mekiki.log          # 全ログ（JSON形式）
├── mekiki_error.log    # エラーログのみ
└── diagnostic.log      # 診断モード時の詳細ログ
```

### 診断レポート生成

1. エラーダイアログで「📤 レポート送信」をクリック
2. 生成されたZIPファイルをサポートに送信

### サポート連絡先

- **メール**: support@mekiki-project.example.com
- **Issue Tracker**: https://github.com/your-org/mekiki/issues

---

## 開発者向け情報

### ビルドオプション

```bash
# クリーンビルド（ビルドキャッシュ削除）
python build.py --clean

# デバッグビルド（詳細ログ付き）
python build.py --debug

# 検証スキップ（高速ビルド）
python build.py --skip-verify

# パッケージング スキップ
python build.py --skip-package
```

### ビルド時の注意事項

1. **仮想環境を使用**
   - グローバル環境でビルドすると不要なパッケージが含まれる

2. **UPX圧縮**
   - `upx=True` で圧縮（サイズ削減）
   - 起動速度を優先する場合は `upx=False`

3. **コンソールウィンドウ**
   - デバッグ時は `console=True` に変更
   - リリース版は `console=False`（GUI専用）

### カスタマイズ

#### アイコン変更

1. `assets/icon.ico` を配置
2. `mekiki.spec` の `icon` パラメータを確認

#### バージョン情報

`mekiki.spec` の `version` 変数を更新

---

## チェックリスト

### ビルド前

- [ ] 仮想環境で作業している
- [ ] すべての依存関係がインストール済み
- [ ] テストが全てパスしている
- [ ] バージョン番号を更新した

### ビルド後

- [ ] 実行ファイルが生成されている
- [ ] ファイルサイズが適正（< 500MB）
- [ ] 実行ファイルが正常に起動する
- [ ] APIキー設定が保存される
- [ ] OCR処理が正常に動作する
- [ ] エラーログが正しく記録される

### 配布前

- [ ] README.txtを確認
- [ ] ZIPファイルを圧縮
- [ ] ウイルススキャン完了
- [ ] テスト環境でインストール検証

---

## バージョン履歴

### v1.0.0 (2026-01-19)
- ✨ 初回リリース
- 🔐 APIキー暗号化保存
- 🎯 スレッドセーフなOCR処理
- 📊 LRU画像キャッシュ（500MB）
- 🎨 高精度座標変換（誤差<0.5px）
- ⌨️ キーボードショートカット統合
- 🔄 Web/PDF スクロール同期
- 📋 仮想化スプレッドシート（1000行対応）
- 🛡️ 統合エラーハンドリング
- 📦 ワンクリックデプロイ

---

© 2026 MEKIKI Project
