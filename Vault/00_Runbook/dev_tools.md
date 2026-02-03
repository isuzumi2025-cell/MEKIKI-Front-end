# 開発効率化ツール

**作成日**: 2026-01-31  
**目的**: 開発サイクル高速化、デバッグ効率向上

---

## 🚀 ツール一覧

| ファイル | 機能 | 使用場面 |
|----------|------|----------|
| `run_dev.py` | 自動キャッシュクリア付きランチャー | コード変更後の起動 |
| `debug_tools.py` | デバッグコマンド集 | 環境確認・キャッシュクリア |
| `config/debug_mode.py` | デバッグモード設定 | 重い処理スキップ |
| `config/fixture_manager.py` | OCR結果キャッシュ | テスト高速化 |
| `config/logging_config.py` | ログ設定 | 詳細ログ出力 |
| `test_minimal.py` | 最小再現テスト | 問題切り分け |
| `app/sdk/notification/context_search.py` | **コンテキスト自動検索** | **作業開始前必須** |

---

## 使用方法

### run_dev.py v2.0

```bash
# 通常起動（キャッシュ自動クリア + ログ設定）
python run_dev.py

# デバッグモード（Gemini補正スキップ）
python run_dev.py --debug

# Fixtureモード（キャッシュデータ使用）
python run_dev.py --fixture

# 環境チェック（起動せず確認のみ）
python run_dev.py --check
```

### test_minimal.py

```bash
# 全テスト実行
python test_minimal.py

# 出力例:
# ✅ API Keys
# ✅ CloudOCREngine
# ✅ HybridOCR Init
# ✅ OCR on test.jpg
```

### Fixture Manager

```python
from config.fixture_manager import get_or_create_fixture

# 一度実行した結果を自動キャッシュ
web_data = get_or_create_fixture(
    "jrkyushu_web",
    lambda: run_web_crawl()
)
```

### Debug Mode

```python
from config.debug_mode import DebugConfig

if DebugConfig.SKIP_GEMINI_CORRECTION:
    # Gemini補正をスキップ
    pass
```

---

## 環境変数

| 変数 | 効果 |
|------|------|
| `MEKIKI_DEBUG=1` | デバッグモード有効 |
| `MEKIKI_SKIP_GEMINI_CORRECTION=1` | Gemini補正スキップ |
| `MEKIKI_USE_FIXTURE=1` | Fixtureデータ使用 |
| `MEKIKI_SKIP_CRAWL=1` | クロールスキップ |

---

## 参照

- [implementation_plan.md](file:///C:/Users/raiko/.gemini/antigravity/brain/5ddc0a0f-7d09-4c38-afa9-774301f31156/implementation_plan.md)
